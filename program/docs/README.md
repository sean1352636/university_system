# Education System - Documentation

Central documentation hub for all four management systems in the Education System platform.

---

## Systems

| System | Description | Docs |
|--------|-------------|------|
| **University** | Higher education platform — 60+ domain modules, CLI/GUI/API/Web | [University Docs](university/README.md) |
| **Sixth Form College** | Further education (16-19) — 110 domain modules, CLI/GUI/API | [College Docs](college_system/README.md) |
| **Secondary School** | Years 7-11, KS3/KS4, GCSE 9-1 — 51 domain modules, CLI/GUI/API | [Secondary School Docs](secondary_school/README.md) |
| **Primary School** | Reception-Year 6, EYFS/KS1/KS2 — 46 domain modules, CLI/GUI/API | [Primary School Docs](primary_school/README.md) |

## Quick Start

Each system has its own quick start guide:

- [University Quick Start](university/QUICK_START.md)
- [College Quick Start](college_system/QUICK_START.md)
- [Secondary School Quick Start](secondary_school/QUICK_START.md)
- [Primary School Quick Start](primary_school/QUICK_START.md)

## Shared Infrastructure

All four systems share a unified authentication module and cross-system tooling:

- [Shared Authentication](shared/AUTHENTICATION.md) — architecture, database, roles, default accounts
- [MFA Guide](shared/MFA_GUIDE.md) — TOTP setup, login flow, recovery codes
- [Universal Login](shared/UNIVERSAL_LOGIN.md) — cross-system login window and launcher
- [Shared Infrastructure](shared/INFRASTRUCTURE.md) — webhooks, offline sync, notifications

The unified launcher (`run.py`) provides system and mode selection for both CLI and GUI, with runtime system switching.

## Documentation Structure

```
docs/
├── README.md                        # This file
├── index.html                       # Static landing page
│
├── reference/                       # Technical references
│   ├── API_REFERENCE.md            # Unified REST API (all 4 systems)
│   ├── CLI_REFERENCE.md            # CLI commands and menu structure
│   ├── WEBHOOKS.md                 # Webhook system guide
│   ├── OFFLINE_SYNC.md             # Offline sync and caching guide
│   ├── MODULE_GUIDES.md            # Index of 150+ module guides
│   ├── PROJECT_STRUCTURE.md        # Full directory tree
│   └── appendices.md               # Appendices A-K
│
├── operations/                      # Deployment and admin
│   ├── ADMIN_OPERATIONS.md         # Consolidated admin/ops manual
│   ├── DEPLOYMENT.md               # Docker, production deployment
│   ├── TROUBLESHOOTING.md          # Common issues and solutions
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
│   └── 0012-centralized-structured-logging.md
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
│   ├── guides/                     # 40+ user guides (5 categories)
│   └── modules/                    # Module documentation
│
├── college_system/                  # College system docs
│   ├── README.md
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                   # Auth, MFA, security
│   ├── infrastructure/             # Database, API, config
│   ├── development/                # Dev setup, testing, modules
│   └── guides/                     # Domain guides (10 categories)
│
├── secondary_school/                # Secondary school docs
│   ├── README.md
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                   # Auth, MFA, security
│   ├── infrastructure/             # Database, auth, config
│   ├── development/                # Dev setup, testing, modules
│   └── guides/                     # Domain guides (7 categories)
│
├── primary_school/                  # Primary school docs
│   ├── README.md
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── security/                   # Auth, MFA, security
│   ├── infrastructure/             # Database, auth, config
│   ├── development/                # Dev setup, testing, modules
│   └── guides/                     # Domain guides (7 categories)
│
└── changelogs/                      # Archived changelogs
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
| [Roadmap](operations/ROADMAP.md) | Future plans and known limitations |

## Reference

| Document | Description |
|----------|-------------|
| [API Reference](reference/API_REFERENCE.md) | Unified REST API — auth, 331 route modules, error formats |
| [CLI Reference](reference/CLI_REFERENCE.md) | CLI commands, menu structures, make targets |
| [Webhooks Guide](reference/WEBHOOKS.md) | Event dispatch, HMAC signing, retry policy |
| [Offline Sync Guide](reference/OFFLINE_SYNC.md) | Caching, mutation queue, conflict resolution |
| [Module Guides](reference/MODULE_GUIDES.md) | Index of 150+ per-module user guides |
| [Project Structure](reference/PROJECT_STRUCTURE.md) | Full directory tree (all 4 systems) |
| [Appendices](reference/appendices.md) | Appendices A-K: conventions, references |
| [Technical Reference](university/technical_reference.md) | University module APIs and integration patterns |

## Architecture Decision Records

| ADR | Description |
|-----|-------------|
| [ADR Index](adr/README.md) | All 12 architecture decisions |
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

## Troubleshooting (Per-System)

- [University Troubleshooting](university/TROUBLESHOOTING.md)
- [College Troubleshooting](college_system/TROUBLESHOOTING.md)
- [Secondary School Troubleshooting](secondary_school/TROUBLESHOOTING.md)
- [Primary School Troubleshooting](primary_school/TROUBLESHOOTING.md)

## Changelog Archives

The main [CHANGELOG.md](../../CHANGELOG.md) covers v6.0+. Older history is archived here:

| Archive | Description |
|---------|-------------|
| [CHANGELOG-v5.md](changelogs/CHANGELOG-v5.md) | Versions 0.x through 5.x (298 releases) |
| [CHANGELOG-modules.md](changelogs/CHANGELOG-modules.md) | Module-specific changelogs (29 entries) |
| [CHANGELOG-legacy-notes.md](changelogs/CHANGELOG-legacy-notes.md) | Legacy feature documentation and migration notes |

---

**Last Updated**: April 2026
