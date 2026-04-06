# Education System

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![codecov](https://codecov.io/gh/sean1352636/university_system/branch/main/graph/badge.svg)](https://codecov.io/gh/sean1352636/university_system)

A comprehensive, enterprise-grade education management platform spanning four distinct systems — **University**, **Sixth Form College**, **Secondary School**, and **Primary School** — with CLI, GUI, REST API, and Web Portal interfaces, shared authentication, and a unified launcher.

> **Note:** The repository is named `university_system` for historical reasons. The project is now **Education System**.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Systems Overview](#systems-overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Development](#development)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/sean1352636/university_system.git
cd university_system
pip install -r requirements.txt

# Run the unified launcher (interactive system & mode selection)
python run.py

# Or specify system and mode directly
python run.py --university --gui    # University GUI
python run.py --college --gui       # Sixth Form College GUI
python run.py --school --gui        # Secondary School GUI
python run.py --primary --gui       # Primary School GUI
python run.py --college --api       # Unified REST API server

# Common operations
make test                  # Run all tests
make format                # Format code
make lint                  # Check code quality
```

> **Warning**
> Default login: `superadmin` / `SuperAdmin@123` — change immediately in production! See the [default accounts table](#default-accounts) for all 18 pre-configured users.

---

## Systems Overview

| System | Files | Modules | Interfaces | Focus |
|--------|-------|---------|------------|-------|
| **University** | 3,420+ | 51 domains | CLI, GUI, REST API, Web Portal | Higher education — academics, finance, health, housing, commerce, HR, student success (23 modules) |
| **Sixth Form College** | 930+ | 112 domains | CLI, GUI, REST API | FE college (16-19) — apprenticeships, T-levels, UCAS, safeguarding, GDPR, quality assurance |
| **Secondary School** | 290+ | 50 domains | CLI, GUI, REST API, Web Dashboard | Years 7-11 — KS3/KS4, GCSE grades 9-1, pastoral care, behaviour, form groups |
| **Primary School** | 280+ | 46 domains | CLI, GUI, REST API, Web Dashboard | Reception-Year 6 — EYFS/KS1/KS2, phonics, reading records, SATs |

**Combined:** 5,169+ Python files, 257 domain modules, 319 REST API routes, 454+ test files.

All four systems share:
- **Unified launcher** (`run.py`) with CLI & GUI system selection
- **Shared authentication** (`shared/auth/`) — bcrypt, MFA (TOTP), sessions, central `auth.db`
- **Unified REST API** (`shared/api/unified_server.py`) — all 4 systems on one server
- **Web Portal** — browser-based SPA with superadmin dashboard, per-system dashboards, live session monitoring
- **Cross-system switching** without re-authentication
- **GDPR compliance** (`shared/gdpr/`) — consent tracking, data subject rights, data retention, portability
- **Unified audit logging** (`shared/audit/`) — cross-system tamper-detected audit trail
- **Webhook system** (`shared/webhooks/`) — event dispatch with HMAC signatures and retry
- **Offline sync** (`shared/offline/`) — local cache, mutation queue, conflict detection

---

## Architecture

### 4-Layer Domain-Driven Design

```
┌─────────────────────────────────────────────────┐
│  Interface Layer (CLI, GUI, REST API, Web)       │
├─────────────────────────────────────────────────┤
│  Domain/Service Layer (Business Logic)           │
├─────────────────────────────────────────────────┤
│  Infrastructure Layer (Auth, DB, Email, AI)      │
├─────────────────────────────────────────────────┤
│  Data Layer (SQLite with Connection Pool + WAL)  │
└─────────────────────────────────────────────────┘
```

### Tech Stack

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.11+ |
| **GUI** | Tkinter (ttk widgets) |
| **Web** | Flask, flask-cors |
| **Database** | SQLite (default), PostgreSQL, MySQL |
| **Auth** | bcrypt, PyJWT, pyotp (TOTP), WebAuthn, SSO (SAML/OIDC) |
| **Data** | pandas, numpy, matplotlib, seaborn, plotly, scikit-learn |
| **Docs** | reportlab, openpyxl, fpdf2 |
| **Testing** | pytest, pytest-cov, pytest-xdist |
| **Quality** | Black, Ruff, mypy, isort |
| **Real-time** | Socket.IO (WebSocket), GraphQL (Strawberry) |
| **Security** | Fernet encryption, HMAC signatures, ClamAV virus scanning |
| **Integrations** | Canvas, Moodle, Google Classroom, Microsoft Teams |

### High-Level Structure

```
education_system/
├── university_system/       # University (3,420+ files, 51 domains)
├── college_system/          # Sixth Form College (930+ files, 112 domains)
├── secondary_school/        # Secondary School (290+ files, 50 domains)
├── primary_school/          # Primary School (280+ files, 46 domains)
├── shared/                  # Shared modules across all 4 systems
│   ├── api/                 # Unified REST API (unified_server.py + per-system routes)
│   │   └── web/             # Web Portal SPA (HTML/CSS/JS)
│   ├── auth/                # Unified authentication (bcrypt, MFA, sessions)
│   ├── gui/                 # Universal login window & superadmin dashboard
│   ├── extras/              # Shared tools (calculator, query builder, etc.)
│   ├── audit/               # Unified audit logging (tamper detection)
│   ├── gdpr/                # GDPR compliance (consent, SAR, portability)
│   ├── webhooks/            # Webhook dispatch and delivery
│   ├── offline/             # Offline-first sync infrastructure
│   ├── analytics/           # Analytics & early warning predictions
│   ├── backup/              # Encrypted backup/restore with scheduling
│   ├── security/            # Field-level encryption (Fernet AES-128)
│   ├── integrations/        # LMS integrations (Canvas, Moodle, Teams)
│   └── data/                # Central auth.db, config, locales (13 languages)
├── docs/                    # Centralised documentation (150+ files)
└── switch.py                # Runtime system/mode switching

run.py                       # Unified launcher
Makefile                     # Development commands (30+ targets)
```

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for the full directory tree.

---

## Installation

### Prerequisites

- **Python 3.11+** (3.12 recommended)
- **pip** package manager
- **tkinter** (for GUI — usually included with Python; on Ubuntu: `sudo apt-get install python3-tk`)

### Setup

```bash
# Clone
git clone https://github.com/sean1352636/university_system.git
cd university_system

# Install dependencies
pip install -r requirements.txt

# (Optional) Development tools
pip install -e ".[dev]"

# (Optional) AI/ML features
pip install -e ".[ai]"

# (Optional) Cloud integration (AWS/Azure/GCP)
pip install -e ".[cloud]"
```

### Environment Configuration

Copy the example environment file and customise:

```bash
cp .env.example .env
```

Key variables: `API_HOST`, `API_PORT`, `JWT_SECRET_KEY`, `SMTP_*`, `DB_*`. See [`.env.example`](.env.example) for the full list.

---

## Usage

### Unified Launcher

```bash
python run.py                       # Interactive menu
python run.py --university --gui    # Direct launch
python run.py --college --api       # Start API server
```

### REST API & Web Portal

```bash
python run.py --college --api       # Starts unified API on http://0.0.0.0:5000
```

| URL | Description |
|-----|-------------|
| `http://localhost:5000/web/login` | Web Portal (browser SPA) |
| `http://localhost:5000/api/v1/docs` | Swagger UI (interactive API docs) |
| `http://localhost:5000/api/v1/auth/login` | Auth endpoint (POST) |
| `http://localhost:5000/api/v1/health` | Health check |
| `http://localhost:5000/api/v1/{system}/...` | Per-system endpoints (university/college/school/primary) |

The API is accessible from other devices on the network. Configure `API_HOST` and `API_PORT` env vars as needed.

#### Web Portal Features

- JWT-authenticated login with MFA support
- **Superadmin dashboard** — cross-system overview (health, users, analytics, notifications, student search, journey, permissions, backup, batch ops, live sessions)
- **Per-system dashboards** — live statistics, CRUD for students/courses/grades/attendance
- **Live session monitoring** — real-time view of logged-in users with force-logout capability
- **Admin session management** — force-logout any user; they're kicked out within 5 seconds
- Responsive design (desktop, tablet, mobile)

### Default Accounts

| Username | Password | Systems | Role |
|----------|----------|---------|------|
| `superadmin` | `SuperAdmin@123` | All 4 | Admin (all systems) |
| `admin` | `Admin@University123` | University | Admin |
| `staff` | `Staff@University123` | University | Staff |
| `student` | `Student@University123` | University | Student |
| `collegeadmin` | `Admin@College123` | College | Admin |
| `schooladmin` | `Admin@School123` | Secondary | Admin |
| `primaryadmin` | `Admin@Primary123` | Primary | Admin |

Plus per-system staff/student/parent accounts following the pattern `<Role>@<System>123`.

### Makefile Targets

```bash
make help              # Show all available targets
make install           # Install production dependencies
make install-dev       # Install dev dependencies
make run               # Interactive launcher
make run-gui           # Launch GUI mode
make run-api           # Start API server
make test              # Run all tests
make test-cov          # Tests with coverage report
make test-university   # University tests only
make test-college      # College tests only
make lint              # Lint code (Ruff)
make format            # Format code (Black + isort)
make type-check        # Run mypy
make check             # Lint + tests
make security-scan     # Bandit security scan
make seed              # Seed databases with demo data
make clean             # Remove cache and build artifacts
make docker-build      # Build Docker image
```

---

## Configuration

### Database

- **SQLite** (default) — zero configuration, stored in `data/db_files/`
- **PostgreSQL** / **MySQL** — configure via `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` in `.env`

Features: thread-safe connection pooling, WAL mode, ACID compliance, schema migrations, backup/restore.

### Authentication

- **bcrypt** password hashing (with transparent migration from legacy PBKDF2-SHA256)
- **MFA**: TOTP (Google Authenticator), Email OTP, SMS OTP, WebAuthn/FIDO2, Biometric, SSO (SAML 2.0 / OIDC)
- **Sessions**: DB-backed with configurable timeout (`EDU_SESSION_TIMEOUT`, default 30 min)
- **RBAC**: Fine-grained role-based access control (355+ permissions in university system)
- **Password security**: history (reuse prevention), common password rejection, expiry enforcement, timing-attack protection
- **Password reset**: secure token-based flow (`POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password`)
- **Consent tracking**: 15 consent types with grant/withdraw/export (GDPR Article 7)
- **MFA enforcement**: admin/staff users prompted to set up MFA if not configured

---

## Development

```bash
make install-dev       # Install dev dependencies
make setup             # Set up pre-commit hooks
make format            # Format code (Black, line-length 100)
make lint              # Lint (Ruff)
make type-check        # Type check (mypy)
make test              # Run all tests
make test-cov          # Tests with HTML coverage report
make check             # All quality checks
```

### Adding a New Feature

1. Implement business logic in the appropriate domain service
2. Add UI components (CLI menu, GUI tab, API route)
3. Add database tables/migrations if needed
4. Write tests (minimum 80% coverage)
5. Update `CHANGELOG.md`
6. Run `make check` before submitting a PR

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit format, PR process, and how to add a new domain module or system.

---

## Documentation

### Top-Level

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Complete version history (340+ releases) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute, branch naming, commit format |
| [SECURITY.md](SECURITY.md) | Security features, practices, and vulnerability reporting |
| [ROADMAP.md](docs/ROADMAP.md) | Future plans and known limitations |
| [.env.example](.env.example) | Environment variable reference |

### Project-Wide Docs

| Document | Description |
|----------|-------------|
| [Project Structure](docs/PROJECT_STRUCTURE.md) | Full directory tree (all 4 systems) |
| [Deployment Guide](docs/DEPLOYMENT.md) | Docker, nginx, production deployment |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [Module Guides](docs/MODULE_GUIDES.md) | Per-module user guides (20+) |
| [Docs Index](education_system/docs/README.md) | Central documentation index |
| [Appendices](education_system/docs/appendices.md) | Supplementary reference material |

### Architecture Decision Records

| ADR | Description |
|-----|-------------|
| [ADR Index](docs/adr/README.md) | All 12 architecture decisions |
| [ADR-0001](docs/adr/0001-unified-flask-server.md) | Unified Flask server |
| [ADR-0002](docs/adr/0002-shared-authentication.md) | Shared authentication |
| [ADR-0003](docs/adr/0003-sqlite-per-system.md) | SQLite per-system databases |
| [ADR-0004](docs/adr/0004-spa-vanilla-js.md) | Vanilla JS SPA |
| [ADR-0005](docs/adr/0005-service-layer-pattern.md) | Service layer pattern |
| [ADR-0006](docs/adr/0006-domain-driven-module-structure.md) | Domain-driven module structure |
| [ADR-0007](docs/adr/0007-multi-interface-architecture.md) | Multi-interface architecture |
| [ADR-0008](docs/adr/0008-graphql-api.md) | GraphQL API |
| [ADR-0009](docs/adr/0009-websocket-realtime.md) | WebSocket real-time features |
| [ADR-0010](docs/adr/0010-multi-tenancy.md) | Multi-tenancy |
| [ADR-0011](docs/adr/0011-data-retention-gdpr.md) | GDPR data retention |
| [ADR-0012](docs/adr/0012-centralized-structured-logging.md) | Centralized structured logging |
| [ADR Template](docs/adr/template.md) | Template for new ADRs |

### Shared Infrastructure Docs

| Document | Description |
|----------|-------------|
| [Authentication](education_system/docs/shared/AUTHENTICATION.md) | Unified auth system (bcrypt, sessions, RBAC) |
| [MFA Guide](education_system/docs/shared/MFA_GUIDE.md) | Multi-factor authentication setup |
| [Universal Login](education_system/docs/shared/UNIVERSAL_LOGIN.md) | Cross-system login flow |
| [Infrastructure](education_system/docs/shared/INFRASTRUCTURE.md) | Shared infrastructure overview |

### Changelogs

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Current changelog (v8.x) |
| [Legacy Notes](education_system/docs/changelogs/CHANGELOG-legacy-notes.md) | Historical development notes |
| [Module Changelog](education_system/docs/changelogs/CHANGELOG-modules.md) | Per-module change history |
| [v5 Changelog](education_system/docs/changelogs/CHANGELOG-v5.md) | Version 5.x changelog |

### Performance & Testing

| Document | Description |
|----------|-------------|
| [Performance Testing](tests/performance/README.md) | Load testing with Locust, SQLite benchmarks |

---

### University System Docs

<details>
<summary>Click to expand — 60+ guides</summary>

**Overview**

| Document | Description |
|----------|-------------|
| [University README](education_system/docs/university_system/README.md) | University system overview |
| [Quick Start](education_system/docs/university_system/QUICK_START.md) | Getting started guide |
| [Troubleshooting](education_system/docs/university_system/TROUBLESHOOTING.md) | Common issues |
| [Technical Reference](education_system/docs/university_system/technical_reference.md) | Technical specifications |
| [Modules Index](education_system/docs/university_system/modules/README.md) | All domain modules |
| [Guides Index](education_system/docs/university_system/guides/README.md) | All user guides |

**Security**

| Document | Description |
|----------|-------------|
| [Security Overview](education_system/docs/university_system/security/SECURITY.md) | Security architecture |
| [Authentication](education_system/docs/university_system/security/AUTHENTICATION.md) | Auth system details |
| [Auth Quick Reference](education_system/docs/university_system/security/AUTH_QUICK_REFERENCE.md) | Auth cheat sheet |
| [MFA Quick Start](education_system/docs/university_system/security/MFA_QUICK_START.md) | MFA setup guide |
| [MFA Documentation](education_system/docs/university_system/security/MFA_SYSTEM_DOCUMENTATION.md) | Full MFA docs |
| [Security Integration](education_system/docs/university_system/security/SECURITY_INTEGRATION_GUIDE.md) | Security integration guide |

**Infrastructure**

| Document | Description |
|----------|-------------|
| [Database](education_system/docs/university_system/infrastructure/DATABASE.md) | Database architecture |
| [Transactions](education_system/docs/university_system/infrastructure/TRANSACTIONS.md) | Transaction handling |
| [Email Scheduler](education_system/docs/university_system/infrastructure/EMAIL_SCHEDULER.md) | Email scheduling |
| [Admin Monitoring](education_system/docs/university_system/infrastructure/ADMIN_MONITORING_GUIDE.md) | Admin dashboard monitoring |
| [CLI Integration](education_system/docs/university_system/infrastructure/CLI_INTEGRATION_SUMMARY.md) | CLI module integration |
| [Enhancements](education_system/docs/university_system/infrastructure/ENHANCEMENTS_GUIDE.md) | Infrastructure improvements |
| [Implementation Summary](education_system/docs/university_system/infrastructure/IMPLEMENTATION_SUMMARY.md) | Implementation details |

**Development**

| Document | Description |
|----------|-------------|
| [Development Guide](education_system/docs/university_system/development/README.md) | Developer setup |
| [Adding Modules](education_system/docs/university_system/development/ADDING_MODULES.md) | How to add new modules |
| [API Guide](education_system/docs/university_system/development/API.md) | REST API development |
| [Testing Guide](education_system/docs/university_system/development/TESTING_GUIDE.md) | Testing practices |
| [Exception Handling](education_system/docs/university_system/development/EXCEPTION_HANDLING.md) | Error handling patterns |
| [Migration Guide](education_system/docs/university_system/development/MIGRATION_GUIDE.md) | Database migrations |

**AI & ML**

| Document | Description |
|----------|-------------|
| [AI Dependencies](education_system/docs/university_system/ai/AI_DEPENDENCIES.md) | AI/ML library setup |
| [Voice Features](education_system/docs/university_system/ai/VOICE_FEATURES.md) | Speech-to-text, TTS |

**Academic Guides**

| Document | Description |
|----------|-------------|
| [Academic Calendar](education_system/docs/university_system/guides/academics/academic-calendar.md) | Calendar management |
| [AI Detector](education_system/docs/university_system/guides/academics/AI_DETECTOR_GUIDE.md) | AI content detection |
| [Assignments](education_system/docs/university_system/guides/academics/ASSIGNMENT_SYSTEM_GUIDE.md) | Assignment system |
| [Attendance Tracking](education_system/docs/university_system/guides/academics/attendance-tracking.md) | Attendance system |
| [Blockchain Credentials](education_system/docs/university_system/guides/academics/BLOCKCHAIN_CREDENTIALS_GUIDE.md) | Credential verification |
| [Course Management](education_system/docs/university_system/guides/academics/COURSE_MANAGEMENT_GUIDE.md) | Course CRUD |
| [Degree Audit](education_system/docs/university_system/guides/academics/DEGREE_AUDIT_GUIDE.md) | Degree progress tracking |
| [Exam Scheduler](education_system/docs/university_system/guides/academics/EXAM_SCHEDULER_GUIDE.md) | Exam scheduling |
| [Grade Tracking](education_system/docs/university_system/guides/academics/GRADE_TRACKING_GUIDE.md) | Grading system |
| [Library Management](education_system/docs/university_system/guides/academics/library-management.md) | Library system |
| [Module Scheduling](education_system/docs/university_system/guides/academics/module-scheduling.md) | Timetable scheduling |
| [Plagiarism Detection](education_system/docs/university_system/guides/academics/PLAGIARISM_DETECTION_GUIDE.md) | Plagiarism checker |
| [Research Grants](education_system/docs/university_system/guides/academics/RESEARCH_GRANTS_GUIDE.md) | Grant management |
| [Virtual Classroom](education_system/docs/university_system/guides/academics/VIRTUAL_CLASSROOM_GUIDE.md) | Online classroom |

**Administration Guides**

| Document | Description |
|----------|-------------|
| [Accessibility Services](education_system/docs/university_system/guides/administration/ACCESSIBILITY_SERVICES_GUIDE.md) | Accessibility features |
| [Activity Logger](education_system/docs/university_system/guides/administration/ACTIVITY_LOGGER_AUDIT_TRAIL_GUIDE.md) | Audit trail |
| [Admissions CRM](education_system/docs/university_system/guides/administration/ADMISSIONS_CRM_GUIDE.md) | Admissions management |
| [Advanced Search](education_system/docs/university_system/guides/administration/ADVANCED_SEARCH_ANALYTICS_GUIDE.md) | Search & analytics |
| [Auth & MFA](education_system/docs/university_system/guides/administration/authentication-mfa.md) | Authentication guide |
| [Dark Mode](education_system/docs/university_system/guides/administration/DARK_MODE_GUIDE.md) | Theme customisation |
| [Database Management](education_system/docs/university_system/guides/administration/database-management.md) | DB admin |
| [Data Encryption](education_system/docs/university_system/guides/administration/DATA_ENCRYPTION_GUIDE.md) | Encryption guide |
| [Email Receipts](education_system/docs/university_system/guides/administration/EMAIL_RECEIPTS_GUIDE.md) | Email receipts |
| [Email System Admin](education_system/docs/university_system/guides/administration/EMAIL_SYSTEM_ADMIN_GUIDE.md) | Email administration |
| [Mobile App/PWA](education_system/docs/university_system/guides/administration/MOBILE_APP_PWA_GUIDE.md) | PWA features |
| [Security Dashboard](education_system/docs/university_system/guides/administration/SECURITY_DASHBOARD_GUIDE.md) | Security monitoring |
| [Staff CRUD](education_system/docs/university_system/guides/administration/STAFF_CRUD_GUIDE.md) | Staff management |

**Campus Guides**

| Document | Description |
|----------|-------------|
| [Campus Events](education_system/docs/university_system/guides/campus/CAMPUS_EVENTS_GUIDE.md) | Events management |
| [Campus Navigation](education_system/docs/university_system/guides/campus/CAMPUS_NAVIGATION_GUIDE.md) | Campus map/navigation |
| [Dentist](education_system/docs/university_system/guides/campus/DENTIST_GUIDE.md) | Dental services |
| [Equipment Management](education_system/docs/university_system/guides/campus/EQUIPMENT_MANAGEMENT_GUIDE.md) | Equipment tracking |
| [Facilities](education_system/docs/university_system/guides/campus/FACILITIES_MANAGEMENT_GUIDE.md) | Facilities management |
| [Gym & Fitness](education_system/docs/university_system/guides/campus/GYM_FITNESS_GUIDE.md) | Gym booking |
| [Health Portal](education_system/docs/university_system/guides/campus/HEALTH_PORTAL_GUIDE.md) | Health services |
| [Housing](education_system/docs/university_system/guides/campus/housing-accommodation.md) | Student housing |
| [Mail & Post](education_system/docs/university_system/guides/campus/MAIL_POST_GUIDE.md) | Mail services |
| [Parking](education_system/docs/university_system/guides/campus/PARKING_MANAGEMENT_GUIDE.md) | Parking management |

**Commerce Guides**

| Document | Description |
|----------|-------------|
| [Barber Shop](education_system/docs/university_system/guides/commerce/BARBER_SHOP_GUIDE.md) | Barber booking |
| [Bar/Cafe/Grocery/Takeaway](education_system/docs/university_system/guides/commerce/BAR_CAFE_GROCERY_TAKEAWAY_GUIDE.md) | Food & drink |
| [Betting Shop](education_system/docs/university_system/guides/commerce/BETTING_SHOP_GUIDE.md) | Betting services |
| [Butcher Shop](education_system/docs/university_system/guides/commerce/BUTCHER_SHOP_GUIDE.md) | Butcher shop |
| [Car Rental](education_system/docs/university_system/guides/commerce/CAR_RENTAL_GUIDE.md) | Car rental |
| [Cinema Booking](education_system/docs/university_system/guides/commerce/CINEMA_BOOKING_GUIDE.md) | Cinema reservations |
| [Legal Services](education_system/docs/university_system/guides/commerce/LEGAL_SERVICES_GUIDE.md) | Legal support |
| [Music Shop](education_system/docs/university_system/guides/commerce/MUSIC_SHOP_GUIDE.md) | Music shop |
| [Nail Bar/Phone Shop](education_system/docs/university_system/guides/commerce/NAIL_BAR_PHONE_SHOP_GUIDE.md) | Services |
| [Restaurant Management](education_system/docs/university_system/guides/commerce/RESTAURANT_MANAGEMENT_GUIDE.md) | Restaurant system |
| [Restaurant Reports](education_system/docs/university_system/guides/commerce/RESTAURANT_REPORTS_GUIDE.md) | Restaurant analytics |
| [Taxi/Train/Trip](education_system/docs/university_system/guides/commerce/TAXI_TRAIN_TRIP_GUIDE.md) | Transport booking |

**Student Life Guides**

| Document | Description |
|----------|-------------|
| [Alumni Management](education_system/docs/university_system/guides/student-life/ALUMNI_MANAGEMENT_GUIDE.md) | Alumni tracking |
| [Budgeting & Portfolio](education_system/docs/university_system/guides/student-life/BUDGETING_PORTFOLIO_GUIDE.md) | Financial tools |
| [Career Services](education_system/docs/university_system/guides/student-life/CAREER_SERVICES_GUIDE.md) | Career support |
| [Early Warning](education_system/docs/university_system/guides/student-life/EARLY_WARNING_GUIDE.md) | At-risk student alerts |
| [Finance Management](education_system/docs/university_system/guides/student-life/finance-management.md) | Student finance |
| [Financial Aid](education_system/docs/university_system/guides/student-life/FINANCIAL_AID_GUIDE.md) | Financial aid |
| [Helpdesk](education_system/docs/university_system/guides/student-life/HELPDESK_SUPPORT_GUIDE.md) | Support tickets |
| [Lost & Found](education_system/docs/university_system/guides/student-life/LOST_FOUND_FEEDBACK_NOTIFICATIONS_GUIDE.md) | Lost items & feedback |
| [Roommate Matching](education_system/docs/university_system/guides/student-life/ROOMMATE_SOCIAL_STUDY_MATCHING_GUIDE.md) | Social matching |
| [Scholarship Finder](education_system/docs/university_system/guides/student-life/SCHOLARSHIP_FINDER_GUIDE.md) | Scholarship search |
| [Student Jobs](education_system/docs/university_system/guides/student-life/STUDENT_JOBS_GUIDE.md) | Job board |
| [Student Marketplace](education_system/docs/university_system/guides/student-life/STUDENT_MARKETPLACE_GUIDE.md) | Buy/sell marketplace |
| [Student Union](education_system/docs/university_system/guides/student-life/STUDENT_UNION_GUIDE.md) | Union management |

</details>

---

### Sixth Form College Docs

<details>
<summary>Click to expand</summary>

| Document | Description |
|----------|-------------|
| [College README](education_system/docs/college_system/README.md) | College system overview |
| [Quick Start](education_system/docs/college_system/QUICK_START.md) | Getting started |
| [Troubleshooting](education_system/docs/college_system/TROUBLESHOOTING.md) | Common issues |
| **Development** | |
| [Development Guide](education_system/docs/college_system/development/README.md) | Developer setup |
| [Adding Modules](education_system/docs/college_system/development/ADDING_MODULES.md) | New module guide |
| [API Guide](education_system/docs/college_system/development/API.md) | REST API development |
| [Testing Guide](education_system/docs/college_system/development/TESTING_GUIDE.md) | Testing practices |
| **Infrastructure** | |
| [Authentication](education_system/docs/college_system/infrastructure/AUTHENTICATION.md) | Auth config |
| [Configuration](education_system/docs/college_system/infrastructure/CONFIGURATION.md) | System config |
| [Database](education_system/docs/college_system/infrastructure/DATABASE.md) | Database setup |
| **Security** | |
| [Security](education_system/docs/college_system/security/SECURITY.md) | Security overview |
| [MFA Guide](education_system/docs/college_system/security/MFA_GUIDE.md) | MFA setup |
| **User Guides** | |
| [Academics](education_system/docs/college_system/guides/academics.md) | Academic management |
| [Admissions](education_system/docs/college_system/guides/admissions.md) | Admissions process |
| [Careers & Destinations](education_system/docs/college_system/guides/careers_destinations.md) | Career tracking |
| [Communication](education_system/docs/college_system/guides/communication.md) | Messaging & email |
| [Facilities](education_system/docs/college_system/guides/facilities.md) | Facility management |
| [Finance & Funding](education_system/docs/college_system/guides/finance_funding.md) | Financial management |
| [Quality Assurance](education_system/docs/college_system/guides/quality_assurance.md) | QA processes |
| [Reporting](education_system/docs/college_system/guides/reporting.md) | Reports & exports |
| [Staff Management](education_system/docs/college_system/guides/staff_management.md) | Staff admin |
| [Student Support](education_system/docs/college_system/guides/student_support.md) | Student services |

</details>

---

### Secondary School Docs

<details>
<summary>Click to expand</summary>

| Document | Description |
|----------|-------------|
| [Secondary README](education_system/docs/secondary_school/README.md) | Secondary system overview |
| [Quick Start](education_system/docs/secondary_school/QUICK_START.md) | Getting started |
| [Troubleshooting](education_system/docs/secondary_school/TROUBLESHOOTING.md) | Common issues |
| **Development** | |
| [Development Guide](education_system/docs/secondary_school/development/README.md) | Developer setup |
| [Adding Modules](education_system/docs/secondary_school/development/ADDING_MODULES.md) | New module guide |
| [API Guide](education_system/docs/secondary_school/development/API.md) | REST API development |
| [Testing Guide](education_system/docs/secondary_school/development/TESTING_GUIDE.md) | Testing practices |
| **Infrastructure** | |
| [Authentication](education_system/docs/secondary_school/infrastructure/AUTHENTICATION.md) | Auth config |
| [Configuration](education_system/docs/secondary_school/infrastructure/CONFIGURATION.md) | System config |
| [Database](education_system/docs/secondary_school/infrastructure/DATABASE.md) | Database setup |
| **Security** | |
| [Security](education_system/docs/secondary_school/security/SECURITY.md) | Security overview |
| [MFA Guide](education_system/docs/secondary_school/security/MFA_GUIDE.md) | MFA setup |
| **User Guides** | |
| [Academics](education_system/docs/secondary_school/guides/academics.md) | Academic management |
| [Admin](education_system/docs/secondary_school/guides/admin.md) | Administration |
| [Communication](education_system/docs/secondary_school/guides/communication.md) | Messaging & email |
| [Facilities](education_system/docs/secondary_school/guides/facilities.md) | Facility management |
| [Pastoral Care](education_system/docs/secondary_school/guides/pastoral_care.md) | Pastoral support |
| [Staff Management](education_system/docs/secondary_school/guides/staff_management.md) | Staff admin |
| [Student Life](education_system/docs/secondary_school/guides/student_life.md) | Student activities |

</details>

---

### Primary School Docs

<details>
<summary>Click to expand</summary>

| Document | Description |
|----------|-------------|
| [Primary README](education_system/docs/primary_school/README.md) | Primary system overview |
| [Quick Start](education_system/docs/primary_school/QUICK_START.md) | Getting started |
| [Troubleshooting](education_system/docs/primary_school/TROUBLESHOOTING.md) | Common issues |
| **Development** | |
| [Development Guide](education_system/docs/primary_school/development/README.md) | Developer setup |
| [Adding Modules](education_system/docs/primary_school/development/ADDING_MODULES.md) | New module guide |
| [API Guide](education_system/docs/primary_school/development/API.md) | REST API development |
| [Testing Guide](education_system/docs/primary_school/development/TESTING_GUIDE.md) | Testing practices |
| **Infrastructure** | |
| [Authentication](education_system/docs/primary_school/infrastructure/AUTHENTICATION.md) | Auth config |
| [Configuration](education_system/docs/primary_school/infrastructure/CONFIGURATION.md) | System config |
| [Database](education_system/docs/primary_school/infrastructure/DATABASE.md) | Database setup |
| **Security** | |
| [Security](education_system/docs/primary_school/security/SECURITY.md) | Security overview |
| [MFA Guide](education_system/docs/primary_school/security/MFA_GUIDE.md) | MFA setup |
| **User Guides** | |
| [Academics](education_system/docs/primary_school/guides/academics.md) | Academic management |
| [Admin](education_system/docs/primary_school/guides/admin.md) | Administration |
| [Communication](education_system/docs/primary_school/guides/communication.md) | Messaging & email |
| [Facilities](education_system/docs/primary_school/guides/facilities.md) | Facility management |
| [Pastoral Care](education_system/docs/primary_school/guides/pastoral_care.md) | Pastoral support |
| [Pupil Life](education_system/docs/primary_school/guides/pupil_life.md) | Pupil activities |
| [Staff Management](education_system/docs/primary_school/guides/staff_management.md) | Staff admin |

</details>

---

## What's New

### Version 8.57.0 (March 30, 2026) — Latest

- **28-item security & feature hardening** — encryption enforcement, password expiry/history/reuse prevention, forgot password flow, common password blocking, timing oracle fix, MFA enforcement, persistent rate limiting, unified audit logging, zip bomb detection, API key expiry/rotation, backup encryption, webhook system, GDPR consent tracking, data subject rights (rectification/restriction/portability), configurable retention, cross-system consent, offline sync, PWA/mobile support, MS Teams integration, GraphQL additions, real-time WebSocket helpers, AI/ML early warning, primary school skills tracker, WCAG accessibility tests

### Version 8.56.0 (March 29, 2026)

- **Comprehensive CI test failure remediation** — reduced failures from 1615 to ~1000 across 10 commits

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, including:

- Branch naming conventions (`feature/`, `bugfix/`, `docs/`)
- Commit message format (`feat:`, `fix:`, `docs:`)
- How to add a new domain module
- How to add a new system (5th system integration points)
- Code style, testing requirements, and PR process

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## Support

- **Documentation**: [Docs Index](education_system/docs/university_system/README.md)
- **Issues**: [GitHub Issues](https://github.com/sean1352636/university_system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sean1352636/university_system/discussions)

---

**Made with dedication for educational institutions worldwide — from primary schools to universities.**
