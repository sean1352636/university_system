# Database

Apprenticeships only — `fe_college` has no database.

One physical SQLite file holds every table:

```
program/var/data/apprenticeships/apprenticeships.db
```

Overridable with `EDU_APPRENTICESHIPS_DATA_DIR`. The path constant is
`paths.APPRENTICESHIPS_DB`; the per-concern aliases beside it
(`APPRENTICESHIPS_FUNDING_DB`, `APPRENTICESHIPS_EPA_DB`, …) all point at
the same file. The screens are join-heavy by nature — an apprentice's
dashboard reads their programme, employer, hours, portfolio, reviews,
gateway and EPA record in one go — so splitting them across files would
buy nothing and cost cross-connection coordination.

## Creation

`infrastructure/persistence/schema.py`, not Alembic. `SCHEMA` is one
`executescript` of `CREATE TABLE IF NOT EXISTS` statements, and
`init_db()` is idempotent, thread-safe and cheap after the first call —
every public service function calls it, so no caller has to bootstrap.

`executescript(SCHEMA)` only ever *creates*, so a column added to an
existing definition never reaches a database that already exists.
`_migrate()` closes that gap and runs on every process start; every step
in it must be idempotent.

## Conventions

| Kind | Stored as |
|---|---|
| Dates | ISO `YYYY-MM-DD` TEXT |
| Timestamps | `datetime('now')` — UTC TEXT |
| Money | REAL |
| Booleans | INTEGER 0/1 |
| Every table | `created_at`; mutable ones also `updated_at` |

Foreign keys are declared **and enforced**: `PRAGMA foreign_keys = ON`
is set per connection in `schema.connect()`, because SQLite does not
persist it in the file. WAL journalling and a 5s busy timeout are set
the same way.

## Tables

36 in five groups.

**People and organisations**
`employers`, `employer_workplaces`, `employer_managers`, `staff`,
`apprentices`, `apprentice_status_history`, `breaks_in_learning`,
`withdrawals`

**Programmes**
`programmes`, `programme_ksbs`, `occupational_duties`

**Delivery and evidence**
`training_sessions`, `session_attendance`, `training_plan_items`,
`otj_entries`, `portfolio_evidence`, `evidence_ksb_map`,
`portfolio_verifications`, `reviews`, `review_targets`,
`review_signatures`, `employer_feedback`

**Finishing**
`functional_skills`, `gateway_records`, `gateway_checks`, `epaos`,
`epa_bookings`, `epa_results`, `epa_resits`

**Money, compliance and system**
`funding_records`, `funding_payments`, `compliance_documents`,
`eligibility_checks`, `email_messages`, `audit_log`, `user_preferences`

Indexes cover the filters every list screen offers plus the foreign keys
the dashboards aggregate over. `ix_appr_journey` is created in
`_migrate()` rather than in `SCHEMA`, because the column it indexes is
itself added by a migration.

## What is deliberately not stored

Three things are recomputed on every read, and putting them in a column
would be a regression:

- **The off-the-job target.** Derived from the programme dates, so
  moving a planned end date re-baselines it
  (`domain/training/off_the_job_hours.target_hours`).
- **Gateway's automatic checks.** Six of the seven requirements are
  recomputed from the hour log, functional skills, portfolio and
  reviews. A hand-back of approved hours or a KSB reopened for more
  evidence has to take the requirement with it — that is what gateway is
  for. Only `employer_sign_off` is stored, in `gateway_checks`.
- **KSB coverage.** Rolled up from `evidence_ksb_map` across accepted
  evidence.

## Audit

`audit_log` is written by `compliance_repository.record(...)`, called
from the services rather than the repositories, so an entry always
carries the actor and the reason rather than just the row that changed.
Actions come from `config.AUDIT_ACTIONS`. `entity_id` is TEXT, because
some entities are keyed on a pair (`"{apprentice_id}:{doc_key}"`).

Reading it is administrator-only: a log that records every user's
actions must not be readable by the people it records, so it is not
scoped-and-shared like the rest of the system.

## Retention

`config.RETENTION_YEARS` (7) after an apprentice's `actual_end_date`.
`compliance_service.retention_report()` lists records past it. Nothing
deletes automatically — disposal is a policy decision, not a cron job.

## Tests

Every test runs against a throwaway file. The fixture repoints
`schema.DB_PATH` **and** calls `schema.reset_ready_flag()`; doing only
the first leaves the next `init_db()` short-circuiting on the cached
"schema is ready" flag and the tests silently writing to the real
database.
