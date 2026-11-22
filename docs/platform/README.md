# Shared Modules

Cross-cutting modules in `src/education_system/platform/`, used by all seven education systems (nursery, primary, secondary, sixth form, FE college, apprenticeships, university). Provides unified authentication, shared GUI components, a unified API server, and data portability services.

---

## Key Components

- **Unified authentication** (`identity/auth/`): bcrypt password hashing (with legacy PBKDF2 migration), MFA via TOTP with recovery codes, DB-backed sessions with token expiry. Central auth database at `var/data/platform/db_files/auth.db`. Tables: `users`, `sessions`, `mfa_secrets`, `mfa_recovery_codes`, `user_systems`.
- **Shared GUI** (`delivery/gui/`): Universal login window (`UniversalLoginWindow`), common widgets and themes used across all systems.
- **Unified REST API** (`delivery/api/`): Single Flask server (`unified_server.py`) and mount table (`registry.py`) serving all seven systems with rate limiting and WebSocket support. The routes themselves are in `education_system/api/<system>/`.
- **Student transfers** (`cross_system/`): Linked learner record and progression transfers between systems (see below).
- **Academic misconduct** (`governance/academic_misconduct/`): Evidence management and case tracking shared across systems.
- **Communications** (`integrations/email/`, `features/messaging/`, `features/notifications/`): Shared notification and messaging infrastructure.
- **Security** (`governance/security/`, `governance/gdpr/`, `governance/audit/`): GDPR compliance, audit logging, and security utilities.
- **Analytics and reporting** (`features/analytics/`, `features/reporting/`): Shared dashboards and report generation.

---

## Directory Layout

```
platform/
    identity/              # Unified authentication, staff directory, student IDs
    delivery/              # Interface delivery: api/, cli/, gui/, portals/, web/
    kernel/                # Core primitives: base, core, database, validation, seeding, backup
    governance/            # Audit, GDPR, safeguarding, security, academic misconduct
    integrations/          # Email, webhooks, external services
    features/              # Analytics, calendar, documents, certificates, messaging and more
    cross_system/          # Linked learner record and progression transfers
    services/              # Chat, data retention, parent links, realtime notifications
    testing/               # Shared test helpers
```

---

## Authentication Flow

1. `python -m education_system` launches `UniversalLoginWindow` from `src/education_system/platform/delivery/gui/`
2. Credentials validated against central `auth.db` via `src/education_system/platform/identity/auth/`
3. `user_systems` table determines which systems the user can access
4. Authenticated user info passed to the target system launcher
5. Cross-system switching supported without re-authentication

---

## Linked Platform (one learner across seven systems)

Code lives in `platform/cross_system/` and `platform/features/`; tables live in the central `auth.db`.

| Area | Module | What it does |
|---|---|---|
| Identity | `cross_system/identity_service.py` | Matches a new record in this order: already-linked local id → NHS number or UPN → name + date of birth. Also handles the duplicate queue, `merge_journeys` (audited, logged in `student_journey_merges`, and a merged id follows its survivor) and login links (`users.journey_id`). |
| Login links | `cross_system/login_links.py` | Links each learner's own login to their learner record (`users.journey_id`) automatically. Each system's adapter declares which roles are a learner's own login (`learner_login_roles`) and how a login pairs with its learner (`learner_ids_for_login`), using the same rule as its own sign-in. It never links a parent or staff role, never links when the matches disagree, and never overwrites a link set by hand. Audited as `<system>:auto-link`. |
| Backfill | `cross_system/identity_backfill.py` | `run_all()` runs the identity pass, then enrolments, then qualifications. It is idempotent. |
| Learner 360 | `cross_system/learner_360.py` | One view of a learner's phases, enrolments, attendance, qualifications and destinations. It is tiered by the viewer's role, and unknown roles fail closed. |
| Transfers | `cross_system/transitions.py` | The seven-step engine, plus reject, acknowledge, per-step effective dates, checklists and a step log (`learner_transition_event`). |
| Handover | `cross_system/handover.py` | Reads the handover only through the gated `get_handover_for`. The handover payload never goes on the bus. |
| Destinations | `cross_system/destinations.py` | `record_destination`, `outcome_summary`. |
| Routes | `cross_system/adapters/`, `route_support.py` | One adapter per system. Systems never import each other. |
| Events | `integrations/external/cross_system_bus.py` | The durable outbox. Its consumers are webhooks (`webhooks/bus_forwarder.py`, ids only), notifications (`features/notifications/`, with per-user preferences) and calendar/tasks (`features/calendar/`). |
| API | `delivery/api/routes/learners_routes.py` | `/api/v1/learners`, `/transfers`, `/events`, `/systems`, `/tasks` and `/notifications/preferences`. Permissions are checked per system, and reads are audited as `cross_system.access`. |
| Admin | `delivery/gui/superadmin_linked_sections.py`, `delivery/cli/superadmin_linked_cli.py` | Tasks, Learner 360, the transfer monitor and boards, the event monitor, the system registry, identity and reports (CLI items 17–24). |

---

## Usage

These modules are not run directly. They are imported by each system. See the [root README](../../README.md) for full documentation.
