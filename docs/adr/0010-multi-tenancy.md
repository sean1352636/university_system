# 0010 — Database-per-Tenant Multi-Tenancy Strategy

**Date:** 2026-03-26
**Status:** Proposed

---

## Context

The current architecture assumes a single institution runs its own self-hosted instance. Each
system has a single database file (e.g. `sixthform.db`, `secondary_school.db`). As demand
grows for a hosted/SaaS offering — where multiple schools or colleges share a single
deployment — the platform needs a multi-tenancy model.

Three conventional strategies:

1. **Row-level tenancy** (shared tables, `tenant_id` column on every row) — simplest to
   operate but highest risk of data leakage via missing `WHERE tenant_id = ?` clauses; also
   requires schema migration to add `tenant_id` to every existing table
2. **Schema-per-tenant** (one database schema per tenant) — not supported by SQLite
3. **Database-per-tenant** — each tenant gets its own SQLite file; strong isolation; aligns
   with the existing single-institution model

## Decision

We propose a database-per-tenant strategy where each tenant is assigned a UUID at onboarding
and all database files for that tenant are stored under a namespaced path:

```
data/tenants/{tenant_uuid}/auth.db
data/tenants/{tenant_uuid}/college.db
data/tenants/{tenant_uuid}/secondary_school.db
...
```

Key design points:

**Tenant resolution**: the Flask request context resolves a tenant from either:
- A subdomain (`westfield.eduplatform.example` → tenant `westfield`)
- An HTTP header (`X-Tenant-ID`) for API clients
- A JWT claim (`tenant_id`) after login

A `TenantMiddleware` resolves the tenant early in the request lifecycle and stores the
database paths on `flask.g` so service constructors receive the correct paths.

**Auth database**: `auth.db` remains per-tenant; usernames are unique within a tenant but two
tenants may have the same username. The superadmin account exists in a separate
`admin/auth.db` outside the tenant namespace.

**Schema initialisation**: the existing `CREATE TABLE IF NOT EXISTS` initialisation functions
are called with the tenant-specific path on first access; no manual provisioning script is
needed.

**Backups**: each tenant's data directory can be backed up independently; tenant deletion is a
directory removal.

**SQLite concurrency**: SQLite's single-writer limitation is acceptable per tenant given
typical single-institution concurrency; high-traffic tenants could be migrated to PostgreSQL
by swapping the `connect()` implementation without changing service code.

## Consequences

### Positive
- Strong data isolation — a query bug in one tenant's request cannot leak another tenant's data
- Aligns with the existing single-tenant model; minimal changes to service layer (db_path is
  already a parameter)
- Independent backup, restore, and deletion per tenant
- Regulatory compliance (GDPR data residency) is easier — a tenant's data lives in one place

### Negative / Trade-offs
- Cross-tenant analytics (e.g. regional benchmarking) requires application-level aggregation
  across multiple database files
- File descriptor usage grows linearly with connected tenants; connection pooling or on-demand
  open/close is required
- Operating hundreds of SQLite files in a shared filesystem requires careful inode and disk
  space management
- The `TenantMiddleware` adds a resolution step to every request; misconfiguration could
  misdirect writes to the wrong tenant

### Neutral
- This strategy explicitly defers a move to PostgreSQL; ADR 0003 documents the SQLite choice
  and its trade-offs
- The superadmin dashboard would need a tenant-picker to manage multiple institutions

---

*Depends on: [0003](0003-sqlite-per-system.md) (SQLite per system), [0002](0002-shared-authentication.md) (per-tenant auth.db)*
