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

1. `run.py` launches `UniversalLoginWindow` from `shared/gui/`
2. Credentials validated against central `auth.db` via `shared/auth/`
3. `user_systems` table determines which systems the user can access
4. Authenticated user info passed to the target system launcher
5. Cross-system switching supported without re-authentication

---

## Usage

These modules are not run directly. They are imported by each subsystem's infrastructure layer. See the [root README](../../../README.md) for full documentation.
