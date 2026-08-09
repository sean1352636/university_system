# 0012 — Centralised Structured Logging (ELK-compatible)

**Date:** 2026-03-26
**Status:** Proposed

---

## Context

The platform currently uses Python's standard `logging` module with a mix of formats across
modules. Log output goes to `stderr` (console) or rotating file handlers configured ad-hoc.
There is no centralised log aggregation, no machine-parseable format, and no correlation
between a user action in the GUI/CLI and the corresponding API request.

As the platform moves toward a hosted multi-tenant deployment (ADR 0010), operators need to:
- Search and filter logs across all four systems from a single interface
- Correlate a user's request chain with a single trace/request ID
- Alert on error rates and specific event types (failed logins, safeguarding alerts)
- Retain and rotate logs in compliance with the audit requirements in ADR 0011

The de-facto standard for log aggregation in self-hosted environments is the ELK stack
(Elasticsearch + Logstash + Kibana) or its lighter-weight alternatives (Grafana Loki + Promtail).
Both expect newline-delimited JSON log records.

## Decision

We propose replacing ad-hoc logging configuration with a centralised structured logging setup
in `shared/logging/`:

**JSON formatter** (`shared/logging/formatters.py`): a custom `logging.Formatter` subclass
that serialises each `LogRecord` to a JSON object:
```json
{
  "timestamp": "2026-03-26T14:22:01.123Z",
  "level": "INFO",
  "logger": "education_system.college_system.modules.domain.attendance",
  "message": "Attendance register submitted",
  "request_id": "a3f1c2d4",
  "user_id": 42,
  "system": "college",
  "tenant_id": "westfield",
  "module": "attendance",
  "extra": {}
}
```

**Request ID middleware** (`shared/api/middleware.py`): generates a UUID4 `request_id` at the
start of each Flask request, stores it on `flask.g`, and injects it into every log record
emitted during that request via a `logging.Filter`. The ID is also returned in the
`X-Request-ID` response header for client-side correlation.

**Log levels by environment**:
- `DEBUG` in development (set via `LOG_LEVEL=DEBUG`)
- `INFO` in production (default)
- `WARNING` for security events regardless of global level (using a dedicated
  `security` logger at `WARNING` floor)

**Output targets**:
- Console (`StreamHandler`) — always enabled; the container/systemd journal captures it
- Rotating file (`RotatingFileHandler`, max 50 MB, 10 backups) — optional via
  `LOG_FILE=/var/log/education_system/app.log`
- Logstash UDP (`python-logstash` handler) — optional via `LOGSTASH_HOST` env var

**Sensitive field scrubbing**: a `SensitiveFieldFilter` replaces values for keys matching
`password`, `token`, `secret`, `mfa_code`, and `recovery_code` with `[REDACTED]` before
serialisation.

**Audit events**: high-value security events (login success/failure, MFA challenges,
permission denials, data exports) are emitted on a dedicated `audit` logger at `INFO` level.
The existing `audit_log` database table is retained for queryable in-app audit history;
the structured log provides an independent, tamper-resistant copy.

**Initialisation**: `shared/logging/setup.py` exports a `configure_logging()` function called
once at application startup from `run.py` and the unified server factory.

## Consequences

### Positive
- All four systems produce consistent, machine-parseable log records from day one of deployment
- Request IDs allow an operator to trace a user complaint ("I got an error at 14:22") to the
  exact log lines and database queries
- ELK/Loki integration requires only pointing Logstash/Promtail at the log file or UDP port —
  no application changes
- Sensitive field scrubbing reduces the risk of credentials appearing in log aggregation tools

### Negative / Trade-offs
- JSON log records are harder to read in a raw terminal than formatted text; a `jq`-based
  alias is needed for developer comfort (`make logs`)
- Structured logging adds minor serialisation overhead per record; negligible at INFO level,
  noticeable at DEBUG level in tight loops
- The `python-logstash` UDP handler is fire-and-forget — log records can be silently lost if
  Logstash is unavailable; a buffered TCP handler reduces this risk at the cost of back-pressure
- Centralised log aggregation infrastructure (Elasticsearch, Loki) is not included in the
  existing `docker-compose.yml` and would need to be added

### Neutral
- The structured log is complementary to (not a replacement for) the in-database `audit_log`
  table; each serves a different consumer (ops tooling vs. in-app admin UI)
- Existing `logging.getLogger(__name__)` calls throughout the codebase require no changes —
  the JSON formatter is applied at the handler level

---

*Depends on: [0001](0001-unified-flask-server.md) (Flask request lifecycle), [0002](0002-shared-authentication.md) (audit events)*
*Related: [0011](0011-data-retention-gdpr.md) (log retention periods), [0010](0010-multi-tenancy.md) (per-tenant log segregation)*
