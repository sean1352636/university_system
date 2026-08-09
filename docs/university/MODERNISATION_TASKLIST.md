# University System Modernisation Tasklist

This is the delivery backlog for turning the university system into a reliable,
cohesive student-record platform. A checkbox means the acceptance criteria have
been met and verified; the existence of a partial implementation is not enough.

## Delivery principles

- Core student-record decisions are transactional, auditable and effective-dated.
- Schema changes are made by Alembic migrations, never opportunistically by a
  screen or service.
- Business services do not import GUI modules.
- Important cross-domain work is delivered at least once and consumed
  idempotently.
- Health and safeguarding data are denied by default and audited on every read.
- New core modules are typed, tested and small enough to review.
- Peripheral campus services are optional packages, not core dependencies.

## Milestone 1 — reliable applicant-to-enrolment core

### 1. Canonical data model

- [x] Publish a canonical data dictionary for applicant, student, programme
  registration, module enrolment, attendance record, charge and payment.
- [x] Add the first Alembic migration for admissions and student lifecycle
  workflow tables.
- [x] Backfill legacy `enrollments`, `student_modules`, attendance and payment
  variants into the canonical tables.
- [x] Add compatibility views for supported legacy readers.
- [x] Replace runtime `CREATE TABLE`/`ALTER TABLE` in admissions and student
  lifecycle services with schema-version checks.
- [x] Move the remaining feature-owned DDL into migrations, domain by domain.
- [x] Reject application startup when the database revision is unsupported.
- [ ] Remove legacy tables after a measured deprecation window.
  - [ ] Triage and migrate remaining legacy-name references (`student_modules`: 216 files,
    `payments`: 275, `enrollments`: 64, `attendance_records`: 47; baseline
    measured 2026-07-30).
  - [ ] Observe zero production reads and writes for at least 30 days.
  - [ ] Reconcile row counts and archive a signed pre-removal report.
  - [ ] Drop legacy tables and compatibility views in a reversible migration.

Done when a fresh install and an upgrade from the oldest supported release
produce the same schema, and application requests execute no DDL.

### 2. Observable operational failures

- [x] Introduce shared typed operation results and degraded-state records.
- [x] Convert admissions, enrolment, finance, safeguarding and export boundaries
  from `ValueError`/silent `pass` to typed errors or operation results.
- [x] Replace silent schema fallbacks in student export with canonical
  repository queries.
- [x] Add health endpoints for database revision, outbox lag, dead letters,
  email, authentication and external integrations.
- [x] Alert on new degraded states and repeated delivery failures.
- [x] Set remediation owners and runbook links for each health check.

Done when operators can distinguish success, partial success, retrying and
permanent failure without reading application logs.

### 3. Module boundaries

- [x] Split `integration_bus.py` into contracts, publisher, subscriber handlers,
  persistence, retry worker and compatibility facade.
- [x] Move the in-process event registry out of `interfaces/gui`.
- [x] Split `auth/core.py` into authentication, credentials, sessions, recovery
  and audit services.
- [x] Complete the `health_portal.py` split:
  - [x] Add bounded health application, domain, infrastructure, reporting and
    CLI packages.
  - [x] Extract records, appointments, emergency contacts, vaccinations,
    exports, backups, audit and reporting workflows.
  - [x] Replace the legacy 2,575-line module with a compatibility facade.
  - [x] Move remaining consent/privacy behavior behind application services.
- [x] Split CLI menu routing into bootstrap, feature, menu and routing packages
  with a compatibility facade and explicit dependencies.
- [x] Split student-union event management by use case.
- [x] Enforce dependency rules: domain -> application ports; infrastructure and
  interfaces -> domain/application, never the reverse.
- [x] Keep new production modules below 800 lines and cyclomatic complexity 15.

Done when core domain imports can be tested in an environment without Tkinter.

### 4. First web journey

- [x] Add accessible applicant application and status pages.
- [x] Add staff document-check, decision and offer work queues.
- [x] Add offer acceptance, condition evidence and right-to-study steps.
- [x] Add registration and module-selection pages.
- [x] Add timetable/deadline, submission/feedback, fee payment, support request
  and graduation-progress pages.
- [x] Meet WCAG 2.2 AA for keyboard, focus, labels, errors and contrast.
- [x] Add browser tests for the complete applicant-to-enrolment journey.

Done when the journey can be completed on mobile without launching Tkinter.

### 5. Shared infrastructure ownership

- [x] Record ownership decisions for identity, database, email, notifications,
  logging, audit, files, realtime delivery and configuration.
- [x] Expose platform ports/adapters for each shared capability.
- [x] Migrate university callers from local implementations.
- [x] Deprecate, measure and remove duplicate implementations.
- [x] Replace direct `sqlite3` imports with repositories/unit-of-work in core
  domains.

Done when each cross-cutting capability has one supported implementation and
one documented extension interface.

### 6. Reliable events and integrations

- [x] Establish a durable outbox and idempotent consumer receipts in the shared
  platform.
- [x] Add event version, correlation ID, causation ID, idempotency key and
  availability time to every envelope.
- [x] Add exponential retry with jitter and configurable attempt limits.
- [x] Move exhausted deliveries to an explicit dead-letter state.
- [x] Add replay, abandon and inspect operations with authorization and audit.
- [x] Add an operator web screen for lag, failures and dead letters.
- [x] Route admissions, enrolment, fee, award and safeguarding events through
  the durable publisher in the same transaction as their source decision.

