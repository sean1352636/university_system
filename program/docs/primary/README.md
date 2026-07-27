# Primary School Management System - Documentation

Complete documentation for the Primary School Management System (v1.0.0).

## Documentation Structure

```
docs/primary/
├── README.md                 # This file - documentation index
├── QUICK_START.md            # Get running in 5 minutes
└── TROUBLESHOOTING.md        # Common issues and solutions
```

## Quick Start

New to the system? Start here:

1. **[Quick Start Guide](QUICK_START.md)** -- Get running in 5 minutes
2. **[Troubleshooting](TROUBLESHOOTING.md)** -- Solve common problems

## By Topic

### Getting Started

| Document | Description |
|----------|-------------|
| [QUICK_START.md](QUICK_START.md) | Installation, first login, and a quick tour of features |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and solutions for login, database, GUI, and CLI |

### Security & Authentication

| Topic | Details |
|-------|---------|
| Shared Auth | Unified authentication via `education_system/shared/auth/` |
| Auth Database | Central `education_system/shared/data/db_files/auth.db` |
| Password Policy | Minimum 8 characters; uppercase, lowercase, digits, and special characters |
| MFA | TOTP via pyotp with recovery codes |
| Sessions | Database-backed with token and expiry; 30-minute timeout by default |
| Lockout | Account locks after 5 failed attempts; 15-minute lockout duration |

### Infrastructure

| Topic | Details |
|-------|---------|
| Database | SQLite at `primary_school/data/db_files/primary_school.db` |
| Logging | File logging at `primary_school/logs/app.log` |
| Configuration | Defaults in `primary_school/core/defaults.py` |
| Exceptions | Hierarchy rooted at `SchoolSystemError` in `primary_school/core/exceptions.py` |
| Paths | Centralized path definitions in `primary_school/core/paths.py` |
| SQL Safety | SQL injection protection in `primary_school/core/sql_safety.py` |

### Development

| Topic | Details |
|-------|---------|
| Language | Python 3.11+ |
| GUI Framework | tkinter with ttk widgets |
| Database | SQLite via `sqlite3` standard library |
| Service Pattern | Service layer with `_conn()` returning `connect(db_path)`, try/except/finally with `conn.close()` |
| Module Layout | Each domain module in `modules/domain/<category>/<module>/` with service and GUI components |

## System Overview

The Primary School Management System is a comprehensive platform for managing all aspects of a primary school (Reception through Year 6). It provides:

- **46 domain modules** covering academics, pastoral care, staff management, administration, pupil life, facilities, and communication
- **7 module categories**: academics (11), pastoral_care (5), staff (4), admin (9), pupil_life (8), facilities (4), communication (6)
- **Tkinter GUI** with tabbed interface and scrollable sidebar navigation
- **Command-line interface** for headless operation
- **SQLite database** at `primary_school/data/db_files/primary_school.db`
- **Shared authentication** with role-based access control (admin, staff, student, parent)
- **Multi-factor authentication** support via TOTP
- **Key stage coverage**: EYFS (Reception), KS1 (Years 1-2), KS2 (Years 3-6)
- **Assessment levels**: Emerging, Developing, Expected, Greater Depth

## Getting Started

```bash
# Activate the virtual environment
source venv/bin/activate

# Launch the GUI
python run.py --primary --gui

# Launch the CLI
python run.py --primary --cli
```

## Project Layout

```
primary_school/
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
│   └── validation/          # Input validation
├── modules/domain/          # 46 domain modules
│   ├── academics/           # pupils, subjects, classes, assessment,
│   │                        # attendance, timetable, homework, sats,
│   │                        # phonics, reading_records, progress
│   ├── pastoral_care/       # behaviour, rewards, safeguarding, send, pastoral
│   ├── staff/               # hr, cpd, cover, staff_directory
│   ├── admin/               # users, settings, admissions, finance,
│   │                        # data_export, audit_log, policies, documents
│   ├── pupil_life/          # clubs, meals, transport, trips,
│   │                        # library, medical, class_groups, consent
│   ├── facilities/          # room_booking, assets, visitors, incidents
│   └── communication/       # email, notifications, announcements,
│                            # calendar, parents_evening, communication_log
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
- Paths use `primary_school/` throughout (not university or college paths)

---

**Last Updated**: March 2026
**Version**: 1.0.0
