# 0011 — Automated GDPR Data Retention Policies

**Date:** 2026-03-26
**Status:** Proposed

---

## Context

The platform stores personal data for students, staff, and parents across all four systems.
UK GDPR (and its predecessor, EU GDPR) requires that personal data is not kept longer than
necessary for the purpose for which it was collected.

Currently there is no automated mechanism to delete or anonymise records when retention periods
expire. Manual compliance relies entirely on administrator discipline. As the platform moves
toward a multi-tenant hosted offering, the absence of automated retention becomes a regulatory
liability.

The platform already contains a `shared/gdpr/` module with some utilities. It needs to be
extended into a full retention policy engine.

Relevant retention periods for UK schools and colleges (approximate; subject to institutional
policy):
- Student academic records: 7 years after leaving
- Safeguarding records: until the subject reaches age 25 (or 75 for child protection)
- Staff HR records: 7 years after employment ends
- Session/audit logs: 2 years
- MFA recovery codes: delete on use; expire unused codes after 1 year

## Decision

We propose an automated retention engine in `shared/gdpr/retention/`:

**Policy definition**: retention policies are declared as Python dataclasses:
```python
@dataclass
class RetentionPolicy:
    table: str
    date_column: str          # e.g. "left_date", "created_at"
    retention_days: int
    action: Literal["delete", "anonymise"]
    anonymise_columns: list[str] = field(default_factory=list)
```

Policies are registered per system in a `RETENTION_POLICIES` list loaded at startup.

**Anonymisation vs deletion**: records subject to legal hold (e.g. safeguarding) are
anonymised (PII columns replaced with `[REDACTED]`) rather than deleted. Purely transactional
records (sessions, temporary tokens) are hard-deleted.

**Execution**: a `RetentionJob` class applies all registered policies for a given db_path.
The job is designed to run as:
- A scheduled task via `APScheduler` (in-process, runs nightly at 02:00)
- A standalone CLI command: `python run.py --school --cli retention run`
- A Makefile target: `make retention-run`

**Audit trail**: every deletion or anonymisation is recorded in the existing `audit_log` table
with `action="data_retention"`, `affected_table`, and `rows_affected`. This provides an
evidence trail for regulatory audits.

**Consent withdrawal**: a `GDPRService.forget_subject(user_id)` method performs immediate
anonymisation across all tables for a subject upon verified request.

**Dry-run mode**: `RetentionJob(dry_run=True)` reports what would be deleted/anonymised
without making changes; used by the admin UI preview before confirming.

## Consequences

### Positive
- Automated compliance reduces regulatory risk for hosted customers
- Consistent policy enforcement — no dependence on manual administrator action
- Audit log provides evidence of compliance for ICO inspections
- Dry-run mode allows administrators to review impact before applying policies

### Negative / Trade-offs
- Incorrectly configured retention periods could delete records that should be kept (e.g. an
  active student whose `left_date` was set in error); policies must be reviewed carefully
- Anonymisation is irreversible; a mistake cannot be undone from backup without understanding
  exactly which rows were affected
- Safeguarding retention periods vary by incident type and local authority guidance; a single
  per-table policy may not be granular enough without row-level policy tags
- APScheduler adds a dependency and requires the API server to be running for scheduled jobs;
  a standalone cron job is the alternative for non-API deployments

### Neutral
- The existing `shared/gdpr/` module will be refactored to host the new engine; any existing
  GDPR utilities are preserved
- Subject access requests (SAR) are a separate concern and are not addressed by this ADR

---

*Depends on: [0003](0003-sqlite-per-system.md) (database layout), [0002](0002-shared-authentication.md) (session/audit tables)*
*Related: [0010](0010-multi-tenancy.md) (per-tenant policy configuration)*
