# Roadmap

> This document was extracted from the main [README.md](../../README.md). See the README for the full project documentation.

---

## Known Limitations

The following limitations should be considered when deploying this system:

| Limitation | Details |
|------------|---------|
| **Web Interface** | All 7 systems have REST routes via the unified server, though FE College and Apprenticeships have only main-menu routes answering 501; University has the most comprehensive Web Portal SPA; other systems have web dashboard views with fewer custom CRUD pages |
| **Multi-tenancy** | Database-per-tenant hosting is available; see [Cloud Orchestration](CLOUD_ORCHESTRATION.md) |
| **SQLite Concurrency** | May have performance limits with high concurrent writes; the application runs on SQLite, so API replicas are limited to a single writer |
| **i18n Coverage** | Most GUI modules now have i18n support (500+ strings translated in v5.41.x); some modules still have incomplete coverage |
| **Production Readiness** | Not recommended for production without implementing security recommendations (see [Security Documentation](../../SECURITY.md)) |
| **Mobile Support** | No native mobile app; web interface responsive but not mobile-optimized |
| **Real-time Features** | Socket.IO/WebSocket support (notifications, chat, presence) ships behind the optional `realtime` extra; disabled with graceful fallback when the extra is not installed |

---

### Multi-System Education Platform (August 2026) — CURRENT (v9.7.x)
- [x] **Canonical ADR 0018 layout** (`src/`): Shared capabilities live under `education_system/platform/`, the seven systems live under `education_system/systems/`, tests live under `tests/`, and runtime state lives under `var/`
- [x] **Unified Launcher** (`src/education_system/launcher/main.py`): Single entry point for University, Sixth Form College, FE College, Apprenticeships, Secondary School, Primary School, and Nursery / Early Years systems with CLI & GUI system selection and runtime switching
- [x] **Shared Authentication** (`education_system/platform/identity/auth/`): Unified auth across all 7 systems with bcrypt hashing, MFA, sessions, WebAuthn, SSO and cross-system identity
- [x] **Cross-System CLI Switching** (v7.5.0): All 7 CLI systems support switching to any other system without re-authenticating
- [x] **Unified REST API**: All 7 systems are served from `education_system/platform/delivery/api/unified_server.py`; route blueprints live under `education_system/api/<system>/` and are mounted by `platform/delivery/api/registry.py`, with the university route library under `platform/delivery/api/university/`
- [x] **GraphQL API alongside REST**: Strawberry schema, authenticated queries, role-gated mutations, depth/rate controls and `/api/v1/graphql` production mounting ship in the default API installation
- [x] **Progressive Web App foundation**: University mobile web assets include a manifest, service worker, offline-capable application shell and responsive styling
- [x] **University System**: 5,738 Python modules across application, domain, infrastructure, CLI, GUI and cross-domain service layers
- [x] **Sixth Form College System**: 1,472 Python modules covering apprenticeships, T-levels, UCAS, functional skills, safeguarding, Prevent duty, GDPR, quality assurance, bursary and funding
- [x] **Secondary School System**: 858 Python modules covering Years 7-11, KS3/KS4, GCSE assessment, pastoral care, behaviour and parent engagement
- [x] **Primary School System**: 839 Python modules covering Reception-Year 6, EYFS/KS1/KS2, phonics, reading, SATs, safeguarding and SEND
- [x] **Nursery / Early Years System**: 771 Python modules covering ages 0-5, EYFS development, key persons, observations, safeguarding and parent communication
- [x] **FE College System**: 165 Python modules covering vocational qualifications for 16+ and adult learners
- [x] **Apprenticeships System**: 250 Python modules covering five roles, off-the-job hours, portfolio, gateway and end-point assessment

### Version 5.47.0 (February 25, 2026) -- COMPLETED
- [x] **Web Portal** (v5.47.0): Full SPA at `/portal` with JWT auth, dashboard, CRUD for all major entities
- [x] **Staff HR Expansion** (v5.44.0-v5.46.0): 20 new modules -- payroll, faculty scheduling, curriculum design, travel, sabbatical, committees, IP, equipment, cover, workload, directory, mentoring, grants, peer review, communication hub, teaching load; 75+ new database tables
- [x] **Student Services** (v5.43.0): Academic advising, digital student ID, study room booking, printing services, textbook store
- [x] **Codebase Consolidation** (v5.46.1-v5.46.2): Merged fragmented versioned files (HR schemas 7->1, admin tools GUI+locale 4->2), centralised path helpers
- [x] **Continued Refactoring** (v5.42.55-v5.42.64): Additional monolithic file decompositions with backward compatibility

