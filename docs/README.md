# Education System - Documentation

Central documentation hub for all seven management systems in the Education System platform.

---

## Systems

| System | Description | Docs |
|--------|-------------|------|
| **University** | Higher education platform — 18 domains, CLI/GUI/API/Web | [University Docs](university/README.md) |
| **Sixth Form College** | Sixth form (16-19) — CLI/GUI/API | [College Docs](sixth_form/README.md) |
| **Secondary School** | Years 7-11, KS3/KS4, GCSE 9-1 — CLI/GUI/API | [Secondary School Docs](secondary/README.md) |
| **Primary School** | Reception-Year 6, EYFS/KS1/KS2 — CLI/GUI/API | [Primary School Docs](primary/README.md) |
| **Nursery / Early Years** | Ages 0-5, EYFS — CLI/GUI/API | [Nursery Docs](nursery/README.md) |
| **FE College** | Further education — CLI/GUI, API main-menu routes only | [FE College Docs](fe_college/college_system.md) |
| **Apprenticeships** | Apprenticeship programmes, five roles — CLI/GUI, API main-menu routes only | [Apprenticeships Docs](apprenticeships/apprenticeship_system.md) |

## Quick Start

Each system has its own quick start guide:

- [University Quick Start](university/QUICK_START.md)
- [College Quick Start](sixth_form/QUICK_START.md)
- [Secondary School Quick Start](secondary/QUICK_START.md)
- [Primary School Quick Start](primary/QUICK_START.md)

## Shared Infrastructure

All seven systems share a unified authentication module and cross-system tooling:

- [Shared Authentication](shared/AUTHENTICATION.md) — architecture, database, roles, default accounts
- [MFA Guide](shared/MFA_GUIDE.md) — TOTP setup, login flow, recovery codes
- [Universal Login](shared/UNIVERSAL_LOGIN.md) — cross-system login window and launcher
- [Shared Infrastructure](shared/INFRASTRUCTURE.md) — webhooks, offline sync, notifications

The unified launcher (`python -m education_system`) provides system and mode selection for both CLI and GUI, with runtime system switching.

## Documentation Structure

