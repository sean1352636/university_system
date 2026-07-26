# Secondary School Management System - Documentation

Complete documentation for the Secondary School Management System.

## Documentation Structure

```
docs/secondary_school/
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
│   ├── CONFIGURATION.md     # Configuration reference
│   └── LOGGING.md           # Logging configuration and log files
│
├── development/              # Developer documentation
│   ├── README.md            # Development environment setup
│   ├── EXCEPTION_HANDLING.md    # Error handling patterns
│   ├── TESTING_GUIDE.md     # Writing and running tests
│   └── ADDING_MODULES.md   # How to create new domain modules
│
└── guides/                   # User and administrator guides
    ├── academics.md         # Academic workflows (grades, attendance, exams)
    ├── pastoral_care.md     # Pastoral care and safeguarding
    ├── staff_management.md  # Staff HR, CPD, and cover
    ├── admin.md             # System administration
    ├── student_life.md      # Clubs, meals, transport, and more
    ├── facilities.md        # Room booking, assets, visitors
    └── communication.md     # Email, notifications, parents evening
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
| [AUTHENTICATION.md](infrastructure/AUTHENTICATION.md) | Shared auth system, sessions, and password hashing |
| [MFA_GUIDE.md](security/MFA_GUIDE.md) | Multi-factor authentication setup and usage |

### Infrastructure

| Document | Description |
|----------|-------------|
| [DATABASE.md](infrastructure/DATABASE.md) | SQLite database schema, tables, and query patterns |
| [CONFIGURATION.md](infrastructure/CONFIGURATION.md) | Configuration reference and environment variables |

### Development

| Document | Description |
|----------|-------------|
| [Development README](development/README.md) | Development environment setup and conventions |
| [TESTING_GUIDE.md](development/TESTING_GUIDE.md) | Testing framework and best practices |
| [ADDING_MODULES.md](development/ADDING_MODULES.md) | Guide to building new domain modules |

### User Guides

| Document | Description |
|----------|-------------|
| [academics.md](guides/academics.md) | Student records, grades (9-1), attendance, exams, timetable |
| [pastoral_care.md](guides/pastoral_care.md) | Behaviour, detentions, safeguarding, SEND, pastoral |
| [staff_management.md](guides/staff_management.md) | HR, CPD, cover management, staff directory |
| [admin.md](guides/admin.md) | Users, settings, admissions, finance, audit log |
| [student_life.md](guides/student_life.md) | Clubs, meals, transport, trips, careers, library |
| [facilities.md](guides/facilities.md) | Room booking, assets, seating plans, visitors |
| [communication.md](guides/communication.md) | Email, notifications, calendar, parents evening |

## System Overview

The Secondary School Management System is a comprehensive platform for managing all aspects of a secondary school (Years 7-11). It provides:

- **51 domain modules** across 7 categories covering academics, pastoral care, staff, admin, student life, facilities, and communication
- **Tkinter GUI** with tabbed interface and scrollable sidebar navigation
- **Command-line interface** for headless operation
- **SQLite database** at `secondary_school/data/db_files/secondary_school.db`
- **Shared authentication** via `shared/auth/` with central `auth.db`
- **Role-based access control** with admin, staff, student, and parent roles
- **Multi-factor authentication** support via TOTP
- **GCSE grading** on the 9-1 scale
- **Key stage support** for KS3 (Years 7-9) and KS4 (Years 10-11)

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
python run.py --school --gui

# Run the CLI application
python run.py --school --cli

# Run tests
python -m pytest education_system/secondary_school/tests/
```

### Key Resources

- **[Adding Modules](development/ADDING_MODULES.md)** -- Create new domain modules
- **[Testing Guide](development/TESTING_GUIDE.md)** -- Write and run tests

### Project Layout

```
secondary_school/
├── __init__.py              # Package init
├── core/                    # Core utilities
│   ├── defaults.py          # Default config, credentials, constants
│   ├── exceptions.py        # Exception hierarchy (SchoolSystemError)
│   ├── i18n.py              # Internationalization support
│   ├── logs.py              # Logging configuration
│   ├── paths.py             # Centralized path definitions
│   └── sql_safety.py        # SQL injection protection
├── infrastructure/          # Infrastructure layer
│   ├── auth/                # Authentication (wraps shared auth)
│   ├── database/            # Database schema and access
│   ├── security/            # Security audit
│   └── validation/          # Input validation
├── modules/domain/          # 51 domain modules
│   ├── academics/           # Students, subjects, grades, attendance, ...
│   ├── pastoral_care/       # Behaviour, detentions, safeguarding, SEND, ...
│   ├── staff/               # HR, CPD, cover, staff directory
│   ├── admin/               # Users, settings, finance, audit log, ...
│   ├── student_life/        # Clubs, meals, transport, trips, careers, ...
│   ├── facilities/          # Room booking, assets, seating plans, ...
│   └── communication/       # Email, notifications, calendar, ...
├── data/                    # Runtime data
│   ├── db_files/            # SQLite database files
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
