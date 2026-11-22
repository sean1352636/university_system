# Education System

The `education_system` package is the top-level Python package for the Education System platform — an enterprise education management system covering the full UK pipeline from early years through Higher Education. Seven systems sit on top of a single shared platform layer (auth, API hosting, GDPR, audit, cross-system transfers), so a learner can be tracked, transferred, and reported on across institution boundaries without duplicating accounts or schemas.

> **Repository note.** The repo is historically named `university_system`; the project is **Education System**. The University is one of seven systems under `systems/`, and by far the largest.

---

## Systems

| Package | Stage | Coverage |
|---|---|---|
| [`systems/nursery/`](nursery/README.md) | Early years (0-5, EYFS) | EYFS, funded hours, ratios, safeguarding, daily diary |
| [`systems/primary/`](primary/README.md) | Reception – Year 6 (EYFS / KS1 / KS2) | Phonics, SATs, attendance, safeguarding |
| [`systems/secondary/`](secondary/README.md) | Years 7-11 (KS3 / KS4) | GCSE, pastoral care, behaviour, parents' evening |
| [`systems/sixth_form/`](sixth_form/README.md) | Sixth Form (16-19) | A-levels, T-levels, UCAS, safeguarding |
| [`systems/fe_college/`](fe_college/college_system.md) | Further Education (16+ and adult) | Vocational qualifications: BTEC, T-Level, NVQ, Access to HE, Functional Skills |
| [`systems/apprenticeships/`](apprenticeships/apprenticeship_system.md) | Post-16 apprenticeships | Five roles, off-the-job hours, portfolio, gateway, end-point assessment |
| [`systems/university/`](university/README.md) | Higher Education | Undergrad / postgrad, research, accommodation, alumni |
| [`platform/`](platform/README.md) | Cross-system | Auth, API hosting, GDPR, audit, webhooks, offline sync, i18n, transfers |
| `api/` | Cross-system | HTTP routes for all seven systems |

Each system ships its own CLI and GUI (Tkinter). All seven share a single `auth.db` and a unified API server.

---

## Quick start

```bash
# Install dependencies (Python 3.11+)
make install

# Interactive launcher
python -m education_system

# Direct launch — system + interface
python -m education_system --university --gui
python -m education_system --college --gui
python -m education_system --secondary --cli
python -m education_system --primary --gui
python -m education_system --nursery --gui
python -m education_system --fecollege --gui
python -m education_system --apprenticeships --gui
python -m education_system --api                    # Unified REST API
python -m education_system --university --web       # Static HTML UI where available
```

Default dev superadmin (only with `EDU_DEV_SEED=true`): `superadmin` / `SuperAdmin@123`.

---

## Directory layout

```
education_system/
├── __init__.py
├── __main__.py                 # python -m education_system
├── paths.py                    # Every filesystem path
├── switch.py                   # Cross-system switching (no re-auth)
├── alembic.ini
├── api/                        # HTTP routes, one package per system
├── launcher/                   # Unified launcher: auth, dispatch, menus, roles
├── migrations/                 # Alembic migrations
├── platform/                   # Shared cross-system platform (see below)
└── systems/
    ├── nursery/                # Early years
    ├── primary/                # EYFS/KS1/KS2
    ├── secondary/              # KS3/KS4
    ├── sixth_form/             # 16-19
    ├── fe_college/             # Further education
    ├── apprenticeships/        # Apprenticeships
    └── university/             # HE
```

The school systems share a consistent layered structure:

```
systems/<system>/
├── manifest.py          # Key, display name and interfaces
├── assets/              # Static and template assets, when present
├── domain/              # Domain modules (academics, finance, pastoral, …)
├── infrastructure/      # Persistence and external adapters
└── interfaces/
    ├── cli/
    └── gui/
```

The University is split into `domains/<slice>/`, `shell/`, `plugins/`, `application/`, `infrastructure/`, `services/` and `shared/`. See [PROJECT_STRUCTURE.md](reference/PROJECT_STRUCTURE.md) for the differences by system. Tests are at the repository root in `tests/`.

---

## Shared platform (`platform/`)

The platform layer is what makes the seven systems cohere as one platform. Highlights:

| Area | Modules |
|---|---|
| **Identity & access** | `identity/auth/` (bcrypt, TOTP MFA, sessions), `governance/security/` |
| **API surface** | `delivery/api/` (hosting and mount table for the blueprints in `education_system/api/`, served from one process) |
| **Compliance** | `governance/gdpr/`, `governance/audit/`, `governance/academic_misconduct/`, `governance/safeguarding/` |
| **Cross-system** | `cross_system/` (identity, transitions, handover, learner 360, adapters) |
| **Data & docs** | `kernel/database/`, `kernel/seeding/`, `features/documents/`, `features/transcript/`, `features/certificates/`, `identity/student_id/` |
| **Comms** | `integrations/email/`, `features/messaging/`, `features/notifications/`, `integrations/webhooks/` |
| **Ops** | `kernel/backup/`, `features/offline/` (sync), `features/analytics/`, `features/reporting/` |
| **Platform** | `features/i18n/`, `integrations/external/` (LMS), `assets/templates/`, `features/extras/` |

A single `auth.db` backs all seven systems; per-system records live in their own SQLite databases (WAL mode).

---

## Testing

```bash
make test                # Default suite (parallel, excludes slow/gui)
make test-all            # Including slow/integration
make test-university     # Single system
make test-shared         # Platform tests only
make test-auth           # Auth infrastructure
```

Run a single test:

```bash
pytest tests/unit/platform/identity/auth/test_auth_core.py -v --timeout=60
```

`pytest-xdist` runs in parallel by default (`-n auto --dist worksteal`). `tests/conftest.py` suppresses background daemon threads (maintenance scheduler, log processor, etc.) that otherwise hang CI.

---

## Tooling

```bash
make lint               # ruff check
make lint-fix           # ruff check --fix
make format             # ruff format
make type-check         # mypy (strict on platform/ and each system's auth, database and validation infrastructure)
make security-scan      # bandit
make ci                 # clean + lint + test-cov + security-scan + supply-chain-check
```

Linter targets Python 3.11, line length 100. Type checking is strict on infrastructure modules and permissive on `domain/` and `services/` to keep iteration fast.

---

## Cross-system features

- **`switch.py`** — switch between systems mid-session without logging out.
- **Unified API** — `src/education_system/platform/delivery/api/unified_server.py` mounts all seven systems on one Flask server, using the mount table in `platform/delivery/api/registry.py`.
- **Transfers** — `platform/cross_system/transitions.py` moves a learner between systems through a tracked workflow; the handover follows them.
- **Parent links** — one parent account can link to children across systems (`platform/services/parent_child_link.py`, `parent_overview.py`).
- **Learner 360** — one view of a learner's record across all seven systems (`platform/cross_system/learner_360.py`).
- **GDPR** — subject access, erasure, and consent audit are centralised in `platform/governance/gdpr/`, not per-system.

---

## Documentation

- [`docs/README.md`](README.md) — central documentation index
- Each system has its own folder under `docs/`, covering stage-specific features
- [`docs/platform/README.md`](platform/README.md) — the shared platform layer
