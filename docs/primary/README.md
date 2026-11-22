# Primary School Management System - Documentation

Complete documentation for the Primary School Management System.

## Documentation Structure

```
docs/primary/
├── README.md                 # This file - documentation index
├── QUICK_START.md            # Get running in 5 minutes
├── TROUBLESHOOTING.md        # Common issues and solutions
├── development/              # Development guide, adding modules, testing, API
├── guides/                   # Feature guides
├── infrastructure/           # Authentication, configuration, database
└── security/                 # Security, MFA, session timeout
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
| Shared Auth | Unified authentication via `src/education_system/platform/identity/auth/` |
| Auth Database | Central `var/data/platform/db_files/auth.db` |
| Password Policy | Minimum 12 characters; uppercase, lowercase, digits, and special characters |
| MFA | TOTP via pyotp with recovery codes |
| Sessions | Database-backed with token and expiry; 30-minute lifetime by default |
| Lockout | Account locks after 3 failed attempts; 15-minute lockout duration |

### Infrastructure

| Topic | Details |
|-------|---------|
| Database | SQLite at `var/data/primary/primary.db` |
| Logging | Console logging set up by the launcher; `--verbose` shows INFO |
| Configuration | Auth defaults in `src/education_system/platform/identity/auth/defaults.py` |
| Exceptions | Modules raise `ValidationError`; there is no system-wide hierarchy |
| Paths | Centralized path definitions in `src/education_system/paths.py` |
| SQL Safety | SQL injection protection in `src/education_system/platform/kernel/database/sql_safety.py` |

### Development

| Topic | Details |
|-------|---------|
| Language | Python 3.11+ |
| GUI Framework | tkinter with ttk widgets |
| Database | SQLite via `sqlite3` standard library |
| Data Layer Pattern | Module functions call `init_db()`, then `with _connect() as conn:` |
| Module Layout | Domain code in `domain/<area>/<module>/`, screens in `interfaces/{cli,gui}/<area>/<module>/`, routes in `education_system/api/primary/routes/` |

## System Overview

The Primary School Management System is a comprehensive platform for managing all aspects of a primary school (Reception through Year 6). It provides:

- **Domain modules** covering academics, admissions, assessment, finance, governance, learners, operations, pastoral care, safeguarding, and staff
- **9 menu categories**: Pupil Management, Academic Management, Assessment & Progress, Pastoral & Wellbeing, Staff & Communication, Finance, Reports & Analytics, Cross-System, System
- **Tkinter GUI** with scrollable sidebar navigation
- **Command-line interface** for headless operation
- **SQLite database** at `var/data/primary/primary.db`
- **Shared authentication** with role-based access control (admin, staff, student, parent)
- **Multi-factor authentication** support via TOTP
- **Key stage coverage**: EYFS (Reception), KS1 (Years 1-2), KS2 (Years 3-6)
- **Assessment grades**: BLW (Below), WTS (Working Towards), EXS (Expected), GDS (Greater Depth)

## Getting Started

```bash
# Activate your virtual environment first

# Launch the GUI
python -m education_system --primary --gui

# Launch the CLI
python -m education_system --primary --cli
```

## Project Layout

```
src/education_system/systems/primary/
├── __init__.py              # Package init
├── manifest.py              # Key, display name and interfaces
├── cli_main.py              # CLI entry point
├── gui_main.py              # GUI entry point
├── domain/                  # Domain modules
│   ├── academics/           # academic_year, attendance, calendar, classes,
│   │                        # enrichment, homework, lesson_plans, library,
│   │                        # subjects, timetable, year_groups
│   ├── admissions/          # admissions, enrolment
│   ├── assessment/          # assessment, eyfs_profile, ks1_sats, ks2_sats,
│   │                        # mtc, phonics, progress, reading_levels and more
│   ├── finance/             # dinner_money, expense_claims, funding,
│   │                        # pupil_premium, receipts, trips
│   ├── governance/          # audit, compliance, gdpr, mfa, policies and more
│   ├── learners/            # pupils
│   ├── operations/          # assets, communications, document_hub, reporting,
│   │                        # todo, visitors and more
│   ├── pastoral/            # behaviour, house_points, send, transport,
│   │                        # wellbeing and more
│   ├── safeguarding/        # safeguarding, prevent_duty
│   └── staff/               # appraisals, cover, cpd, staff_hr and more
├── infrastructure/          # Currently only __init__.py
└── interfaces/
    ├── cli/                 # Terminal menus, by area
    └── gui/                 # tkinter windows, by area

src/education_system/api/primary/
├── routes/                  # One Flask blueprint per module
└── schemas/                 # Scaffolded, not yet implemented

var/data/primary/primary.db  # SQLite database
```

## Documentation Standards

All documentation follows these standards:

- Written in GitHub-flavored Markdown
- Code examples are tested and working
- Clear, concise, professional language
- Paths are relative to the repository root

---

**Last Updated**: October 2026
