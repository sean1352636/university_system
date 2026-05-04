# Education System

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![codecov](https://codecov.io/gh/sean1352636/university_system/branch/main/graph/badge.svg)](https://codecov.io/gh/sean1352636/university_system)

A comprehensive, enterprise-grade education management platform spanning four distinct systems — **University**, **Sixth Form College**, **Secondary School**, and **Primary School** — with CLI, GUI, REST API, and Web Portal interfaces, shared authentication, and a unified launcher.

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
python run.py --university --gui    # University GUI
python run.py --college --gui       # Sixth Form College GUI
python run.py --school --gui        # Secondary School GUI
python run.py --primary --gui       # Primary School GUI
python run.py --college --api       # Unified REST API server

# Common operations
make test                  # Run all tests
make format                # Format code
make lint                  # Check code quality
```

> **Warning**
> Default login: `admin` / `admin123` — change immediately in production. See [Default Accounts](docs/reference/DEFAULT_ACCOUNTS.md) for the full list of pre-configured users across all four systems.

---

## Systems Overview

| System | Files | Modules | Interfaces | Focus |
|--------|-------|---------|------------|-------|
| **University** | 3,458+ | 16 domain categories (85+ sub-modules) | CLI, GUI, REST API, Web Portal | Higher education — academics, finance, health, housing, commerce, HR, student success, campus services |
| **Sixth Form College** | 1,020+ | 112 domains | CLI, GUI, REST API | FE college (16-19) — apprenticeships, T-levels, UCAS, safeguarding, GDPR, quality assurance |
| **Secondary School** | 590+ | 50 domains | CLI, GUI, REST API, Web Dashboard | Years 7-11 — KS3/KS4, GCSE grades 9-1, pastoral care, behaviour, form groups |
| **Primary School** | 670+ | 46 domains | CLI, GUI, REST API, Web Dashboard | Reception-Year 6 — EYFS/KS1/KS2, phonics, reading records, SATs |

**Combined:** 6,530+ Python files, 300+ domain modules, 319 REST API routes, 740+ test files. University domain directory reorganised into 15 top-level categories in v8.77.0 (April 2026).

All four systems share:
- **Unified launcher** (`run.py`) with CLI & GUI system selection
- **Shared authentication** (`shared/auth/`) — bcrypt, MFA (TOTP), sessions, central `auth.db`
- **Unified REST API** (`shared/api/unified_server.py`) — all 4 systems on one server
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
├── university_system/       # University (3,458+ files, 16 domain categories)
├── college_system/          # Sixth Form College (1,020+ files, 112 domains)
├── secondary_school/        # Secondary School (590+ files, 50 domains)
├── primary_school/          # Primary School (670+ files, 46 domains)
├── shared/                  # Shared modules across all 4 systems
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
└── switch.py                # Runtime system/mode switching

run.py                       # Unified launcher
Makefile                     # Development commands (30+ targets)
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

# Install dependencies
pip install -r requirements.txt

# (Optional) Development tools
pip install -e ".[dev]"

# (Optional) AI/ML features
pip install -e ".[ai]"

# (Optional) Cloud integration (AWS/Azure/GCP)
pip install -e ".[cloud]"
```

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
| `http://localhost:5000/api/v1/{system}/...` | Per-system endpoints (university/college/school/primary) |

The API is accessible from other devices on the network. Configure `API_HOST` and `API_PORT` env vars as needed.

#### Web Portal Features

- JWT-authenticated login with MFA support
- **Superadmin dashboard** — cross-system overview (health, users, analytics, notifications, student search, journey, permissions, backup, batch ops, live sessions)
- **Per-system dashboards** — live statistics, CRUD for students/courses/grades/attendance
- **Live session monitoring** — real-time view of logged-in users with force-logout capability
- **Admin session management** — force-logout any user; they're kicked out within 5 seconds
- Responsive design (desktop, tablet, mobile)

### Default Accounts

See [docs/reference/DEFAULT_ACCOUNTS.md](docs/reference/DEFAULT_ACCOUNTS.md) for pre-seeded dev credentials across all four systems. Change every password before any non-development deployment.

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
| [CHANGELOG.md](CHANGELOG.md) | Complete v8.x version history (178 releases, latest 8.104.0 on 2026-04-28) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute, branch naming, commit format |
| [SECURITY.md](SECURITY.md) | Security features, practices, and vulnerability reporting |
| [ROADMAP.md](docs/operations/ROADMAP.md) | Future plans and known limitations |
| [.env.example](.env.example) | Environment variable reference |

### Project-Wide Docs

| Document | Description |
|----------|-------------|
| [Project Structure](docs/reference/PROJECT_STRUCTURE.md) | Full directory tree (all 4 systems) |
| [Deployment Guide](docs/operations/DEPLOYMENT.md) | Docker, nginx, production deployment |
| [Troubleshooting](docs/operations/TROUBLESHOOTING.md) | Common issues and solutions |
| [Module Guides](docs/reference/MODULE_GUIDES.md) | Per-module user guides (20+) |
| [Docs Index](docs/README.md) | Central documentation index |
| [Appendices](docs/reference/appendices.md) | Supplementary reference material |

### Architecture Decision Records

All 12 ADRs are listed in [docs/adr/README.md](docs/adr/README.md).

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
| [CHANGELOG.md](CHANGELOG.md) | Current changelog (v8.x) |
| [Legacy Notes](docs/changelogs/CHANGELOG-legacy-notes.md) | Historical development notes |
| [Module Changelog](docs/changelogs/CHANGELOG-modules.md) | Per-module change history |
| [v5 Changelog](docs/changelogs/CHANGELOG-v5.md) | Version 5.x changelog |

### Performance & Testing

| Document | Description |
|----------|-------------|
| [Performance Testing](education_system/shared/tests/performance/README.md) | Load testing with Locust, SQLite benchmarks |

---

### Per-System Documentation

Each subsystem has its own docs index covering setup, security, infrastructure, and per-domain user guides:

| System | Docs Index |
|--------|------------|
| University | [docs/university_system/README.md](docs/university_system/README.md) |
| Sixth Form College | [docs/college_system/README.md](docs/college_system/README.md) |
| Secondary School | [docs/secondary_school/README.md](docs/secondary_school/README.md) |
| Primary School | [docs/primary_school/README.md](docs/primary_school/README.md) |

---

## What's New

See [CHANGELOG.md](CHANGELOG.md) for the full v8.x release history. Earlier versions are in [docs/changelogs/CHANGELOG-v5.md](docs/changelogs/CHANGELOG-v5.md).

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

- **Documentation**: [Docs Index](docs/university_system/README.md)
- **Issues**: [GitHub Issues](https://github.com/sean1352636/university_system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sean1352636/university_system/discussions)

---

**Made with dedication for educational institutions worldwide — from primary schools to universities.**