Done when killing a consumer cannot lose an event and replay cannot duplicate
its business effect.

### 7. Security and privacy boundaries

- [x] Move runtime keys outside the source/package tree.
- [x] Load secrets through a platform secret-provider interface.
- [x] Reject invalid file keys and disable local key generation outside
  development/test environments.
- [x] Separate health and safeguarding storage from general student records.
- [x] Add purpose-of-use and field-level authorization.
- [x] Audit successful and denied sensitive-record reads immutably.
- [x] Apply explicit retention, legal-hold, redaction and deletion policies.
- [x] Add break-glass access with time limits, reason and independent review.

Done when a general student-record role cannot query sensitive fields directly.

### 8. Enforceable quality gates

- [x] Make Ruff and MyPy blocking for new core modules.
- [x] Remove the command-line `--ignore-missing-imports` override from CI.
- [x] Enforce university domain coverage, starting at 60% and ratcheting upward.
- [x] Add migration upgrade/downgrade and old-version compatibility tests.
- [x] Add API schema/contract and authorization tests.
- [x] Add automated accessibility tests and browser journey tests.
- [x] Add complexity, file-size and forbidden-import checks.
- [x] Publish test, coverage, migration and accessibility reports in CI.

Done when the required CI gate cannot be green after any required check fails.

### 9. Dependency profiles

- [x] Define `core`, `desktop`, `analytics`, `ai`, `documents`, `commerce`,
  `integrations` and `campus-services` installation profiles.
- [x] Remove scientific, GUI and specialist-campus dependencies from core.
- [x] Make optional imports lazy and return a clear capability-unavailable error.
- [x] Build and smoke-test a minimal core wheel in CI.
- [x] Generate an SBOM and scan each supported profile.

Done when the web/API student-record core installs without Tkinter or the
scientific stack.

### 10. Product scope and plugin boundary

- [x] Publish the supported core capability catalogue.
- [x] Classify every current module as core, optional, integration, demo or
  retire.
- [x] Define a versioned plugin manifest and capability/permission model.
- [x] Move betting, butcher, bakery, nail bar, church, car rental and similar
  facilities behind optional plugins.
- [x] Prevent optional modules from owning or mutating canonical student data.
- [x] Document support level, data classification and lifecycle for each plugin.

Done when disabling every optional plugin leaves a complete university
student-record system.

## Milestone 2 — authoritative academic lifecycles

### Admissions

- [x] Separate prospects/applications from students.
- [x] Add multiple choices, conditions, document checks, interviews/auditions,
  acceptance, decline, deferral, lapse and guarded conversion.
- [x] Remove sixth-form intake's default `CS` course and direct active-student
  provisioning.
- [x] Add deposits, sponsorship and right-to-study policy services.
- [x] Make conversion atomic with canonical registration and outbox events.
- [x] Add the full end-to-end integration and browser tests.

### Student registration and status

- [x] Implement registration, re-registration, interruption, withdrawal,
  deferral, suspension, resumption, transfer, mode/campus change, repeat,
  completion and closure service operations.
- [x] Record effective-dated history and downstream reconciliation work.
- [x] Move lifecycle schema creation to migrations only.
- [x] Make finance, modules, visa, accommodation, library and account consumers
  idempotent.
- [x] Add correction/reversal workflows and reconciliation dashboards.

### Assessment boards and awards

- [x] Add an initial assessment-board service.
- [x] Add agenda generation, compensation/condonement, reassessment and
  progression decisions.
- [x] Add chair approval, immutable locked minutes and controlled reopening.
- [x] Store ratified outcomes separately from mutable marks.
- [x] Make transcripts, certificates and graduation consume ratified awards only.

### Postgraduate research

- [x] Add an initial PGR administration service.
- [x] Complete proposal, supervisory team, meetings, training, review, ethics,
  upgrade, submission, examiner, viva, corrections and deposit workflows.
- [x] Add milestone extensions and overdue escalation.
- [x] Keep PGR assessment separate from taught assessment.

### Programme governance

- [x] Add an initial versioned programme-governance service.
- [x] Complete proposal, business case, validation, amendment and committee flow.
- [x] Add accreditation, regulations, effective year and teach-out plans.
- [x] Bind every student registration to an immutable regulation version.
- [x] Prove historical degree-audit results are stable after curriculum changes.

## Milestone 3 — institutional operations

- [x] Build shared case management for appeals, complaints, misconduct, fitness
  to practise and mitigating circumstances.
- [x] Build controlled student identity correction, merge and merge-reversal.
- [x] Upgrade timetabling to institution-wide constraint optimisation with
  published versions and change control.
- [x] Productise UCAS, HESA/Jisc, SLC, UKVI/CAS, payments, library, VLE, IdP,
  timetable and degree-verification connectors.
- [x] Automate completion-to-alumni transition, access changes, account
  settlement, consent and graduate outcomes.

## Current verification commands

```bash
python -m alembic -c src/education_system/alembic.ini upgrade head
python -m pytest tests/systems/university -m "not slow and not gui"
make lint
make type-check
make coverage-university-core
make architecture-check
```
