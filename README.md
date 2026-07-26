# Education System

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![codecov](https://codecov.io/gh/sean1352636/university_system/branch/main/graph/badge.svg)](https://codecov.io/gh/sean1352636/university_system)

A comprehensive, feature-rich education management platform spanning five distinct systems — **Nursery**, **Primary School**, **Secondary School**, **Sixth Form College**, and **University** — with CLI, GUI, REST API, and Web Portal interfaces, shared authentication, and a unified launcher.

> **Project status:** Feature-complete for demonstration and development use, but **not recommended for production** without first implementing the outstanding [security recommendations](program/docs/university_system/security/SECURITY.md). See the [Roadmap](program/docs/operations/ROADMAP.md) for known limitations.

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
python run.py --university --gui           # University GUI
python run.py --college --gui              # Sixth Form College GUI (--sixthform alias)
python run.py --school --gui               # Secondary School GUI (--secondary alias)
python run.py --primary --gui              # Primary School GUI
python run.py --nursery --gui              # Nursery / Early Years GUI
python run.py --university --api           # Unified REST API server

# Common operations
make test                  # Run all tests
make format                # Format code
make lint                  # Check code quality
```

> **Warning**
> Dev login `admin` / `admin123` is created **only** with `EDU_DEV_SEED=true` (fine for local/demo use, never for production). A fresh production database is left empty — bootstrap it with `EDU_INITIAL_ADMIN_USER` / `EDU_INITIAL_ADMIN_PASSWORD` instead. See [Default Accounts](program/docs/reference/DEFAULT_ACCOUNTS.md) for the full list of pre-configured users across all five systems.

---

## Systems Overview

| System | Files | Modules | Interfaces | Focus |
|--------|-------|---------|------------|-------|
| **Nursery** | 360+ | 80 domain modules | CLI, GUI | Early years (0-5) — EYFS, Ofsted, funded hours, ratios/occupancy, safeguarding (DSL/Prevent), learning journeys, 2-year progress checks, daily diary |
| **Primary School** | 420+ | Reception-Year 6 domains | CLI, GUI, REST API, Web Dashboard | Reception-Year 6 — EYFS/KS1/KS2, phonics, reading records, SATs |
| **Secondary School** | 440+ | Years 7-11 domains | CLI, GUI, REST API, Web Dashboard | Years 7-11 — KS3/KS4, GCSE grades 9-1, pastoral care, behaviour, form groups |
| **Sixth Form College** | 570+ | FE college domains | CLI, GUI, REST API | FE college (16-19) — apprenticeships, T-levels, UCAS, safeguarding, GDPR, quality assurance |
| **University** | 3,900+ | 9 domain categories (60+ sub-modules) | CLI, GUI, REST API, Web Portal | Higher education — academics, admissions, analytics, campus, commerce, finance, health, operations, student affairs |

**Combined:** 5,600+ Python files across the five systems plus shared infrastructure. The University domain directory was reorganised into top-level categories (academics, admissions, analytics, campus, commerce, finance, health, operations, student_affairs) in the 9.0.0 release; the Nursery system was added in 9.0.0.

All five systems share:
- **Unified launcher** (`run.py`) with CLI & GUI system selection
- **Shared authentication** (`shared/auth/`) — bcrypt, MFA (TOTP), sessions, central `auth.db`
- **Unified REST API** (`shared/api/unified_server.py`) — all systems on one server
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
├── nursery_system/          # Nursery / Early Years (0-5, EYFS)
├── primarysch_system/       # Primary School (Reception-Year 6)
├── secondarysch_system/     # Secondary School (Years 7-11)
├── post_16/                 # Post-16 phase
│   └── sixthform_system/    # Sixth Form College (16-19)
├── post_18/                 # Post-18 phase
│   └── university_system/   # University (3,900+ files, 9 domain categories)
├── shared/                  # Shared modules across all systems
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
├── migrations/              # Alembic migration scripts
└── switch.py                # Runtime system/mode switching

run.py                       # Unified launcher
Makefile                     # Development commands (30+ targets)
```

See [program/docs/reference/PROJECT_STRUCTURE.md](program/docs/reference/PROJECT_STRUCTURE.md) for the full directory tree.

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

# Smallest supported install — everything the shipped core features need
pip install -r requirements.txt      # pinned/reproducible
#   or:  pip install -e .            # minimum-range install from pyproject.toml
```

This runtime install covers all five systems across CLI, GUI, REST API and web.
The scientific/reporting stack (numpy, pandas, scikit-learn, matplotlib, …) is
part of it because core academics and finance features depend on it.

#### Optional feature tiers (pip extras)

Install only what you need — none of these are required to run the app:

```bash
pip install -e ".[dev]"          # tests, ruff, mypy, black  (or: -r requirements-dev.txt)
pip install -e ".[security]"     # bandit, safety, pip-audit, semgrep
pip install -e ".[perf]"         # locust load testing
pip install -e ".[ai]"           # torch / transformers / spaCy / OpenCV
pip install -e ".[graphql]"      # GraphQL API layer
pip install -e ".[realtime]"     # WebSocket / Socket.IO
pip install -e ".[postgres]"     # PostgreSQL backend   (".[mysql]" for MySQL)
pip install -e ".[cloud-aws]"    # AWS only (".[cloud-azure]", ".[cloud-gcp]", or ".[cloud]" for all)
pip install -e ".[integrations]" # Google Classroom LMS, Twilio SMS
pip install -e ".[remote]"       # SSH/SFTP (paramiko)
```

> Development/CI tooling is **not** in `requirements.txt`; it lives in
> `requirements-dev.txt` (equivalently the `dev`/`security`/`perf` extras) so
> ordinary users don't install pytest, locust, semgrep or bandit.

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
| `http://localhost:5000/api/v1/{system}/...` | Per-system endpoints (university/college/school/primary/nursery) |

The API is accessible from other devices on the network. Configure `API_HOST` and `API_PORT` env vars as needed.

#### Web Portal Features

- JWT-authenticated login with MFA support
- **Superadmin dashboard** — cross-system overview (health, users, analytics, notifications, student search, journey, permissions, backup, batch ops, live sessions)
- **Per-system dashboards** — live statistics, CRUD for students/courses/grades/attendance
- **Live session monitoring** — real-time view of logged-in users with force-logout capability
- **Admin session management** — force-logout any user; they're kicked out within 5 seconds
- Responsive design (desktop, tablet, mobile)

### Default Accounts

See [program/docs/reference/DEFAULT_ACCOUNTS.md](program/docs/reference/DEFAULT_ACCOUNTS.md) for pre-seeded dev credentials across all five systems. Change every password before any non-development deployment.

> These demo accounts are flagged `must_change_password`, so the app forces a new password on first login and won't let the seeded password persist. Seeding runs **only** when `EDU_DEV_SEED=true` — a fresh database without the flag (the production default) is never populated with them. To provision a production admin, set `EDU_INITIAL_ADMIN_USER` / `EDU_INITIAL_ADMIN_PASSWORD` (≥12 chars) for a single strong account. The passwords are published here **only** because they're well-known dev defaults — treat any deployment that still accepts them as unconfigured.

### Makefile Targets

Run `make help` for the full list. Common ones:

```bash
make run               # Interactive launcher
make test              # Run all tests
make format            # Format (Black + isort)
make lint              # Lint (Ruff)
make check             # Lint + tests
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
| [CHANGELOG.md](CHANGELOG.md) | Complete version history (latest **9.7.0** on 2026-07-23) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute, branch naming, commit format |
| [SECURITY.md](SECURITY.md) | Security features, practices, and vulnerability reporting |
| [ROADMAP.md](program/docs/operations/ROADMAP.md) | Future plans and known limitations |
| [.env.example](.env.example) | Environment variable reference |

### Project-Wide Docs

| Document | Description |
|----------|-------------|
| [Project Structure](program/docs/reference/PROJECT_STRUCTURE.md) | Full directory tree (all 5 systems) |
| [Deployment Guide](program/docs/operations/DEPLOYMENT.md) | Docker, nginx, production deployment |
| [Troubleshooting](program/docs/operations/TROUBLESHOOTING.md) | Common issues and solutions |
| [Module Guides](program/docs/reference/MODULE_GUIDES.md) | Per-module user guides (20+) |
| [Docs Index](program/docs/README.md) | Central documentation index |
| [Appendices](program/docs/reference/appendices.md) | Supplementary reference material |

### Architecture Decision Records

All 12 ADRs are listed in [program/docs/adr/README.md](program/docs/adr/README.md).

### Shared Infrastructure Docs

| Document | Description |
|----------|-------------|
| [Authentication](program/docs/shared/AUTHENTICATION.md) | Unified auth system (bcrypt, sessions, RBAC) |
| [MFA Guide](program/docs/shared/MFA_GUIDE.md) | Multi-factor authentication setup |
| [Universal Login](program/docs/shared/UNIVERSAL_LOGIN.md) | Cross-system login flow |
| [Infrastructure](program/docs/shared/INFRASTRUCTURE.md) | Shared infrastructure overview |

### Changelogs

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Current changelog (v9.x) |
| [Legacy Notes](program/docs/changelogs/CHANGELOG-legacy-notes.md) | Historical development notes |
| [Module Changelog](program/docs/changelogs/CHANGELOG-modules.md) | Per-module change history |
| [v5 Changelog](program/docs/changelogs/CHANGELOG-v5.md) | Version 5.x changelog |

### Performance & Testing

| Document | Description |
|----------|-------------|
| [Performance Testing](education_system/shared/tests/performance/README.md) | Load testing with Locust, SQLite benchmarks |

---

### Per-System Documentation

Each subsystem has its own docs index covering setup, security, infrastructure, and per-domain user guides:

| System | Docs Index |
|--------|------------|
| University | [program/docs/university_system/README.md](program/docs/university_system/README.md) |
| Sixth Form College | [program/docs/college_system/README.md](program/docs/college_system/README.md) |
| Secondary School | [program/docs/secondary_school/README.md](program/docs/secondary_school/README.md) |
| Primary School | [program/docs/primary_school/README.md](program/docs/primary_school/README.md) |
| Nursery / Early Years | [program/docs/nursery_system/README.md](program/docs/nursery_system/README.md) |

---

## What's New

**9.x highlights:**
- **Nursery / Early Years system** added (EYFS, Ofsted, funded hours, ratios, safeguarding) — 9.0.0.
- **University domain reorganised** into top-level categories (academics, admissions, analytics, campus, commerce, finance, health, operations, student_affairs) with cross-system integration — 9.0.0.
- **CLI ↔ GUI parity pass** across the University system: real Facilities/Admissions CLIs, gym check-out, event creation, and CLIs for compliance/case-management, finance, health, academics, and commerce modules — 9.3.0.
- **Schema-drift fixes** — corrected table-name collisions, bad `NOT NULL` constraints, missing columns, and empty-DB seed-ordering crashes in the Staff HR schemas — 9.3.0.

See [CHANGELOG.md](CHANGELOG.md) for the full release history (latest **9.7.0**). Earlier versions are in [program/docs/changelogs/CHANGELOG-v5.md](program/docs/changelogs/CHANGELOG-v5.md).

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

- **Documentation**: [Docs Index](program/docs/university_system/README.md)
- **Issues**: [GitHub Issues](https://github.com/sean1352636/university_system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sean1352636/university_system/discussions)

---

**Made with dedication for educational institutions worldwide — from primary schools to universities.**