```
docs/
├── README.md                        # This file
├── TESTING.md                       # Running the test suite
├── education_system.md              # Package overview
├── index.html                       # Static landing page
│
├── api/                             # OpenAPI specs
├── assets/                          # Images for the guides
├── platform/                        # Shared platform overview
│
├── reference/                       # Technical references
│   ├── API_REFERENCE.md            # Unified REST API
│   ├── CLI_REFERENCE.md            # CLI commands and menu structure
│   ├── WEBHOOKS.md                 # Webhook system guide
│   ├── OFFLINE_SYNC.md             # Offline sync and caching guide
│   ├── MODULE_GUIDES.md            # Index of module guides
│   ├── PROJECT_STRUCTURE.md        # Full directory tree
│   ├── DEFAULT_ACCOUNTS.md         # Pre-seeded dev credentials
│   ├── appendices.md               # Appendices A-K
│   └── college_and_apprenticeships/ # Apprenticeships architecture, CLI, GUI, API
│
├── operations/                      # Deployment and admin
│   ├── ADMIN_OPERATIONS.md         # Consolidated admin/ops manual
│   ├── DEPLOYMENT.md               # Docker, production deployment
│   ├── TROUBLESHOOTING.md          # Common issues and solutions
│   ├── CLOUD_ORCHESTRATION.md      # Kubernetes and Swarm runbook
│   ├── LAYOUT_MIGRATION_MAP.md     # Old path to new path
│   ├── layout-migration-map.tsv
│   └── ROADMAP.md                  # Future plans and known limitations
│
├── adr/                             # Architecture Decision Records
│   ├── README.md                   # ADR index
│   ├── template.md                 # ADR template
│   ├── 0001-unified-flask-server.md
│   ├── 0002-shared-authentication.md
│   ├── 0003-sqlite-per-system.md
│   ├── 0004-spa-vanilla-js.md
│   ├── 0005-service-layer-pattern.md
│   ├── 0006-domain-driven-module-structure.md
│   ├── 0007-multi-interface-architecture.md
│   ├── 0008-graphql-api.md
│   ├── 0009-websocket-realtime.md
│   ├── 0010-multi-tenancy.md
│   ├── 0011-data-retention-gdpr.md
│   ├── 0012-centralized-structured-logging.md
│   ├── 0013-general-ledger.md
│   ├── 0014-accounts-payable.md
│   ├── 0015-vat.md
│   ├── 0016-multi-currency-fx-accounting.md
│   ├── 0017-fixed-assets-depreciation.md
│   ├── 0018-repository-layout.md
│   └── 0019-service-oriented-runtime.md
│
├── shared/                          # Shared infrastructure docs
│   ├── AUTHENTICATION.md           # Unified auth system
│   ├── INFRASTRUCTURE.md           # Webhooks, offline, notifications
│   ├── MFA_GUIDE.md                # Multi-factor authentication
│   └── UNIVERSAL_LOGIN.md          # Cross-system login
│
├── university/                      # University system docs
│   ├── README.md                   # Documentation index
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── technical_reference.md      # Module APIs and patterns
│   ├── ai/                         # AI dependencies, voice features
│   ├── security/                   # Auth, MFA, security guides
│   ├── infrastructure/             # Database, email, monitoring
│   ├── development/                # Dev setup, testing, API
│   ├── maintenance/                # Maintenance notes by feature
│   ├── guides/                     # User guides (5 categories)
│   └── modules/                    # Module documentation
│
├── sixth_form/                  # Sixth form system docs
│   ├── README.md
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                   # Auth, MFA, security
│   ├── infrastructure/             # Database, API, config
│   ├── development/                # Dev setup, testing, modules
│   └── guides/                     # Domain guides (10 categories)
│
├── secondary/                # Secondary school docs
│   ├── README.md
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                   # Auth, MFA, security
│   ├── infrastructure/             # Database, auth, config
│   ├── development/                # Dev setup, testing, modules
│   └── guides/                     # Domain guides (7 categories)
│
├── primary/                  # Primary school docs
│   ├── README.md
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                   # Auth, MFA, security
│   ├── infrastructure/             # Database, auth, config
│   ├── development/                # Dev setup, testing, modules
│   └── guides/                     # Domain guides (7 categories)
│
├── nursery/                  # Nursery docs
│   └── README.md
│
├── fe_college/               # FE College docs
│   └── college_system.md
│
├── apprenticeships/          # Apprenticeships docs
│   ├── apprenticeship_system.md
│   └── university_integration.md
│
└── changelogs/                      # Archived changelogs
    ├── CHANGELOG-v8.md             # Version 8.x
    ├── CHANGELOG-v7.md             # Version 7.x
    ├── CHANGELOG-v6.md             # Version 6.x
    ├── CHANGELOG-v5.md             # Versions 0.x through 5.x
    ├── CHANGELOG-modules.md        # Module-specific changelogs
    └── CHANGELOG-legacy-notes.md   # Legacy feature docs
```

## Operations & Administration

| Document | Description |
|----------|-------------|
| [Admin Operations Manual](operations/ADMIN_OPERATIONS.md) | Setup, users, security, backups, monitoring, maintenance |
| [Deployment Guide](operations/DEPLOYMENT.md) | Docker, nginx, production deployment |
| [Troubleshooting](operations/TROUBLESHOOTING.md) | Common issues and solutions |
| [Cloud Orchestration](operations/CLOUD_ORCHESTRATION.md) | Kubernetes and Docker Swarm runbook |
| [Roadmap](operations/ROADMAP.md) | Future plans and known limitations |

## Reference

