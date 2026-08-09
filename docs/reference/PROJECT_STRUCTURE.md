# Project Structure

> Back to [Documentation](../README.md)

This document describes the active ADR 0018 repository layout. Paths are
relative to the repository root. The installable package lives under `src/`;
`tests/`, `docs/`, `tools/` and `var/` are its siblings.

Counts were generated from the working tree on 2026-08-02 and exclude
`__pycache__` files. They will naturally change as modules are added or split.

## Repository overview

```text
<repo root>/
├── src/
│   └── education_system/          # Installable Python application (6,966 .py)
│       ├── __main__.py            # Unified launcher (python -m education_system)
│       ├── launcher/              # System selection and launch orchestration
│       ├── migrations/            # Alembic and feature-schema migrations
│       │   └── versions/
│       ├── platform/              # Shared cross-system platform (607 .py)
│       └── systems/               # Five independently usable systems
│           ├── nursery/           # Early Years / Nursery (388 .py)
│           ├── primary/           # Primary School (420 .py)
│           ├── secondary/         # Secondary School (433 .py)
│           ├── sixth_form/        # Sixth Form College (553 .py)
│           ├── university/        # University system (4,539 .py)
│           ├── fe_college/        # Incubating skeleton — stubs only, not wired in
│           └── apprenticeships/   # Apprenticeships (273 .py) — CLI and GUI live
├── tests/                         # Canonical test tree (734 .py)
│   ├── launcher/
│   ├── migrations/
│   ├── platform/
│   ├── systems/
│   └── tools/
├── tools/                         # Maintainer and architecture tools
│   ├── docs/
│   └── university/
├── docs/                          # Central documentation
│   ├── adr/
│   ├── api/
│   ├── operations/
│   ├── platform/
│   ├── reference/
│   └── {nursery,primary,secondary,sixth_form,university}/
├── var/                           # Runtime state; never application source
│   ├── backups/
│   ├── data/
│   ├── logs/
│   └── secrets/
└── run.py                         # Deprecated shim -> education_system.launcher.main
```

The tree currently contains 12,454 non-cache files,
including 7,729 Python source files. The public website's older 6,473 figure
predates the current modularisation work.

## Shared platform

`education_system/platform/` contains capabilities shared by more than one
education system. System-specific rules do not belong here.

```text
education_system/platform/
├── assets/                        # Shared templates and static assets
├── cross_system/                  # Enrolment, progression, handover, transitions
│   └── adapters/
├── delivery/                      # Shared interface delivery
│   ├── api/                       # Unified Flask APIs and web portal
│   ├── cli/                       # Superadmin and shared CLI delivery
│   ├── gui/                       # Shared administrative GUIs
│   └── portals/                   # Browser portal services
├── features/                      # Reusable product capabilities
│   ├── analytics/
│   ├── calendar/
│   ├── certificates/
│   ├── documents/
│   ├── i18n/
│   ├── lms/
│   ├── messaging/
│   ├── notifications/
│   ├── offline/
│   └── reporting/
├── governance/                    # Audit, GDPR, safeguarding and security
├── identity/                      # Authentication and identity services
├── integrations/                  # Email, webhooks and external systems
├── kernel/                        # Database, validation, backup and core ports
├── services/                      # Cross-cutting application services
└── testing/                       # Shared test support
```

`platform/delivery/api/` owns the shared API machinery — hosting, middleware,
router registration and common protocol support — and is system-agnostic. Each
system's own route blueprints live with that system, under
`systems/<system>/interfaces/api/routes/`, and `unified_server.py` registers
them. University API hosting (`api_server.py`, `core_api.py`, `auth.py`,
`pagination.py`, `validators.py`) and its static pages remain under
`platform/delivery/api/university/`.

## System layout

Each system follows the same broad ownership model:

```text
education_system/systems/<system>/
├── assets/                        # System-owned static/templates assets
├── domain/                        # Business rules and domain services
├── infrastructure/                # Persistence and external adapters
├── interfaces/                    # CLI and GUI delivery
└── data/                          # Packaged seed/reference data, when required
```

The university system additionally has explicit `application/`, `services/`
and `plugins/` boundaries because of its size.

`fe_college/` and `apprenticeships/` both arrived as docstring-stub skeletons
relocated from the `college_and_apprenticeships` starter project. They have
since diverged.

