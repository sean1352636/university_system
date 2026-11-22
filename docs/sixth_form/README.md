# Sixth Form College Management System - Documentation

Complete documentation for the Sixth Form College Management System (v1.0.0).

## Documentation Structure

```
docs/sixth_form/
├── README.md                 # This file - documentation index
├── QUICK_START.md            # Get running in 5 minutes
├── TROUBLESHOOTING.md        # Common issues and solutions
│
├── security/                 # Security & Authentication
│   ├── SECURITY.md          # Security features and best practices
│   ├── MFA_GUIDE.md         # Multi-factor authentication setup
│   └── SESSION_TIMEOUT.md   # Idle auto-logout
│
├── infrastructure/           # Infrastructure guides
│   ├── AUTHENTICATION.md    # Authentication implementation guide
│   ├── CONFIGURATION.md     # Configuration reference
│   └── DATABASE.md          # Database schema and usage
│
├── development/              # Developer documentation
│   ├── README.md            # Development environment setup
│   ├── ADDING_MODULES.md    # How to create new domain modules
│   ├── API.md               # REST API reference
│   └── TESTING_GUIDE.md     # Writing and running tests
│
└── guides/                   # User and administrator guides, one per functional area
```

## Quick Start

New to the system? Start here:

1. **[Quick Start Guide](QUICK_START.md)** -- Get running in 5 minutes
2. **[Troubleshooting](TROUBLESHOOTING.md)** -- Solve common problems

## By Topic

### Security & Authentication

| Document | Description |
|----------|-------------|
| [SECURITY.md](security/SECURITY.md) | Security features, password policy, and best practices |
| [AUTHENTICATION.md](infrastructure/AUTHENTICATION.md) | Auth system internals: JWT tokens, session management |
| [MFA_GUIDE.md](security/MFA_GUIDE.md) | Multi-factor authentication setup and usage |

### Infrastructure

| Document | Description |
|----------|-------------|
| [DATABASE.md](infrastructure/DATABASE.md) | SQLite database schema, tables, and query patterns |
| [CONFIGURATION.md](infrastructure/CONFIGURATION.md) | Environment variables, paths, and defaults |
| [API_REFERENCE.md](../reference/API_REFERENCE.md) | Flask REST API endpoints and usage |

### Development

| Document | Description |
|----------|-------------|
| [Development README](development/README.md) | Development environment setup and conventions |
| [TESTING_GUIDE.md](development/TESTING_GUIDE.md) | Testing framework and best practices |
| [ADDING_MODULES.md](development/ADDING_MODULES.md) | Guide to building new domain modules |
| [API.md](development/API.md) | REST API for the sixth form |

### User Guides

One guide per functional area, in [`guides/`](guides/):

| Document | Description |
|----------|-------------|
| [academics.md](guides/academics.md) | Courses, timetabling, and assessment |
| [admissions.md](guides/admissions.md) | Applications, offers, and enrolment |
| [careers_destinations.md](guides/careers_destinations.md) | Careers guidance and destinations tracking |
| [communication.md](guides/communication.md) | Messaging, notifications, and parental contact |
| [facilities.md](guides/facilities.md) | Rooms, resources, and facilities booking |
| [finance_funding.md](guides/finance_funding.md) | Fees, bursaries, and funding |
| [quality_assurance.md](guides/quality_assurance.md) | Quality processes and observations |
| [reporting.md](guides/reporting.md) | Reports and analytics |
| [staff_management.md](guides/staff_management.md) | Staff records and workload |
| [student_support.md](guides/student_support.md) | Pastoral support and interventions |

## System Overview

The Sixth Form College Management System is a comprehensive platform for managing all aspects of a sixth form or further education college. It provides:

- **110+ domain modules** covering academics, student support, staff management, finance, facilities, communication, governance, and more
- **Tkinter GUI** with tabbed interface and scrollable sidebar navigation
- **Flask REST API** for headless and integration use cases
- **SQLite database** at `var/data/sixth_form/sixthform.db`
- **Role-based access control** with admin, staff, teacher, student, and parent roles, shared with the other six systems through the central `var/data/platform/db_files/auth.db`
- **Multi-factor authentication** support
- **Internationalization** through the shared engine in `src/education_system/platform/features/i18n/`

## Troubleshooting

Having issues? Check:

1. **[Troubleshooting Guide](TROUBLESHOOTING.md)** -- Common issues and solutions
2. **[Quick Start Guide](QUICK_START.md)** -- Verify your setup is correct

## For Developers

### Getting Started

```bash
# Activate the virtual environment
source venv/bin/activate

# Run the GUI application
python -m education_system --college --gui

# Run the API server
python -m education_system --college --api

# Run tests
python -m pytest tests/unit/systems/sixth_form/
```

### Key Resources

- **[Module Development](development/ADDING_MODULES.md)** -- Create new domain modules
- **[Testing Guide](development/TESTING_GUIDE.md)** -- Write and run tests

### Project Layout

```
src/education_system/systems/sixth_form/
├── manifest.py              # System key, display name and interfaces
├── assets/templates/email/  # Email templates
├── domain/                  # Domain modules, by area
│   ├── academics/           # Courses, timetable, attendance, library, ...
│   ├── admissions/          # Admissions, enrolments, onboarding
│   ├── assessment/          # Exams, predicted grades, targets, reports
│   ├── governance/          # Policies, GDPR, risk, user management
│   ├── learners/            # Students, alumni, bulk operations, search
│   ├── operations/          # Parent portal, data export
│   ├── pastoral/            # Behaviour, SEND, health, wellbeing
│   ├── progression/         # UCAS, destinations, work experience
│   ├── safeguarding/        # Safeguarding
│   └── staff/               # Staff records, CPD, appraisals
├── domains/                 # Vertical slices
│   ├── communications/      # Messages, notifications, announcements
│   ├── finance/             # Fees, bursaries, funding
│   └── operations/          # Assets, visitors, helpdesk, transport
├── infrastructure/          # Database access, log store, scheduler, integrations
└── interfaces/
    ├── cli/cli_main.py      # CLI entry point, with menus by area
    └── gui/gui_main.py      # GUI entry point, with windows by area

src/education_system/api/sixth_form/
├── access_gate.py           # Capability rule for every route
├── routes/                  # API route blueprints
└── schemas/

var/data/sixth_form/sixthform.db   # SQLite database
```

Authentication, API hosting, validation and other shared code live in `src/education_system/platform/`. See [PROJECT_STRUCTURE.md](../reference/PROJECT_STRUCTURE.md).

## Documentation Standards

All documentation follows these standards:

- Written in GitHub-flavored Markdown
- Clear, concise, professional language
- Organized by topic with cross-references

---

**Last Updated**: October 2026
**Version**: 1.0.0
