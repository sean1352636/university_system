# Nursery System - Documentation

Complete documentation for the Nursery / Early Years Management System (children aged 0-5, EYFS).

## Documentation Structure

```
docs/nursery/
├── README.md                 # This file - documentation index
```

> The Nursery system shares the platform's cross-cutting infrastructure with the
> other six systems. For auth, MFA, universal login, and shared infrastructure,
> see the [Shared Infrastructure Docs](../shared/) rather than duplicating them here.

## Quick Start

```bash
# Install
pip install -r requirements.lock
pip install -e .

# Launch directly
python -m education_system --nursery --gui      # Nursery GUI
python -m education_system --nursery --cli      # Nursery CLI
# ...or run `python -m education_system` and choose "Nursery" from the interactive menu

# Run the Nursery tests
python -m pytest tests/unit/systems/nursery/
```

> **Note:** The Nursery system launches directly via `python -m education_system --nursery --gui`
> (or `--cli`), or from the interactive launcher menu. It is fully integrated into
> the shared launcher, authentication, and cross-system switching.

## System Overview

The Nursery System is a comprehensive Early Years management platform for a
nursery / pre-school setting (ages 0-5). It provides:

- **Domain modules** covering the full early-years lifecycle
- **Tkinter GUI** (`gui_main.py`) and a **command-line interface** (`cli_main.py`)
- **SQLite database** at `var/data/nursery/nursery.db`
- **Shared authentication** via `src/education_system/platform/identity/auth/` with the central `auth.db`
- **Role-based access control** (`domain/access.py`): admin and staff logins see every screen. A student or parent login sees only its own account settings and a message, and any other role sees nothing. The GUI and CLI share the rule and check it when a screen opens.
- **TOTP multi-factor authentication**
- **Idle logout** after 30 minutes in the GUI and CLI (`EDU_IDLE_TIMEOUT_MINUTES`; `0` turns it off; the CLI timer is Unix-only)
- **EYFS-aligned** learning, development, and compliance tooling

### Domain areas

| Area | Modules |
|------|---------|
| **Children & enrolment** | children, admissions, enrolment, leavers, transitions, settling_in, cohort_tracking, key_persons |
| **EYFS, curriculum & learning** | eyfs_compliance, eyfs_profile, curriculum_planning, observations, learning_journeys, development_tracking, effective_learning, next_steps, evidence, progress_check_2yr, daily_diary, daily_updates, activity_feed |
| **Health & daily care** | allergies, medication_log, first_aid, accident_log, accident_report, existing_injuries, sleep_log, toileting_log, bottle_feeds, meals, welfare, wellbeing |
| **Safeguarding & compliance** | safeguarding, dsl, concerns, prevent_duty, looked_after, ehc_plans, send, consents, risk_assessments, ofsted, policies, complaints, feedback, gdpr, audit_reports, data_export |
| **Attendance, occupancy & ratios** | daily_register, sign_in_out, attendance_report, occupancy, occupancy_report, ratios, rooms |
| **Finance** | invoices, payments, funded_hours, funding_claims, funding_report, childcare_vouchers, discounts, expense_claims |
| **Staff & HR** | staff, staff_absence, appraisals, qualifications, dbs_checks, recruitment, rota |
| **Communication** | messaging, email_centre, newsletters, parent_contacts, parent_meetings, emergency_contacts, visitors |
| **Administration** | dashboard, user_management, mfa |

## For Developers

### Getting Started

```bash
# Launch Nursery directly
python -m education_system --nursery --gui
python -m education_system --nursery --cli

# Run the Nursery test suite
python -m education_system --nursery --test
# ...or directly with pytest
python -m pytest tests/unit/systems/nursery/
python -m pytest tests/smoke/nursery/
```

### Project Layout

```
src/education_system/systems/nursery/
├── __init__.py              # Re-exports SYSTEM_NAME from manifest.py
├── manifest.py              # Key, display name and interfaces
├── cli_main.py              # CLI entry point
├── gui_main.py              # Tkinter GUI entry point
├── menu.py                  # Menu definitions
├── domain/                  # Domain modules (see Domain areas above), by area:
│                            #   academics, admissions, assessment, finance,
│                            #   governance, learners, operations, pastoral,
│                            #   progression, safeguarding, staff
├── infrastructure/
│   └── database.py          # Database schema and bootstrap (init_db)
├── interfaces/
│   ├── cli/                 # Terminal menus, by area
│   └── gui/                 # Tkinter windows, by area
└── assets/templates/email/  # Email templates

src/education_system/api/nursery/  # REST routes and schemas
src/education_system/paths.py      # Centralized paths (NURSERY_DB, NURSERY_DATA_DIR)
var/data/nursery/nursery.db        # SQLite database
tests/unit/systems/nursery/        # Unit tests
tests/smoke/nursery/               # Smoke test
```

## Related Documentation

| Document | Description |
|----------|-------------|
| [Docs Index](../README.md) | Central documentation index (all seven systems) |
| [Project Structure](../reference/PROJECT_STRUCTURE.md) | Full directory tree |
| [Authentication](../shared/AUTHENTICATION.md) | Shared auth system (bcrypt, sessions, RBAC) |
| [MFA Guide](../shared/MFA_GUIDE.md) | Multi-factor authentication setup |
| [Universal Login](../shared/UNIVERSAL_LOGIN.md) | Cross-system login flow |
| [Infrastructure](../shared/INFRASTRUCTURE.md) | Shared infrastructure overview |

## Documentation Standards

All documentation follows these standards:

- Written in GitHub-flavored Markdown
- Clear, concise, professional language
- Organized by topic with cross-references

---

**Last Updated**: October 2026