`apprenticeships/` is built: domain, services, repositories, a five-role CLI
and a five-role GUI, all reachable from the launcher (`--apprenticeships`) and
registered with shared auth and `paths`. It adds `services/`, plus `pathways/`
and `integrations/` — including a degree-apprenticeship university gateway — to
the shape above. Its own database is `var/data/apprenticeships/apprenticeships.db`,
built by `infrastructure/persistence/schema.py` rather than by Alembic. Two
interface trees are still scaffolding: `interfaces/api/` and
`interfaces/portals/` hold empty modules and nothing imports them, so this
system is absent from the unified API and the web portal. See
`docs/apprenticeships/` for the system, its roles and its rules.

`fe_college/` remains a skeleton: every module is a docstring stub, and it is
registered with nothing. Its placeholder docs are in `docs/fe_college/`.
Maintenance scripts for both live in `tools/college_and_apprenticeships/`.

Naming note: a `domain/**/assets/` package (primary, secondary and sixth form
each carry one) is the *fixed-asset register* business domain — equipment tags,
custodians, warranties — and holds Python code. It is unrelated to the static
`assets/` trees above. Likewise `university/domain/academics/services/assignments/templates/`
is the assignment-templates domain feature, not a static-template directory.

## University system

```text
education_system/systems/university/
├── application/                  # Use-case orchestration (23 .py)
│   ├── admissions.py
│   ├── assessment.py
│   ├── finance.py
│   ├── health/
│   ├── operations.py
│   ├── progression.py
│   ├── research.py
│   └── students.py
├── domain/                       # Business domains (1,283 .py)
│   ├── academics/                # Teaching, research and scheduling (392 .py)
│   ├── admissions/               # Applicant lifecycle and policy (17 .py)
│   ├── assessment/               # Boards, grading and progress (58 .py)
│   ├── finance/                  # Accounts, billing and reporting (77 .py)
│   ├── governance/               # Compliance and institutional policy (26 .py)
│   ├── learners/                 # Canonical student lifecycle (23 .py)
│   ├── operations/               # Campus and commerce operations (261 .py)
│   ├── pastoral/                 # Health and student life (354 .py)
│   ├── progression/              # Progression workflows (13 .py)
│   ├── safeguarding/             # Safeguarding domain (24 .py)
│   └── staff/                    # Staff-owned business rules (37 .py)
├── infrastructure/               # Technical adapters (516 .py)
│   ├── auth/                     # Modular auth façade and implementations
│   ├── database/                 # Connections, schemas and schema versions
│   ├── email/                    # University email adapters
│   ├── events.py                 # Event/outbox infrastructure
│   ├── health/                   # Health persistence adapters
│   ├── security/                 # Encryption and security adapters
│   ├── unit_of_work.py
│   └── utils/
├── interfaces/                   # User-facing delivery (2,543 .py)
│   ├── cli/                      # CLI shell and feature commands (466 .py)
│   └── gui/                      # Tkinter applications and components (2,076 .py)
├── services/                     # Cross-domain university services (169 .py)
│   ├── ai_features/
│   ├── analytics/
│   ├── bus/                      # Integration bus and jobs
│   ├── business_intelligence/
│   ├── communication/
│   ├── dashboard/
│   ├── events/
│   ├── integrations/
│   ├── boundary_errors.py
│   ├── degraded_states.py
│   ├── operational_health.py
│   └── operations.py
├── assets/                       # University web/static assets
└── plugins/                      # University extension points
```

### University interfaces

```text
interfaces/
├── cli/
│   ├── pastoral/                 # Health and student-life CLIs
│   └── shell/
│       ├── bootstrap/            # CLI startup and dependency wiring
│       ├── features/             # Feature command adapters
│       ├── menus/                # Menu routing and presentation
│       ├── routing/              # Command dispatch
│       └── services/             # Compatibility entry points and CLI services
└── gui/
    ├── academics/
    ├── admissions/
    ├── assessment/
    ├── finance/
    ├── operations/
    │   ├── campus/
    │   └── commerce/
    ├── pastoral/
    ├── shell/                    # Main window, search, reporting and utilities
    └── staff/
```

Large legacy entry points are retained as compatibility façades. Their
implementations are held in adjacent focused packages such as `tabs/`,
`services/`, named feature packages, or generated `*_parts/` packages with a
corresponding `*_shared.py` module. This keeps old imports working while
preventing individual source files from growing beyond the current 80 KB
maintenance threshold.

