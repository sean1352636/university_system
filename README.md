# Education System

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![codecov](https://codecov.io/gh/sean1352636/university_system/branch/main/graph/badge.svg)](https://codecov.io/gh/sean1352636/university_system)

A comprehensive, feature-rich education management platform spanning seven distinct systems — **Nursery**, **Primary School**, **Secondary School**, **Sixth Form College**, **FE College**, **Apprenticeships**, and **University** — with CLI, GUI, REST API, and Web Portal interfaces, shared authentication, and a unified launcher.

> **Project status:** Feature-complete for demonstration and development use, but **not recommended for production** without first implementing the outstanding [security recommendations](SECURITY.md). See the [Roadmap](docs/operations/ROADMAP.md) for known limitations.

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
make install                # from requirements.lock (make install-dev for tooling)
pip install -e . --no-deps  # make education_system importable (or use: python run.py)

# Run the unified launcher (interactive system & mode selection)
python -m education_system

# Or specify system and mode directly
python -m education_system --university --gui   # University GUI
python -m education_system --college --gui      # Sixth Form College GUI (--sixthform alias)
python -m education_system --secondary --gui    # Secondary School GUI (--school alias)
python -m education_system --primary --gui      # Primary School GUI
python -m education_system --nursery --gui      # Nursery / Early Years GUI
python -m education_system --fecollege --gui    # FE College GUI (--fe-college alias)
python -m education_system --apprenticeships --gui  # Apprenticeships GUI (--apprenticeship alias)
python -m education_system --university --api   # Unified REST API server

# Installing the project also provides an `education-system` console script.

# Common operations
make test                  # Run all tests
make format                # Format code
make lint                  # Check code quality
```

> **Warning**
> Dev login `admin` / `admin123` is created **only** with `EDU_DEV_SEED=true` (fine for local/demo use, never for production). A fresh production database is left empty — bootstrap it with `EDU_INITIAL_ADMIN_USER` / `EDU_INITIAL_ADMIN_PASSWORD` instead. See [Default Accounts](docs/reference/DEFAULT_ACCOUNTS.md) for the full list of pre-configured users across all seven systems.

---

## Systems Overview

| System | Python files | Interfaces | Focus |
|--------|--------------|------------|-------|
| **Nursery** | 771 | CLI, GUI, REST API | Early years (0-5) — EYFS, Ofsted, funded hours, ratios/occupancy, safeguarding (DSL/Prevent), learning journeys, 2-year progress checks, daily diary |
| **Primary School** | 839 | CLI, GUI, REST API | Reception-Year 6 — EYFS/KS1/KS2, phonics, reading records, SATs |
| **Secondary School** | 858 | CLI, GUI, REST API | Years 7-11 — KS3/KS4, GCSE grades 9-1, pastoral care, behaviour, form groups |
| **Sixth Form College** | 1,472 | CLI, GUI, REST API | Sixth form (16-19) — A-levels, T-levels, UCAS, safeguarding, GDPR, quality assurance |
| **FE College** | 165 | CLI, GUI, REST API (main-menu routes only, answering 501 until backed by a service) | Further education (16+ and adult) — vocational qualifications (BTEC, T-Level, NVQ, Access to HE, Functional Skills) |
| **Apprenticeships** | 250 | CLI, GUI, REST API (main-menu routes only, answering 501 until backed by a service) | Five roles (admin, tutor, apprentice, employer, end-point assessor) — off-the-job hours, portfolio, gateway, EPA, funding |
| **University** | 5,738 | CLI, GUI, REST API, Web | Higher education — 18 domains (admissions, assessment, curriculum, finance, governance, health, integrity, learners, library, operations, progression, quality, research, safeguarding, staff, student life, student support, teaching) plus the campus commerce and community services plugins |

**Combined:** 11,435 Python files under `src/` (counted 2026-10-31): the seven systems above, plus 865 in `api/` (HTTP routes) and 382 in `platform/` (shared infrastructure).

All seven systems share:
- **Unified launcher** (`education_system/launcher/main.py`, run via `python -m education_system`) with CLI & GUI system selection
- **Shared authentication** (`src/education_system/platform/identity/auth/`) — bcrypt, MFA (TOTP), sessions, central `auth.db`
- **Unified REST API** (`src/education_system/platform/delivery/api/unified_server.py`) — all systems on one server
- **Web Portal** — browser-based SPA with superadmin dashboard, per-system dashboards, live session monitoring
- **Cross-system switching** without re-authentication
- **GDPR compliance** (`src/education_system/platform/governance/gdpr/`) — consent tracking, data subject rights, data retention, portability
- **Unified audit logging** (`src/education_system/platform/governance/audit/`) — cross-system tamper-detected audit trail
- **Webhook system** (`src/education_system/platform/integrations/webhooks/`) — event dispatch with HMAC signatures and retry
- **Offline sync** (`src/education_system/platform/features/offline/`) — local cache, mutation queue, conflict detection

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
| **Database** | SQLite (WAL mode) |
| **Auth** | bcrypt, PyJWT, pyotp (TOTP), WebAuthn, SSO (SAML/OIDC) |
| **Data** | pandas, numpy, matplotlib, seaborn, plotly, scikit-learn |
| **Docs** | reportlab, openpyxl, fpdf2 |
| **Testing** | pytest, pytest-cov, pytest-xdist |
| **Quality** | Ruff, mypy, bandit |
| **Real-time** | Socket.IO (WebSocket), GraphQL (Strawberry) |
| **Security** | Fernet encryption, HMAC signatures, ClamAV virus scanning |
| **Integrations** | Canvas, Moodle, Google Classroom, Microsoft Teams |

### High-Level Structure

```
src/
├── education_system/
│   ├── api/                 # HTTP route blueprints, one package per system
│   ├── platform/            # Cross-cutting infrastructure shared by all seven systems
│   │   ├── identity/        # Unified authentication (bcrypt, TOTP MFA, sessions, auth.db)
│   │   ├── delivery/        # Interface delivery layer
│   │   │   ├── api/         # Unified REST API hosting (unified_server.py, registry.py mount table)
│   │   │   ├── cli/         # Shared CLI shell
│   │   │   ├── gui/         # Universal login window & superadmin dashboard
│   │   │   ├── portals/     # Role portals
│   │   │   └── web/         # Web Portal SPA (HTML/CSS/JS)
│   │   ├── kernel/          # Core primitives: base, core, database, validation, seeding, backup
│   │   ├── governance/      # Audit, GDPR, safeguarding, security, academic misconduct
│   │   ├── integrations/    # Email, webhooks, LMS (Canvas, Moodle, Teams)
│   │   ├── features/        # Analytics, calendar, documents, certificates, offline sync, extras
│   │   ├── cross_system/    # Cross-system progression transfers
│   │   ├── services/        # Chat, data retention, parent link, notifications
│   │   └── testing/         # Shared test helpers
│   ├── systems/             # The seven education systems
│   │   ├── nursery/         # Nursery / Early Years (0-5, EYFS)
│   │   ├── primary/         # Primary School (Reception-Year 6)
│   │   ├── secondary/       # Secondary School (Years 7-11)
│   │   ├── sixth_form/      # Sixth Form College (16-19)
│   │   ├── fe_college/      # FE College
│   │   ├── apprenticeships/ # Apprenticeships (five roles; own database outside Alembic)
│   │   └── university/      # University (5,738 files, 18 domains)
│   ├── launcher/            # Unified launcher modules
│   ├── migrations/          # Alembic migration scripts
│   ├── paths.py             # Every filesystem path
│   ├── switch.py            # Runtime system/mode switching
│   └── __main__.py          # Unified launcher (python -m education_system)
tests/                       # Organised by scope, then by owner
docs/                        # Centralised documentation (243 files)
tools/
deploy/                      # docker-stack.yml, kubernetes/
docker/                      # Dockerfile, compose, nginx, monitoring config
remove/                      # Code awaiting deletion by hand
var/                         # Runtime data, logs, backups, secrets (never committed)

Makefile                     # Development commands
```

See [docs/reference/PROJECT_STRUCTURE.md](docs/reference/PROJECT_STRUCTURE.md) for the full directory tree.

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
make install                 # pinned/reproducible, from requirements.lock
pip install -e . --no-deps   # make education_system importable (or use: python run.py)
#   or:  pip install -e .    # minimum-range install from pyproject.toml
```

This runtime install covers all seven systems across CLI, GUI, REST API and web.
The scientific/reporting stack (numpy, pandas, scikit-learn, matplotlib, …) is
part of it because core academics and finance features depend on it.

#### Optional feature tiers (pip extras)

Install only what you need — none of these are required to run the app:

```bash
pip install -e ".[dev]"          # tests, ruff, mypy, black  (or: make install-dev)
pip install -e ".[desktop]"      # ttkthemes, tkcalendar, Pillow, qrcode for the GUIs
pip install -e ".[security]"     # bandit, safety, pip-audit, semgrep
pip install -e ".[perf]"         # locust load testing
pip install -e ".[ai]"           # torch / transformers / spaCy / OpenCV
pip install -e ".[realtime]"     # WebSocket / Socket.IO
pip install -e ".[postgres]"     # PostgreSQL batch export (".[mysql]" for MySQL)
pip install -e ".[cloud-aws]"    # AWS only (".[cloud-azure]", ".[cloud-gcp]", or ".[cloud]" for all)
pip install -e ".[integrations]" # Google Classroom LMS, Twilio SMS
pip install -e ".[remote]"       # SSH/SFTP (paramiko)
```

> Development/CI tooling is **not** in `requirements.lock`; it lives in
> `requirements-dev.lock` (equivalently the `dev`/`security`/`perf` extras) so
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
python -m education_system                       # Interactive menu
python -m education_system --university --gui    # Direct launch
python -m education_system --api                 # Start API server
```

### REST API & Web Portal

```bash
python -m education_system --api                 # Starts unified API on http://0.0.0.0:5000
```

| URL | Description |
|-----|-------------|
| `http://localhost:5000/web/login` | Web Portal (browser SPA) |
| `http://localhost:5000/api/v1/docs` | Swagger UI (interactive API docs) |
| `http://localhost:5000/api/v1/auth/login` | Auth endpoint (POST) |
| `http://localhost:5000/api/v1/health` | Health check |
| `http://localhost:5000/api/v1/{system}/...` | Per-system endpoints (`university`, `sixthform`, `school`, `primary`, `nursery`, `fecollege`, `apprentice`) |

The API is accessible from other devices on the network. Configure `API_HOST` and `API_PORT` env vars as needed.

#### Web Portal Features

- JWT-authenticated login with MFA support
- **Superadmin dashboard** — cross-system overview (health, users, analytics, notifications, student search, journey, permissions, backup, batch ops, live sessions)
- **Per-system dashboards** — live statistics, CRUD for students/courses/grades/attendance
- **Live session monitoring** — real-time view of logged-in users with force-logout capability
- **Admin session management** — force-logout any user; they're kicked out within 5 seconds
- Responsive design (desktop, tablet, mobile)

### Default Accounts

See [docs/reference/DEFAULT_ACCOUNTS.md](docs/reference/DEFAULT_ACCOUNTS.md) for pre-seeded dev credentials across all seven systems. Change every password before any non-development deployment.

> These demo accounts are flagged `must_change_password`, so the app forces a new password on first login and won't let the seeded password persist. Seeding runs **only** when `EDU_DEV_SEED=true` — a fresh database without the flag (the production default) is never populated with them. To provision a production admin, set `EDU_INITIAL_ADMIN_USER` / `EDU_INITIAL_ADMIN_PASSWORD` (≥12 chars) for a single strong account. The passwords are published here **only** because they're well-known dev defaults — treat any deployment that still accepts them as unconfigured.

### Makefile Targets

Run `make help` for the full list. Common ones:

```bash
make run               # Interactive launcher
make test              # Run all tests
make format            # Format (ruff format)
make lint              # Lint (Ruff)
make check             # Lint + tests
```

---

## Configuration

### Database

- **SQLite** — zero configuration, stored under `var/data/<system>/` (University: `var/data/university/db_files/student_records.db`; shared auth: `var/data/platform/db_files/auth.db`). See `src/education_system/paths.py`.
- **PostgreSQL** / **MySQL** — the `postgres` and `mysql` extras are used by the University's batch export to external databases; the application itself runs on SQLite.

Features: thread-safe connection pooling, WAL mode, ACID compliance, schema migrations, backup/restore.

### Authentication

- **bcrypt** password hashing (with transparent migration from legacy PBKDF2-SHA256)
- **MFA**: TOTP (Google Authenticator), Email OTP, SMS OTP, WebAuthn/FIDO2, Biometric, SSO (SAML 2.0 / OIDC)
- **Sessions**: DB-backed with configurable timeout (`EDU_SESSION_TIMEOUT`, default 30 min)
- **RBAC**: Fine-grained role-based access control
- **Password security**: history (reuse prevention), common password rejection, expiry enforcement, timing-attack protection
- **Password reset**: secure token-based flow (`POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password`)
- **Consent tracking**: 16 consent types with grant/withdraw/export (GDPR Article 7)
- **MFA enforcement**: admin/staff users prompted to set up MFA if not configured

---

## Development

```bash
make install-dev       # Install dev dependencies
make format            # Format code (ruff format, line-length 100)
make lint              # Lint (Ruff)
make type-check        # Type check (mypy)
make test              # Run all tests
make test-cov          # Tests with HTML coverage report
make check             # Lint + tests
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
| [ROADMAP.md](docs/operations/ROADMAP.md) | Future plans and known limitations |
| [.env.example](.env.example) | Environment variable reference |

### Project-Wide Docs

| Document | Description |
|----------|-------------|
| [Project Structure](docs/reference/PROJECT_STRUCTURE.md) | Full directory tree (all 7 systems) |
| [Deployment Guide](docs/operations/DEPLOYMENT.md) | Docker, nginx, production deployment |
| [Troubleshooting](docs/operations/TROUBLESHOOTING.md) | Common issues and solutions |
| [Module Guides](docs/reference/MODULE_GUIDES.md) | Per-module user guides (20+) |
| [Docs Index](docs/README.md) | Central documentation index |
| [Appendices](docs/reference/appendices.md) | Supplementary reference material |

### Architecture Decision Records

All 19 ADRs are listed in [docs/adr/README.md](docs/adr/README.md).

### Shared Infrastructure Docs

| Document | Description |
|----------|-------------|
| [Authentication](docs/shared/AUTHENTICATION.md) | Unified auth system (bcrypt, sessions, RBAC) |
| [MFA Guide](docs/shared/MFA_GUIDE.md) | Multi-factor authentication setup |
| [Universal Login](docs/shared/UNIVERSAL_LOGIN.md) | Cross-system login flow |
| [Infrastructure](docs/shared/INFRASTRUCTURE.md) | Shared infrastructure overview |

### Changelogs

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Current changelog (v9.x) |
| [Legacy Notes](docs/changelogs/CHANGELOG-legacy-notes.md) | Historical development notes |
| [Module Changelog](docs/changelogs/CHANGELOG-modules.md) | Per-module change history |
| [v5 Changelog](docs/changelogs/CHANGELOG-v5.md) | Version 5.x changelog |

### Performance & Testing

| Document | Description |
|----------|-------------|
| [Performance Testing](tests/performance/README.md) | Load testing with Locust, SQLite benchmarks |

---

### Per-System Documentation

Each subsystem has its own docs index covering setup, security, infrastructure, and per-domain user guides:

| System | Docs Index |
|--------|------------|
| University | [docs/university/README.md](docs/university/README.md) |
| Sixth Form College | [docs/sixth_form/README.md](docs/sixth_form/README.md) |
| Secondary School | [docs/secondary/README.md](docs/secondary/README.md) |
| Primary School | [docs/primary/README.md](docs/primary/README.md) |
| Nursery / Early Years | [docs/nursery/README.md](docs/nursery/README.md) |
| FE College | [docs/fe_college/college_system.md](docs/fe_college/college_system.md) |
| Apprenticeships | [docs/apprenticeships/apprenticeship_system.md](docs/apprenticeships/apprenticeship_system.md) |

---

## What's New

**9.x highlights:**
- **Nursery / Early Years system** added (EYFS, Ofsted, funded hours, ratios, safeguarding) — 9.0.0.
- **University domain reorganised** into top-level categories with cross-system integration — 9.0.0. It has since become the 18 vertical slices under `systems/university/domains/`.
- **CLI ↔ GUI parity pass** across the University system: real Facilities/Admissions CLIs, gym check-out, event creation, and CLIs for compliance/case-management, finance, health, academics, and commerce modules — 9.3.0.
- **Schema-drift fixes** — corrected table-name collisions, bad `NOT NULL` constraints, missing columns, and empty-DB seed-ordering crashes in the Staff HR schemas — 9.3.0.

See [CHANGELOG.md](CHANGELOG.md) for the full release history (latest **9.7.0**). Earlier versions are in [docs/changelogs/CHANGELOG-v5.md](docs/changelogs/CHANGELOG-v5.md).

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, including:

- Branch naming conventions (`feature/`, `bugfix/`, `docs/`)
- Commit message format (`feat:`, `fix:`, `docs:`)
- How to add a new domain module
- How to add another system (integration points)
- Code style, testing requirements, and PR process

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## Support

- **Documentation**: [Docs Index](docs/README.md)
- **Issues**: [GitHub Issues](https://github.com/sean1352636/university_system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sean1352636/university_system/discussions)

---

**Made with dedication for educational institutions worldwide — from primary schools to universities.**
