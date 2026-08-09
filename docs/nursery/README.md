# Nursery System - Documentation

Complete documentation for the Nursery / Early Years Management System (children aged 0-5, EYFS).

## Documentation Structure

```
docs/nursery/
├── README.md                 # This file - documentation index
```

> The Nursery system shares the platform's cross-cutting infrastructure with the
> other four systems. For auth, MFA, universal login, and shared infrastructure,
> see the [Shared Infrastructure Docs](../shared/) rather than duplicating them here.

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Launch directly
python run.py --nursery --gui      # Nursery GUI
python run.py --nursery --cli      # Nursery CLI
# ...or run `python run.py` and choose "Nursery" from the interactive menu

# Run the Nursery tests
python -m pytest education_system/nursery_system/tests/
```

> **Note:** The Nursery system launches directly via `python run.py --nursery --gui`
> (or `--cli`), or from the interactive launcher menu. It is fully integrated into
> the shared launcher, authentication, and cross-system switching.

## System Overview

The Nursery System is a comprehensive Early Years management platform for a
nursery / pre-school setting (ages 0-5). It provides:

- **80 domain modules** covering the full early-years lifecycle
- **Tkinter GUI** (`main_gui.py`) and a **command-line interface** (`cli_main.py`)
- **SQLite database** at `nursery_system/data/nursery.db`
- **Shared authentication** via `shared/auth/` with the central `auth.db`
- **Role-based access control** and **TOTP multi-factor authentication**
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
python run.py --nursery --gui
python run.py --nursery --cli

# Run the Nursery test suite
python run.py --nursery --test
# ...or directly with pytest
python -m pytest education_system/nursery_system/tests/
```

### Project Layout

```
nursery_system/
├── __init__.py              # Package init (SYSTEM_NAME = "Nursery System")
├── cli_main.py              # CLI entry point
├── main_gui.py              # Tkinter GUI entry point
├── menu.py                  # Menu definitions
├── core/                    # Core utilities
│   ├── database.py          # Database access helpers
│   └── paths.py             # Centralized paths (NURSERY_DB = data/nursery.db)
├── modules/
│   └── domain/              # 80 domain modules (see Domain areas above)
├── data/                    # Runtime data
│   └── nursery.db           # SQLite database
└── tests/                   # Test suite
```

## Related Documentation

| Document | Description |
|----------|-------------|
| [Docs Index](../README.md) | Central documentation index (all five systems) |
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

**Last Updated**: July 2026
