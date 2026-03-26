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
> Default login: `superadmin` / `SuperAdmin@123` — change immediately in production! See the [default accounts table](#default-accounts) for all 18 pre-configured users.

---

## Systems Overview

| System | Files | Modules | Interfaces | Focus |
|--------|-------|---------|------------|-------|
| **University** | 3,420+ | 51 domains | CLI, GUI, REST API, Web Portal | Higher education — academics, finance, health, housing, commerce, HR, student success (23 modules) |
| **Sixth Form College** | 930+ | 112 domains | CLI, GUI, REST API | FE college (16-19) — apprenticeships, T-levels, UCAS, safeguarding, GDPR, quality assurance |
| **Secondary School** | 290+ | 50 domains | CLI, GUI, REST API, Web Dashboard | Years 7-11 — KS3/KS4, GCSE grades 9-1, pastoral care, behaviour, form groups |
| **Primary School** | 280+ | 46 domains | CLI, GUI, REST API, Web Dashboard | Reception-Year 6 — EYFS/KS1/KS2, phonics, reading records, SATs |

**Combined:** 5,169+ Python files, 257 domain modules, 319 REST API routes, 448+ test files.

All four systems share:
- **Unified launcher** (`run.py`) with CLI & GUI system selection
- **Shared authentication** (`shared/auth/`) — bcrypt, MFA (TOTP), sessions, central `auth.db`
- **Unified REST API** (`shared/api/unified_server.py`) — all 4 systems on one server
- **Web Portal** — browser-based SPA with superadmin dashboard, per-system dashboards, live session monitoring
- **Cross-system switching** without re-authentication

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

### High-Level Structure

```
education_system/
├── university_system/       # University (3,420+ files, 51 domains)
├── college_system/          # Sixth Form College (930+ files, 112 domains)
├── secondary_school/        # Secondary School (290+ files, 50 domains)
├── primary_school/          # Primary School (280+ files, 46 domains)
├── shared/                  # Shared modules across all 4 systems
│   ├── api/                 # Unified REST API (unified_server.py + per-system routes)
│   │   └── web/             # Web Portal SPA (HTML/CSS/JS)
│   ├── auth/                # Unified authentication (bcrypt, MFA, sessions)
│   ├── gui/                 # Universal login window & superadmin dashboard
│   ├── extras/              # Shared tools (calculator, query builder, etc.)
│   └── data/                # Central auth.db, config, locales (13 languages)
├── docs/                    # Centralised documentation (150+ files)
└── switch.py                # Runtime system/mode switching

run.py                       # Unified launcher
Makefile                     # Development commands (30+ targets)
```

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for the full directory tree.

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

| Username | Password | Systems | Role |
|----------|----------|---------|------|
| `superadmin` | `SuperAdmin@123` | All 4 | Admin (all systems) |
| `admin` | `Admin@University123` | University | Admin |
| `staff` | `Staff@University123` | University | Staff |
| `student` | `Student@University123` | University | Student |
| `collegeadmin` | `Admin@College123` | College | Admin |
| `schooladmin` | `Admin@School123` | Secondary | Admin |
| `primaryadmin` | `Admin@Primary123` | Primary | Admin |

Plus per-system staff/student/parent accounts following the pattern `<Role>@<System>123`.

### Makefile Targets

```bash
make help              # Show all available targets
make install           # Install production dependencies
make install-dev       # Install dev dependencies
make run               # Interactive launcher
make run-gui           # Launch GUI mode
make run-api           # Start API server
make test              # Run all tests
make test-cov          # Tests with coverage report
make test-university   # University tests only
make test-college      # College tests only
make lint              # Lint code (Ruff)
make format            # Format code (Black + isort)
make type-check        # Run mypy
make check             # Lint + tests
make security-scan     # Bandit security scan
make seed              # Seed databases with demo data
make clean             # Remove cache and build artifacts
make docker-build      # Build Docker image
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

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Complete version history (340+ releases) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute, branch naming, commit format |
| [SECURITY.md](SECURITY.md) | Security features, practices, and vulnerability reporting |
| [ROADMAP.md](ROADMAP.md) | Future plans and known limitations |
| [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | Full directory tree (all 4 systems) |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, nginx, production deployment |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [docs/MODULE_GUIDES.md](docs/MODULE_GUIDES.md) | Per-module user guides (20+) |
| [docs/adr/README.md](docs/adr/README.md) | Architecture Decision Records (ADRs) — 12 decisions |
| [.env.example](.env.example) | Environment variable reference |

### System-Specific Docs

- [University Docs](education_system/docs/university_system/README.md) — 60+ guides (security, infrastructure, development, AI, user guides)
- [College Docs](education_system/docs/college_system/)
- [Secondary School Docs](education_system/docs/secondary_school/)
- [Primary School Docs](education_system/docs/primary_school/)

---

## What's New

### Version 8.43.0 (March 24, 2026) — Latest

- **API login and routing fixes** — fixed web login, dashboard 404s, Swagger UI blank page
- **Network access** — API binds to `0.0.0.0` by default; accessible from other devices
- **Live session monitoring** — admin dashboard auto-refreshes every 5s with force-logout
- **Real-time force logout** — kicked users are redirected to login within 5 seconds

### Version 8.41.0 (March 24, 2026)

- **API improvements** — request validation, per-user rate limiting, caching middleware, API keys, content negotiation, request size limits

### Version 8.40.0 (March 24, 2026)

- **API versioning** (`/api/v1/`), OpenAPI/Swagger UI, deduplicated shared API modules, University Flask migration

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

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

- **Documentation**: [Docs Index](education_system/docs/university_system/README.md)
- **Issues**: [GitHub Issues](https://github.com/sean1352636/university_system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sean1352636/university_system/discussions)

---

**Made with dedication for educational institutions worldwide — from primary schools to universities.**
