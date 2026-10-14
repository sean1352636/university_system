# Shared Modules

Cross-cutting modules used by all four education subsystems (university, college, secondary school, primary school). Provides unified authentication, shared GUI components, a unified API server, and data portability services.

---

## Key Components

- **Unified authentication** (`auth/`): bcrypt password hashing (with legacy PBKDF2 migration), MFA via TOTP with recovery codes, DB-backed sessions with token expiry. Central auth database at `shared/data/db_files/auth.db`. Tables: `users`, `sessions`, `mfa_secrets`, `mfa_recovery_codes`, `user_systems`.
- **Shared GUI** (`gui/`): Universal login window (`UniversalLoginWindow`), common widgets and themes used across all systems.
- **Unified REST API** (`api/`): Single Flask server (`unified_server.py`) serving all four systems with rate limiting and WebSocket support.
- **Student data portability** (`transfer/`, `bulk_transfer/`): CTF, JSON, and CSV export/import for cross-system student transfers.
- **Academic misconduct** (`academic_misconduct/`): Evidence management and case tracking shared across systems.
- **Communications** (`communications/`, `email/`, `messaging/`, `notifications/`): Shared notification and messaging infrastructure.
- **Security** (`security/`, `gdpr/`, `audit/`): GDPR compliance, audit logging, and security utilities.
- **Analytics and reporting** (`analytics/`, `reporting/`): Shared dashboards and report generation.

---

## Directory Layout

```
shared/
    auth/                  # Unified authentication (bcrypt, MFA, sessions)
    gui/                   # Universal login window, shared widgets
    api/                   # Unified REST API server
    core/                  # Shared core utilities
    data/                  # Central auth.db and shared data files
    transfer/              # Student data portability (CTF/JSON/CSV)
    bulk_transfer/         # Bulk data transfer operations
    academic_misconduct/   # Misconduct evidence management
    communications/        # Shared comms infrastructure
    security/              # Security and GDPR utilities
    analytics/             # Shared analytics
    tests/                 # Shared module tests
```

---

## Authentication Flow

1. `python -m education_system` launches `UniversalLoginWindow` from `shared/gui/`
2. Credentials validated against central `auth.db` via `shared/auth/`
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

These modules are not run directly. They are imported by each subsystem's infrastructure layer. See the [root README](../../../README.md) for full documentation.