| Document | Description |
|----------|-------------|
| [API Reference](reference/API_REFERENCE.md) | Unified REST API — auth, per-system routes, error formats |
| [CLI Reference](reference/CLI_REFERENCE.md) | CLI commands, menu structures, make targets |
| [Webhooks Guide](reference/WEBHOOKS.md) | Event dispatch, HMAC signing, retry policy |
| [Offline Sync Guide](reference/OFFLINE_SYNC.md) | Caching, mutation queue, conflict resolution |
| [Module Guides](reference/MODULE_GUIDES.md) | Index of per-module user guides |
| [Project Structure](reference/PROJECT_STRUCTURE.md) | Full directory tree (all 7 systems) |
| [Default Accounts](reference/DEFAULT_ACCOUNTS.md) | Pre-seeded dev credentials |
| [Testing Guide](TESTING.md) | Running the test suite |
| [Appendices](reference/appendices.md) | Appendices A-K: conventions, references |
| [Technical Reference](university/technical_reference.md) | University module APIs and integration patterns |

## Architecture Decision Records

| ADR | Description |
|-----|-------------|
| [ADR Index](adr/README.md) | All 19 architecture decisions |
| [ADR-0001](adr/0001-unified-flask-server.md) | Unified Flask server |
| [ADR-0002](adr/0002-shared-authentication.md) | Shared authentication |
| [ADR-0003](adr/0003-sqlite-per-system.md) | SQLite per-system databases |
| [ADR-0004](adr/0004-spa-vanilla-js.md) | Vanilla JS SPA |
| [ADR-0005](adr/0005-service-layer-pattern.md) | Service layer pattern |
| [ADR-0006](adr/0006-domain-driven-module-structure.md) | Domain-driven module structure |
| [ADR-0007](adr/0007-multi-interface-architecture.md) | Multi-interface architecture |
| [ADR-0008](adr/0008-graphql-api.md) | GraphQL API |
| [ADR-0009](adr/0009-websocket-realtime.md) | WebSocket real-time features |
| [ADR-0010](adr/0010-multi-tenancy.md) | Multi-tenancy |
| [ADR-0011](adr/0011-data-retention-gdpr.md) | GDPR data retention |
| [ADR-0012](adr/0012-centralized-structured-logging.md) | Centralized structured logging |
| [ADR-0013](adr/0013-general-ledger.md) | General ledger |
| [ADR-0014](adr/0014-accounts-payable.md) | Accounts payable and vendor master |
| [ADR-0015](adr/0015-vat.md) | VAT (UK) |
| [ADR-0016](adr/0016-multi-currency-fx-accounting.md) | Multi-currency and FX accounting |
| [ADR-0017](adr/0017-fixed-assets-depreciation.md) | Fixed assets and depreciation |
| [ADR-0018](adr/0018-repository-layout.md) | Repository layout consolidation |
| [ADR-0019](adr/0019-service-oriented-runtime.md) | Service-oriented production runtime |

## Troubleshooting (Per-System)

- [University Troubleshooting](university/TROUBLESHOOTING.md)
- [College Troubleshooting](sixth_form/TROUBLESHOOTING.md)
- [Secondary School Troubleshooting](secondary/TROUBLESHOOTING.md)
- [Primary School Troubleshooting](primary/TROUBLESHOOTING.md)

## Changelog Archives

The main [CHANGELOG.md](../CHANGELOG.md) covers the current version 9 history.
Earlier history is archived here:

| Archive | Description |
|---------|-------------|
| [CHANGELOG-v8.md](changelogs/CHANGELOG-v8.md) | Version 8.x (300 releases) |
| [CHANGELOG-v7.md](changelogs/CHANGELOG-v7.md) | Version 7.x (25 releases) |
| [CHANGELOG-v6.md](changelogs/CHANGELOG-v6.md) | Version 6.x (29 releases) |
| [CHANGELOG-v5.md](changelogs/CHANGELOG-v5.md) | Versions 0.x through 5.x (298 releases) |
| [CHANGELOG-modules.md](changelogs/CHANGELOG-modules.md) | Module-specific changelogs (29 entries) |
| [CHANGELOG-legacy-notes.md](changelogs/CHANGELOG-legacy-notes.md) | Legacy feature documentation and migration notes |

---

**Last Updated**: October 2026
