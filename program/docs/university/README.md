# University Management System

A comprehensive higher-education management platform built with Python, tkinter (GUI), Flask (REST API), and SQLite. Provides CLI, GUI, API, and web portal interfaces with 51+ domain modules organised in a 4-layer Domain-Driven Design architecture.

---

## Key Features

- Student lifecycle management (admissions through alumni)
- Academic modules: courses, enrollment, grades, attendance, timetable, exams, dissertations
- Finance: invoicing, payments, scholarships, bursaries
- Health and wellbeing services
- Student housing and accommodation
- Commerce: campus shop, marketplace
- HR and staff management
- Student services: careers, counselling, disability support (23 modules)
- Role-based portals: student, staff, instructor, parent
- Digital library and document management
- Analytics and reporting dashboards

---

## Directory Layout

The university system lives at `program/education_system/systems/university/`:

```
university/
    domain/            # Domain modules, grouped by area (academics, admissions,
                       # assessment, finance, governance, learners, operations,
                       # pastoral, progression, safeguarding, staff)
    interfaces/        # Delivery layer — cli/ and gui/
    infrastructure/    # Database, email, security, validation
    services/          # Cross-cutting university services (bus, scheduling)
    assets/            # Web portal templates and static assets
```

Cross-cutting infrastructure shared with the other four systems (auth, unified
API, GDPR, audit, backups) lives under `program/education_system/platform/`.
Tests live at `program/tests/systems/university/`.

API route names do not always match top-level domain folders. The route-to-domain
ownership map is documented in
[`domain/README.md`](../../education_system/systems/university/domain/README.md).

---

## Entry Points

- **GUI:** `python run.py --university --gui` (from repository root)
- **CLI:** `python run.py --university --cli`
- **API:** `python run.py --university --api`

---

## Documentation Structure

```
docs/university/
├── README.md                 # This file — system overview and documentation index
├── QUICK_START.md            # Get running in 5 minutes
├── TROUBLESHOOTING.md        # Common issues and solutions
├── technical_reference.md    # Technical reference
│
├── security/                 # Security & authentication
│   ├── AUTHENTICATION.md     # Authentication implementation guide
│   ├── AUTH_QUICK_REFERENCE.md   # Quick authentication reference
│   ├── MFA_SYSTEM_DOCUMENTATION.md   # Complete MFA guide
│   └── MFA_QUICK_START.md    # MFA setup quick start
│
├── infrastructure/           # Infrastructure guides
│   ├── DATABASE.md           # Database schema and usage
│   ├── TRANSACTIONS.md       # Transaction safety guide
│   └── EMAIL_SCHEDULER.md    # Automated email system
│
├── development/              # Developer documentation
│   ├── README.md             # Development overview
│   ├── EXCEPTION_HANDLING.md # Error handling patterns
│   └── TESTING_GUIDE.md      # Writing and running tests
│
├── guides/                   # User guides by area
├── ai/                       # AI feature documentation
└── modules/                  # Module documentation
    └── README.md             # Module overview and guides
```

The repository-wide security policy — vulnerability reporting, security
features, and the production hardening checklist — is a single document at
[`SECURITY.md`](../../../SECURITY.md) in the repository root.

## Quick Start

New to the system? Start here:

1. **[Quick Start Guide](QUICK_START.md)** — Get running in 5 minutes
2. **[Security Policy](../../../SECURITY.md)** — Security features and hardening
3. **[MFA Setup](security/MFA_QUICK_START.md)** — Enable multi-factor authentication

## By Topic

### Security & Authentication

| Document | Description |
|----------|-------------|
| [SECURITY.md](../../../SECURITY.md) | Security policy, features, and production checklist (repository root) |
| [AUTHENTICATION.md](security/AUTHENTICATION.md) | Authentication system implementation |
| [AUTH_QUICK_REFERENCE.md](security/AUTH_QUICK_REFERENCE.md) | Quick reference for auth operations |
| [MFA_SYSTEM_DOCUMENTATION.md](security/MFA_SYSTEM_DOCUMENTATION.md) | Complete MFA implementation guide |
| [MFA_QUICK_START.md](security/MFA_QUICK_START.md) | Quick MFA setup guide |

### Infrastructure

| Document | Description |
|----------|-------------|
| [DATABASE.md](infrastructure/DATABASE.md) | Database schema, tables, and queries |
| [TRANSACTIONS.md](infrastructure/TRANSACTIONS.md) | Transaction handling and ACID compliance |
| [EMAIL_SCHEDULER.md](infrastructure/EMAIL_SCHEDULER.md) | Automated email scheduling system |

### Development

| Document | Description |
|----------|-------------|
| [Development README](development/README.md) | Development environment setup |
| [EXCEPTION_HANDLING.md](development/EXCEPTION_HANDLING.md) | Error handling patterns and guidelines |
| [TESTING_GUIDE.md](development/TESTING_GUIDE.md) | Testing framework and best practices |

### Modules

| Document | Description |
|----------|-------------|
| [Modules README](modules/README.md) | Overview of all system modules |

## Troubleshooting

Having issues? Check:

1. **[Troubleshooting Guide](TROUBLESHOOTING.md)** — Common issues and solutions
2. **[Auth Quick Reference](security/AUTH_QUICK_REFERENCE.md)** — Authentication problems
3. **[Database Guide](infrastructure/DATABASE.md)** — Database issues

## For Developers

### Getting Started

```bash
# Run tests
make test

# Format code
make format

# Run quality checks
make check
```

### Key Resources

- **[Testing Guide](development/TESTING_GUIDE.md)** — Write and run tests
- **[Exception Handling](development/EXCEPTION_HANDLING.md)** — Error handling patterns

## Documentation Standards

All documentation follows these standards:

- Written in GitHub-flavored Markdown
- Code examples are tested and working
- Clear, concise language
- Organized by topic