### Version 5.42.54 (February 22, 2026) -- COMPLETED
- [x] **Advanced Authentication** (v5.40.0): WebAuthn/FIDO2, SSO (SAML 2.0 & OIDC), biometric, account linking, delegated access, 25 new permissions
- [x] **Codebase Refactoring** (v5.42.x): 54 monolithic files decomposed into modular packages with full backward compatibility
- [x] **i18n Expansion** (v5.41.x): 500+ hardcoded strings replaced with translation calls across 20+ GUI modules
- [x] **Bug Fixes** (v5.39.6-v5.40.x): 50+ database schema fixes, GUI layout corrections, email integration fixes
- [x] **Security Hardening** (v5.39.7): Removed hardcoded credentials, secure random password generation via `secrets` module

### Version 5.39.5 (February 11, 2026) -- COMPLETED
- [x] **Flask REST API** (v5.22.0): 60 route files, JWT auth, 57+ endpoint groups, pagination, rate limiting
- [x] **Major Security Audit** (v5.28.0): 25+ critical/high/medium fixes across 30+ files
- [x] **Office Hours & TA Management** (v5.29.0): Full CRUD with CLI, GUI, and API
- [x] **Role-Based Dashboards** (v5.29.0-v5.39.0): Admin, instructor, student dashboards with live data
- [x] **Admin Tools** (v5.36.0): Alert config, department management, institution branding
- [x] **Instructor Tools** (v5.37.0): Roster viewer, bulk grade import, course messaging, semester analytics
- [x] **Student Self-Service** (v5.39.0): 13 new features (profile, security, notifications, grades, degree progress, catalog, GPA calculator, messaging, forums, finance, help center, documents)
- [x] **Seed Demo Data** (v5.38.0): 310+ records across 30 tables
- [x] 200+ bug fixes and quality improvements

### Version 5.17.0 (February 7, 2026) -- COMPLETED
- [x] **Document Manager GUI**: 26-file modular package (from 18,953-line monolith)
- [x] **AI Detector**: 49-file modular package (from 10,864-line monolith)
- [x] **Cinema GUI**: 52-file modular package (from 11,086-line monolith)
- [x] **Plagiarism GUI**: 20-file modular package (from 7,132-line monolith)
- [x] **Housing & Shop GUIs**: Converted to modular packages

### Version 5.12.0 (February 2026) -- COMPLETED
- [x] **Observability & Monitoring** - Metrics, health checks, alerts
- [x] **Automated Data Management** - Backup scheduler with retention
- [x] **Performance Optimization** - LRU cache with TTL
- [x] **Remember Me Authentication** - 30-day persistent tokens

### Version 5.5.0 (January 2026) -- COMPLETED
- [x] **Student Success & Engagement Platform** - 18 comprehensive modules
- [x] 40+ new database tables, full CLI and GUI interfaces

### Version 5.4.0 (January 2026) -- COMPLETED
- [x] **Staff HR Management System** - 15 specialized managers
- [x] 23 new database tables, 14 CLI menus + 14 GUI interfaces

### Remaining Tasks
- [x] ~~REST API for Secondary School and Primary School systems~~ (completed v7.25.0-v7.31.0)
- [x] ~~Integration with external LMS systems~~ (shipped: Canvas, Moodle, Google Classroom, Microsoft Teams via the `integrations` extra)
- [x] ~~Real-time collaboration features (notifications, chat, presence via WebSockets)~~ (shipped: Socket.IO server via the `realtime` extra)
- [ ] Mobile application (no client exists in this repository; see Known Limitations)
- [x] ~~Complete i18n support for all remaining GUI modules~~ (all recognized
  GUI text sinks use the shared translation service; an audit/codemod prevents
  hardcoded widget, window, menu and dialog text from returning)

### Future Considerations
- [x] ~~Microservices architecture~~ (service-oriented strangler runtime with an independently deployable read-only credential verifier and versioned contract)
- [x] ~~GraphQL API alongside REST~~ (implemented with Strawberry as a default dependency, authenticated endpoint and role-gated mutations)
- [x] ~~Production-ready multi-tenancy for hosting multiple institutions~~ (database-per-tenant isolation, strict middleware, conflict rejection, provisioning and cross-database tests)
- [x] ~~Cloud-native orchestration~~ (Kubernetes/Kustomize and Swarm definitions, probes, secrets, persistent storage, security contexts and operations runbook)
- [ ] Localization (l10n) — expand translation coverage beyond 13 languages
- [x] ~~Tamper-evident credential verification~~ (canonical signed payloads, mandatory persistent signing key, issuance, public/authenticated verification, tamper detection, revocation ledger, GUI, CLI and API integration)
- [x] ~~Extend tamper-evident credential support to authoritative academic records and external verification networks~~ (source-record hashes/resolvers, network receipts and failure-safe publication)
- [x] ~~Advanced AI features (chatbot improvements, automated grading)~~ (authenticated grounded-assistant and review-first grading APIs over the existing engines)
- [x] ~~Mobile-first responsive web design~~ (single-column small-screen layouts, accessible touch targets, safe areas, and overflow-safe navigation/tables)
