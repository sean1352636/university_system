# Education System

The `education_system` package is the top-level Python package for the Education System platform — an enterprise education management system covering the full UK pipeline from Reception through Higher Education. Four independent subsystems sit on top of a single shared infrastructure layer (auth, API, GDPR, audit, data portability), so a learner can be tracked, transferred, and reported on across institution boundaries without duplicating accounts or schemas.

> **Repository note.** The repo is historically named `university_system`; the project is **Education System**. The `university_system/` package below is one of four equal subsystems.

---

## Subsystems

| Package | Stage | Coverage |
|---|---|---|
| [`university_system/`](university_system/README.md) | Higher Education | Undergrad / postgrad, research, accommodation, alumni |
| [`sixthform_system/`](sixthform_system/) | Further Education (16-19) | Sixth Form: A-levels, T-levels, apprenticeships, UCAS, safeguarding |
| [`secondarysch_system/`](secondarysch_system/) | Years 7-11 (KS3 / KS4) | GCSE, pastoral care, behaviour, parents' evening |
| [`primarysch_system/`](primarysch_system/) | Reception – Year 6 (EYFS / KS1 / KS2) | Phonics, SATs, attendance, safeguarding |
| [`shared/`](shared/README.md) | Cross-system | Auth, REST API, GDPR, audit, webhooks, offline sync, i18n, transfers |

Each subsystem ships its own CLI and GUI (Tkinter). All four share a single `auth.db` and a unified API server.

---

## Quick start

```bash
# Install dependencies (Python 3.11+)
pip install -r ../requirements.txt

# Interactive launcher
python ../run.py

# Direct launch — system + interface
python ../run.py --university --gui
python ../run.py --college --gui
python ../run.py --secondary --cli
python ../run.py --primary --gui
python ../run.py --api                    # Unified REST API
python ../run.py --university --web       # Static HTML UI where available
```

Default dev superadmin: `superadmin` / `SuperAdmin@123`.

---

## Directory layout

```
education_system/
├── __init__.py
├── switch.py                   # Cross-system switching (no re-auth)
├── README.md
├── launcher/                   # Unified launcher: auth, dispatch, menus, roles
├── shared/                     # 45+ cross-system modules (see below)
├── university_system/          # HE
├── sixthform_system/           # FE 16-19
├── secondarysch_system/        # KS3/KS4
├── primarysch_system/          # EYFS/KS1/KS2
└── data/                       # Shared seed data
```

Each subsystem follows a consistent 4-layer DDD structure:

```
<subsystem>/
├── modules/
│   ├── domain/          # Domain modules (academics, finance, housing, …)
│   ├── core/            # Subsystem-wide utilities
│   ├── shared/          # Subsystem-local shared (CLI/GUI entry points)
│   └── services/        # Cross-cutting services
├── infrastructure/      # DB, email, validation
└── tests/               # cli/, gui/, integration/
```

---

## Shared infrastructure (`shared/`)

The shared layer is what makes the four systems cohere as one platform. Highlights:

| Area | Modules |
|---|---|
| **Identity & access** | `auth/` (bcrypt, TOTP MFA, sessions, JWT), `security/` |
| **API surface** | `api/` (Flask blueprints per system, served from one process) |
| **Compliance** | `gdpr/`, `audit/`, `academic_misconduct/`, `safeguarding` modules |
| **Cross-system** | `bulk_transfer/`, `transfer/`, `transfer_docs/`, `reverse_lookup/`, `parent_continuity/`, `cross_system/` |
| **Data & docs** | `database/`, `migrations/`, `seeding/`, `documents/`, `transcript/`, `certificates/`, `student_id/` |
| **Comms** | `email/`, `messaging/`, `notifications/`, `webhooks/` |
| **Ops** | `backup/`, `offline/` (sync), `analytics/`, `reporting/`, `predictive/`, `outcomes/` |
| **Platform** | `i18n/`, `integrations/`, `lms/`, `templates/`, `extras/` |

A single `auth.db` backs all four systems; per-system records live in their own SQLite databases (WAL mode).

---

## Testing

```bash
make test                # Default suite (parallel, excludes slow/gui)
make test-all            # Including slow/integration
make test-university     # Single subsystem
make test-shared         # shared/ tests only
make test-auth           # Auth infrastructure
```

Run a single test:

```bash
~/venv/bin/pytest education_system/shared/tests/test_auth_core.py -v --timeout=60
```

`pytest-xdist` runs in parallel by default (`-n auto --dist worksteal`). The root `conftest.py` suppresses background daemon threads (maintenance scheduler, log processor, etc.) that otherwise hang CI.

---

## Tooling

```bash
make lint               # ruff check
make lint-fix           # ruff check --fix
make format             # ruff format
make type-check         # mypy (strict on shared/, core/, auth/, database/, validation/)
make security-scan      # bandit
make ci                 # clean + lint + test-cov + security-scan
```

Linter targets Python 3.11, line length 100. Type checking is strict on infrastructure modules and permissive on `domain/` and `services/` to keep iteration fast.

---

## Cross-system features

- **`switch.py`** — switch between subsystems mid-session without logging out.
- **Unified API** — `shared/api/unified_server.py` mounts all four systems on one Flask server with per-system blueprints.
- **Bulk transfer** — promote a Year 6 cohort to Year 7, or a Year 11 cohort into Sixth Form, in one operation; transfer documents follow.
- **Parent continuity** — one parent account spans every child across every system.
- **Reverse lookup** — find a learner by name across all four systems at once.
- **GDPR portal** — subject access, erasure, and consent audit are centralised, not per-system.

---

## Documentation

- `docs/` (per-subsystem) — design notes, schema diagrams, runbooks
- Each subsystem's own `README.md` covers stage-specific features
- `shared/README.md` — deep dive on the shared infrastructure layer
