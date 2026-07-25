# 0003 — SQLite Per-System Databases

**Date:** 2025-06-01
**Status:** Accepted

---

## Context

The platform needs a persistent relational store for each of its four education systems plus a
shared authentication database. The requirements at initial development were:
- Zero-infrastructure deployment (no separate database server process)
- Simple backup (copy a file)
- Sufficient performance for single-institution usage (hundreds to low thousands of concurrent
  users at most)
- Easy development setup on any OS without Docker

Alternatives considered:
- PostgreSQL — full-featured but requires a running server and pg client libraries; raises
  the barrier for local development significantly
- A single shared SQLite file for all systems — rejected because table name collisions across
  systems would require prefixing every table, and a single corrupt file would take down all
  systems simultaneously
- MySQL/MariaDB — similar objections to PostgreSQL

## Decision

We will use one SQLite database file per system, plus a separate file for shared auth:

| File | Purpose |
|------|---------|
| `shared/data/db_files/auth.db` | Shared authentication (users, sessions, MFA) |
| `university_system/data/db_files/student_records.db` | University domain data |
| `college_system/data/db_files/sixthform.db` | College domain data |
| `secondary_school/data/db_files/secondary_school.db` | Secondary school domain data |
| `primary_school/data/db_files/primary_school.db` | Primary school domain data |

Each system owns its schema and migrations independently. The `connect(db_path)` function
in each system's `infrastructure/database/db.py` returns a `sqlite3.Connection` configured
with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`.

Database paths are resolved at runtime via environment variables (`COLLEGE_DB_PATH`,
`UNIVERSITY_DB_PATH`, etc.) with sensible defaults pointing to the paths above. This allows
test suites and Docker deployments to redirect to temporary or volume-mounted paths.

Schema initialisation is idempotent (`CREATE TABLE IF NOT EXISTS`) so restarting a system
never corrupts existing data.

## Consequences

### Positive
- No external database server — `pip install -r requirements.txt` is all that is needed
- Each system's database can be backed up independently with a file copy
- Corruption or schema issue in one system does not affect others
- `sqlite3` is in the Python standard library; no additional driver dependencies

### Negative / Trade-offs
- SQLite does not support full concurrent write access — only one writer at a time; acceptable
  for single-institution deployments but a blocker for multi-tenant SaaS
- No native replication or streaming backups; point-in-time recovery requires external tooling
- Cross-system queries (e.g. "show all students across university and college") require
  application-level joins or `ATTACH DATABASE`

### Neutral
- The `docker-compose.yml` mounts `./education_system/{system}/data/db_files/` as volumes so
  data persists across container restarts
- ADR [0010](0010-multi-tenancy.md) (proposed) addresses the path to multi-tenancy

---

*See also: [0002](0002-shared-authentication.md) (auth.db), [0005](0005-service-layer-pattern.md) (connection pattern)*
