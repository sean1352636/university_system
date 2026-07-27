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
│   ├── AUTHENTICATION.md    # Authentication implementation guide
│   ├── MFA_GUIDE.md         # Multi-factor authentication setup
│   └── ROLES_PERMISSIONS.md # Role-based access control reference
│
├── infrastructure/           # Infrastructure guides
│   ├── DATABASE.md          # Database schema and usage
│   ├── API_REFERENCE.md     # REST API endpoint reference
│   └── LOGGING.md           # Logging configuration and log files
│
├── development/              # Developer documentation
│   ├── README.md            # Development environment setup
│   ├── EXCEPTION_HANDLING.md    # Error handling patterns
│   ├── TESTING_GUIDE.md     # Writing and running tests
│   └── MODULE_DEVELOPMENT.md   # How to create new domain modules
│
└── guides/                   # User and administrator guides
    ├── ADMIN_GUIDE.md       # System administration
    ├── TEACHER_GUIDE.md     # Teacher workflows
    └── STUDENT_GUIDE.md     # Student-facing features
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
| [API_REFERENCE.md](../reference/API_REFERENCE.md) | Flask REST API endpoints and usage |

### Development

| Document | Description |
|----------|-------------|
| [Development README](development/README.md) | Development environment setup and conventions |
| [TESTING_GUIDE.md](development/TESTING_GUIDE.md) | Testing framework and best practices |
| [ADDING_MODULES.md](development/ADDING_MODULES.md) | Guide to building new domain modules |
| [API.md](development/API.md) | Internal API surface for domain modules |

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
- **SQLite database** at `college_system/data/db_files/sixthform.db`
- **Role-based access control** with admin, teacher, and student roles
- **Multi-factor authentication** support
- **Internationalization** with locale files under `college_system/data/locales/`

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
python -m education_system.college_system.run

# Run the API server
python -m education_system.college_system.api.api_server

# Run tests
python -m pytest education_system/college_system/tests/
```

### Key Resources

- **[Module Development](development/ADDING_MODULES.md)** -- Create new domain modules
- **[Testing Guide](development/TESTING_GUIDE.md)** -- Write and run tests

### Project Layout

```
college_system/
├── __init__.py              # Package init (version 1.0.0)
├── core/                    # Core utilities
│   ├── defaults.py          # Default config, credentials, constants
│   ├── exceptions.py        # Exception hierarchy
│   ├── i18n.py              # Internationalization support
│   ├── logs.py              # Logging configuration
│   ├── paths.py             # Centralized path definitions
│   └── sql_safety.py        # SQL injection protection
├── api/                     # Flask REST API
│   ├── api_server.py        # App factory and server entry point
│   ├── config.py            # Flask configuration
│   ├── errors.py            # Global error handlers
│   └── routes/              # API route blueprints
├── infrastructure/          # Infrastructure layer
│   ├── auth/                # Authentication (core, MFA, passwords, roles, sessions)
│   ├── database/            # Database schema and access
│   ├── security/            # Security audit
│   └── validation/          # Input validation
├── modules/domain/          # 110+ domain modules
│   ├── students/            # Student records
│   ├── courses/             # Course management
│   ├── enrollment/          # Enrollment processing
│   ├── attendance/          # Attendance tracking
│   ├── grades/              # Grade management
│   ├── timetable/           # Timetable scheduling
│   └── ...                  # (see full list in QUICK_START.md)
├── data/                    # Runtime data
│   ├── db_files/            # SQLite database files
│   ├── locales/             # Internationalization files
│   └── config/              # Configuration files
└── logs/                    # Application log files
    └── app.log              # Main application log
```

## Documentation Standards

All documentation follows these standards:

- Written in GitHub-flavored Markdown
- Code examples are tested and working
- Clear, concise, professional language
- Organized by topic with cross-references

---

**Last Updated**: March 2026
**Version**: 1.0.0