Examples include:

```text
interfaces/gui/operations/commerce/betting/
├── betting_shop_gui.py           # Stable compatibility import
├── application.py
├── base.py
├── shared.py
├── services/
└── tabs/

interfaces/gui/operations/commerce/nailbar/
├── nailbar_gui.py                # Stable compatibility import
├── nailbar_gui_shared.py
└── nailbar_gui_parts/

infrastructure/database/schemas/
├── admin_support_schemas.py      # Stable compatibility import
├── admin_support_schemas_shared.py
└── admin_support_schemas_parts/
```

## Migrations

```text
education_system/migrations/
├── env.py                        # Alembic environment
├── feature_schema_sql.py         # Feature-owned schema helpers
└── versions/
    ├── ...canonical_university_lifecycles.py
    ├── ...core_feature_owned_schemas.py
    ├── ...university_transactional_outbox.py
    ├── ...admissions_policy_and_consumer_receipts.py
    └── ...institutional_operations.py
```

Migration filenames include revision identifiers; the abbreviated names above
describe their responsibilities rather than replacing the actual filenames.

## Tests

```text
tests/
├── launcher/
├── migrations/
├── platform/                     # Tests mirroring shared platform boundaries
├── systems/
│   ├── nursery/
│   ├── primary/
│   ├── secondary/
│   ├── sixth_form/
│   └── university/               # 603 Python test/support files
│       ├── _support/
│       ├── application/
│       ├── browser/
│       ├── contracts/
│       ├── domain/
│       ├── infrastructure/
│       ├── integration/
│       ├── interfaces/
│       ├── services/
│       └── smoke/
└── tools/
```

Tests belong in `tests`; test packages are not stored inside production
system packages.

## Runtime data

Runtime databases, uploads, reports, caches, logs, backups and secrets belong
under `var`, not inside importable packages:

```text
var/
├── backups/university/
├── data/
│   ├── platform/
│   ├── nursery/
│   ├── primary/
│   ├── secondary/
│   ├── sixth_form/
│   └── university/
├── logs/university/
└── secrets/
```

Use the path constants in `education_system.paths` rather than constructing
runtime paths manually. It is the single source of truth for every filesystem
path in the platform: the nine per-system `paths.py` modules that used to sit
under `platform/` and each system's `infrastructure/` were consolidated into it,
because 60 of their 225 names collided — `DATA_DIR`, `STAFF_DB` and
`ensure_directories` meant different files in different packages.

Every constant is prefixed with the system that owns it — `UNIVERSITY_`,
`SIXTH_FORM_`, `SECONDARY_`, `PRIMARY_`, `NURSERY_`, `PLATFORM_`. Only the three
anchors that are identical across all six (`PROGRAM_ROOT`, `VAR_DIR`,
`REPO_ROOT`) are unprefixed. Directories are never created on import; call the
relevant `ensure_*_directories()` at startup, or `ensure_all_directories()`.

## Import conventions

- Use absolute imports beginning with `education_system` across architectural
  boundaries.
- Use relative imports only within a cohesive package.
- Import shared capabilities from `education_system.platform`, not from another
  system package.
- Keep domain modules independent of Tkinter, Flask and CLI presentation code.
- Preserve public imports with a small compatibility façade when splitting a
  mature module.
- Do not add package directories directly to `sys.path`; run with `src/` as
  the application root or install the project. Never put
  `src/education_system/` itself on `sys.path` — its `platform/` package would
  shadow the standard library `platform` module.

## Primary entry points

`main()` and argument parsing live in `education_system/launcher/main.py`.
`education_system/__main__.py` forwards to it so `python -m education_system`
works, and the repository root carries a deprecated `run.py` shim that imports
the same function, so `python run.py` keeps working from a source checkout.

```text
src/education_system/launcher/main.py
src/education_system/__main__.py
education_system/launcher/systems.py
education_system/platform/delivery/api/unified_server.py
education_system/platform/delivery/api/university/api_server.py
education_system/systems/university/interfaces/cli/shell/menu_router.py
education_system/systems/university/interfaces/gui/shell/main/main_gui.py
```

See [ADR 0018](../adr/0018-repository-layout.md) for layout decisions and the
[University documentation](../university/README.md) for system-specific
architecture and ownership guidance.
