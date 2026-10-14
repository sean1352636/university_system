# Changelog

All notable changes to the Education System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Table of Contents

**Version 9.x**

- [Unreleased](#unreleased)
- [9.7.0 — 2026-07-23](#970---2026-07-23)
- [9.6.0 — 2026-07-19](#960---2026-07-19)
- [9.5.0 — 2026-07-18](#950---2026-07-18)
- [9.4.2 — 2026-07-13](#942---2026-07-13)
- [9.4.1 — 2026-07-09](#941---2026-07-09)
- [9.4.0 — 2026-07-06](#940---2026-07-06)
- [9.3.0 — 2026-07-05](#930---2026-07-05)
- [9.2.0 — 2026-07-03](#920---2026-07-03)
- [9.1.0 — 2026-07-02](#910---2026-07-02)
- [9.0.1 — 2026-06-15](#901---2026-06-15)
- [9.0.0 — 2026-06-13](#900---2026-06-13)

**Archived Versions**

- [Version 8.x](docs/changelogs/CHANGELOG-v8.md) (300 releases)
- [Version 7.x](docs/changelogs/CHANGELOG-v7.md) (25 releases)
- [Version 6.x](docs/changelogs/CHANGELOG-v6.md) (29 releases)

**Older Versions**

- [Versions 5.x — 0.x](docs/changelogs/CHANGELOG-v5.md) (298 releases)
- [Module-specific changelogs](docs/changelogs/CHANGELOG-modules.md) (29 entries)
- [Legacy notes & feature documentation](docs/changelogs/CHANGELOG-legacy-notes.md)

---
## [Unreleased]

### Fixed — sixth form → university handover

The two routes into the university from the sixth form (the students-GUI
import picker and the progression bus) contradicted each other and skipped
the controls the handover contract already declared.

- Added `sixth_form.domain.progression.handover_eligibility`: a per-learner
  readiness gate over the same sources the handover payload is built from —
  confirmed destination, accepted offer, discharged offer conditions,
  released results, active handover consent, identity, and whether the
  learner is already a university student. Failures are separated into
  blocking (something the platform can positively disprove) and advisory
  (something it merely cannot confirm), so a college that does not run the
  full UCAS stack can still transfer its leavers.
- The university's sixth-form import picker no longer lists every active
  Year 13 student. It shows each candidate's readiness, refuses a learner
  with a blocking failure, warns on the rest, and requires an explicit
  right-to-study acknowledgement — the one required condition the sixth
  form cannot answer for itself.
- The manual import is now driven by `university_handover.build()` rather
  than an ad-hoc copy of names, gender, DOB and three A-levels, so both
  routes carry the same dataset under the same consent and restricted-field
  rules.
- Medical records no longer cross on a button press. `health.records
  .sixth_form_import` resolves a lawful basis first: recorded handover
  consent releases the full record, an asserted vital-interests basis
  releases only the safety-critical subset, and neither is a refusal. Every
  attempt — including refusals — is written to the platform audit log with
  the basis, the scope and the receiving team.
- The bus intake is idempotent at the journey rather than at
  `(journey_id, external_reference)`, and records a `sixth_form ->
  university` transition for a newly staged applicant, which it previously
  claimed to do and did not.
- `mark_transferred()` records the transition for the home route too;
  before, only leavers going *elsewhere* appeared in their own journey.
- A directly-created student is now bound to any applicant the bus already
  staged for them (`admissions_lifecycle.attach_direct_enrolment`), with the
  bypassed gates named in the status history, instead of leaving one person
  as two unlinked records.
- Added `identity_service.record_transition_once` (retryable flows no longer
  append the same hop repeatedly) and batched cohort lookups
  (`find_by_students`, `find_applications_for_journeys`) so the picker does
  not open one database connection per Year 13 student.

### Added — University Progression dashboards in both systems

The handover fixes above made each step correct one learner at a time.
These make the whole cohort visible at once, which is what results day
actually needs. Both boards are a headless service plus a thin view, so a
CLI or a scheduled job can drive the same operations.

**Sixth form** — `progression.university_progression`, wired into the GUI
as *UCAS & Careers → University Progression*:

- One row per Year 13 leaver: destination, firm-choice course, what is
  outstanding, and a state (`Stranded`, `Blocked`, `Needs attention`,
  `Ready`, `Submitted`, `Enrolled`, `Left the platform`). Trouble sorts
  first — an alphabetical roll is the wrong screen on results day.
- **Stranded leavers appear at all.** A learner marked Left whose
  announcement never landed has dropped out of the enrolled cohort, so no
  cohort query could see them. They are fetched separately and merged in.
- **Prepare handover** is a dry run: it builds exactly the payload that
  would be sent and reports what it contains, what was withheld for want
  of consent, and what the destination's own validator would reject —
  without publishing. Previously the only way to learn what a handover
  contained was to perform it.
- **Submit** still delegates entirely to `mark_transferred()`. A blocked
  learner is refused unless explicitly forced, and a submission whose
  announcement did not land is reported as a failure rather than a
  success with a caveat.
- Bulk submit and retry-stranded report one line per learner, successes
  and validation failures alike; neither stops on the first error.

**University** — `admissions.services.handover_board`, wired into the nav
under *Administration → Admissions & Records*:

- Incoming applicants with their source sixth form, offer and
  qualification status, and the handover fields that did and did not
  arrive — read back off the durable outbox, which is the only record of
  what was actually sent.
- Duplicate-match warnings for the two shapes that produce a second
  student: more than one application on one journey, and a second journey
  holding the same legal name and date of birth.
- **Accept handover** transitions and audits; **Request information**
  raises the missing fields as real `admission_requirements` rows
  (idempotent per field) so the chase holds the enrolment gate closed
  instead of sitting in an inbox; **Complete enrolment** delegates to
  `convert_to_student` and surfaces its refusal reasons rather than
  routing around them. The board never creates a student itself.
- Bulk enrolment converts every applicant that has cleared its gates and
  reports each refusal against the applicant it belongs to.

Supporting changes: `cross_system_bus.events_for_journeys` /
`latest_event_for_journey` (the outbox had no read path),
`sixthform_intake.ensure_schema` (the lifecycle columns are ALTERed on, so
the read-only lookups silently answered "no application" on a database
where the intake had never run).

### Added — UCAS choices pick from the university's course catalogue

A UCAS choice's course name and code were three free-text boxes, and a
hand-typed `"Comp Sci"` / `"CS1"` is a firm choice that matches no
programme when the learner is handed over — `sixthform_intake` and the
import picker both look that code up against the university's catalogue.

- Added `sixth_form.domain.progression.destination_courses`, which reads
  the university's active courses through its own `list_active_courses`
  (so withdrawn courses, duplicate codes and the table's two column
  spellings are handled once, not twice).
- The UCAS choice dialog gains a **"Course at &lt;University&gt;"** dropdown
  above the existing fields. Selecting a course fills the code and the name
  together, and fills the institution if it was blank. Re-opening a saved
  choice pre-selects its course, matching on the code and falling back to
  the course name for rows recorded before the picker existed.
- The UCAS CLI's add/edit flows offer the same catalogue as a numbered
  picker, defaulting to the course already on the record.
- The free-text fields stay. Four of a learner's five choices are at
  institutions this platform does not run, and a sixth form running
  without the university installed gets the dialog it always had rather
  than an empty dropdown.

The ADR 0018 layout is now the active development tree under `program/`.
This release consolidates the multi-system platform, adds canonical university
lifecycles and operational APIs, breaks the largest university modules into
smaller packages while retaining their public import paths, and builds out the
Sixth Form attendance package from lesson registers into a full attendance
operation.

### Added — canonical platform and university lifecycles

- Added application-layer university workflows, boundary errors, degraded-state
  reporting, operational-health checks, event services, a transactional outbox,
  and unit-of-work support.
- Added canonical enrolment, progression, handover and transition contracts for
  cross-system student journeys, backed by adapters and integration-bus jobs.
- Added university lifecycle services for admissions, students, assessment
  boards, finance, programme governance and postgraduate research.
- Added Alembic migrations for canonical university lifecycles, feature-owned
  schemas, institutional operations, admissions policy/consumer receipts and
  the transactional outbox.
- Added institutional and student-lifecycle API routes, including operations,
  submissions, support, fees, graduation, timetabling, connector, identity,
  programme and PGR endpoints.
- Added matching university web pages, shared feature-page assets, journey
  styling/scripts and mobile web assets.

### Added — sixth-form attendance

Forty features taking the Sixth Form attendance package from lesson registers
and reporting to a full attendance operation: 31 new domain modules under
`education_system/systems/sixth_form/domain/academics/attendance/`, reachable
from seven new CLI submenus on the Attendance menu.

- **Capture.** Kiosk and QR self check-in with room-bound devices, revocable
  learner tokens and a tap that returns an outcome rather than raising at a
  doorway. Offline register bundles carrying a digest, with per-learner
  conflict detection on sync and server-wins / device-wins / hold resolution.
  Cover registers with allocation, permission checks and fairness counts.
  Bulk CSV import with dry-run preview, batch tracking and exact rollback.
- **Off-timetable registers.** Tutorial, assembly, enrichment, EPQ supervision
  and supervised-study activities with their own rosters and a `required` flag
  so a voluntary club cannot drag down a reported figure. Work-placement days
  confirmed by the employer supervisor and written through to the college
  register. Exam-room registers with seating plans, the one-hour reportable
  threshold and invigilator sign-off. Emergency roll call over a list frozen
  at the moment the alarm sounds.
- **Absence intake.** An inbound reporting queue for calls and portal
  messages, learner self-certification capped per term, planned-leave requests
  with notice tracking and exam-clash detection, evidence with deadlines that
  revert a mark to unauthorised when unmet, and appeals against a mark routed
  to the tutor.
- **Chasing and communications.** First-day calling with a risk-ordered list
  that skips anything already explained, guardian absence alerts and weekly
  statements queued rather than sent, register nudges escalating teacher →
  head of department → SLT, and threshold-triggered letters issued once per
  stage per year.
- **Intervention.** An escalation ladder with owners and review dates,
  measurable attendance contracts, meeting logs, punctuality tracking counted
  in minutes of teaching lost, persistent- and severe-absence cohorts with
  snapshots and movement between them, a safeguarding bridge raising DSL
  alerts and children-missing-education referrals, 16–19 bursary holds with
  hardship exemptions, and attendance and most-improved awards.
- **Analysis and returns.** Attendance-versus-attainment correlation reported
  with its sample size, subject-level comparison, end-of-year forecast with
  remaining headroom, year-on-year benchmarking, a week × period heatmap,
  marking-anomaly detection, a one-page governor report in text, Markdown or
  JSON, and census/ILR extracts that refuse to export until validation passes.
- **Configuration.** A single threshold table scoped college / year group /
  cohort that every other module reads, and an attendance calendar of terms,
  closures, INSET days, bank holidays and per-year-group study leave, so
  session counts stop approximating term dates.
- Added 31 test files (~914 tests) covering the new modules, and registered
  every new module in the shared attendance test fixture so no test can write
  to the live `sixthform.db`.

### Added — incubating FE college and apprenticeships skeletons

- Relocated the `college_and_apprenticeships` starter scaffold into the
  canonical tree as two incubating system skeletons (stub modules only, not
  wired into the launcher, auth or unified API):
  `education_system/systems/fe_college/` and
  `education_system/systems/apprenticeships/`, each reshaped to the standard
  system layout (`domain/`, `infrastructure/persistence/`,
  `interfaces/{api,cli,gui,portals}/`, `services/`), with placeholder docs
  under `docs/fe_college/`, `docs/apprenticeships/` and
  `docs/reference/college_and_apprenticeships/`, stub scripts under
  `tools/college_and_apprenticeships/`, and stub test modules under
  `tests/systems/{fe_college,apprenticeships}/`.

### Added — university student finance

- Added student-to-student money transfers to the University bank: a Send Money
  dialog in the Student Bank app, an atomic `transfer_student_finance_funds`
  service recording both `transfer_out`/`transfer_in` legs in the unified
  transactions ledger under a shared `TRF-` reference number plus a free-text
  reference (e.g. "Meal out", "Money owed"), a JSON-templated HTML receipt
  emailed to the sender, and an in-app Notifications Hub message delivered to
  the recipient.

### Added — security and operations

- Completed university GUI internationalization by routing remaining static
  widget, window, menu, heading and dialog text through the shared translation
  service with readable, module- and widget-context semantic keys plus English
  fallbacks. Added a repeatable AST audit and migration tool, with regression
  tests, to detect future hardcoded GUI text while leaving SQL, paths,
  identifiers and persisted values unchanged.
- Added generated `gui_auto.json` source catalogs for every installed university
  locale. Their JSON structure follows readable feature, module and widget-role
  namespaces (for example `gui.staff.staff_hr.grievance.labels.status`) rather
  than opaque hash identifiers. Existing human translations remain untouched,
  while new untranslated entries have a version-controlled English baseline.
- Completed the supported GraphQL API alongside REST: Strawberry is now a
  default runtime dependency, the unified server mounts an authenticated
  production endpoint, queries require a caller, mutations enforce staff/admin
  roles, depth and rate controls remain active, canonical databases for all five
  systems are registered, and production startup fails closed if GraphQL cannot
  initialize.
- Completed institution-hosted tamper-evident academic credentials: canonical
  payloads are signed with HMAC-SHA256 using a persistent secret, and the shared
  service now drives GUI, CLI and API issuance, integrity verification,
  verification logging and signed revocation records. Public hash verification
  detects relational or metadata tampering without exposing write operations.
- Added security ports and adapters, sensitive-access controls, secret handling,
  security-training simulations and their email templates.
- Added a modular university authentication implementation covering password,
  MFA, WebAuthn, biometric and federated login; recovery; session management;
  account linking; delegated access; persistence; bootstrap; and immutable audit
  events. Compatibility façades preserve existing authentication imports.
- Added admissions-policy enforcement and receipt tracking, database schema
  version support, feature-owned schema helpers and operational architecture
  checks.
- Added completed-feature, migration, lifecycle, contract, browser, security,
  operational-health and atomic-conversion test coverage.

### Changed — repository and runtime layout

- Promoted `program/` from a migration preview to the canonical source, test,
  documentation and tooling layout. Launchers, Make targets, CI, packaging,
  environment examples and ignore rules now use this structure.
- Consolidated platform code under `education_system/platform`, system-specific
  code under `education_system/systems`, tests under `program/tests`, tools under
  `program/tools`, and runtime data beneath the configured `var` directories.
- Moved the remaining staged `other/` content into its owned `program/`
  packages, repaired imports and removed the obsolete staging locations.
- Updated platform, nursery, sixth-form and university path resolution so
  runtime and repository paths are derived consistently from the canonical
  root.
- Updated the unified server, launcher and top-level entry points for the new
  routing and package boundaries.

### Changed — university module decomposition

- Split all 32 remaining university Python modules at or above 80 KB into
  import-compatible façades, shared module state and bounded implementation
  components. The batch covers commerce and transport GUIs, butcher/barber
  CLIs, database schemas, LMS and academic tooling, advanced search, backup and
  shell administration, research, assessment, early warning, first aid, green
  initiatives and elections. Original callable bodies and public entry points
  are retained while no Python file in the university tree now exceeds 80 KB.
- Split the authentication façade/core, integration bus, university CLI menu
  router and café CLI into focused compatibility façades, services, handlers,
  repositories and supporting modules.
- Split Academic Calendar into a manager package for schema, events, periods,
  exports, maintenance and trips while retaining the original calendar API.
- Split Grade Tracking into focused grade-management modules while retaining
  `grade_manager.py` as the stable entry point.
- Split Church/Community Management, Dentist/Health Portal, Advanced Search
  demographics and Enhanced Reporting dialogs into smaller packages with
  compatibility imports from their original modules.
- Split the Betting Shop GUI into a composed application, shared dependencies,
  tab mixins and payment/receipt services. All 47 original GUI methods remain
  available through `BettingShopGUI` and `launch_betting_shop_gui`.
- Split bakery POS, marketplace, shop-management, document-management,
  plagiarism-search, library, finance and student-analytics responsibilities
  into smaller helpers where appropriate.
- Removed duplicate implementations exposed during the package moves and made
  canonical modules the single source of behaviour.

### Changed — university domains and integrations

- Reworked the café domain into models, persistence repositories, integrations
  and services for checkout, inventory, loyalty, menus, permissions, reporting,
  reservations, scheduling and suppliers.
- Reworked dental services into models, persistence, finance/email integrations
  and focused appointment, patient, payment, prescription, refund, reporting and
  treatment services.
- Reworked health records around explicit models, permissions and services, with
  focused contacts, vaccination and reporting packages and updated health-portal
  integration.
- Reworked Student Union events into domain, application, infrastructure and
  reporting layers covering attendance, registration, ticketing, finance,
  recurrence, sustainability and virtual events.
- Updated admissions, finance, safeguarding, campus operations, certificates,
  messaging, analytics and data export to use the new platform boundaries and
  shared infrastructure.

### Changed — sixth-form attendance core

- **`save_register` and `update_record` now enforce a retro-marking window.**
  Inside it nothing changes; past it a write needs a `reason`; past the
  cutoff it is refused. Both gained `allow_retro` for deliberate backfills,
  and every use is written to an override log with the actor who forced it.
  The curated amendment paths — authorising, unauthorising, recoding,
  off-site marking — pass it and so still reach a mark of any age, which is
  the point: after the window shuts they are the only way in. A save landing
  outside the window is now written to the amendment trail whether or not the
  register was ever submitted.
- **Timetable expansion honours an A/B week cycle.**
  `attendance_sessions.expected_lessons`,
  `attendance_register.unsubmitted_registers` and `mark_range` now drop slots
  that do not run in a given date's week. A college with no cycle configured
  gets exactly the answers it did before — an unconfigured system is a
  one-week system.
- `mark_range` gained `skipped_closed`, naming the dates the retro-marking
  window has closed rather than failing the whole batch, and `mark_all`,
  `mark_by_key` and `copy_previous_register` now carry a `reason` through to
  the save.
- Arrival and departure stamps go through the same window check: a clock time
  typed six weeks later is a reconstruction, not an observation.
- Added `cover` to `attendance_codes.DATA_SOURCES`, so marks taken by
  somebody who does not know the class stay distinguishable from the rest.

### Changed — documentation and verification

- Added the canonical data dictionary, scope/ownership guide, modernisation task
  list, module-classification data, platform overview documents and supporting
  documentation assets.
- Updated ADR 0018 and the university documentation for the implemented layout
  and ownership model.
- Updated launcher, migration, integration, health, admissions, academic
  calendar, event-management and path tests for the canonical imports and new
  service boundaries.
- Expanded CI and project configuration for architecture checks, migrations,
  security workflows and the reorganised test suite.

### Fixed

- **Primary school CLI dispatch was failing for every label.**
  `primarysch_system/cli_main.py` imported
  `…modules.domain.operations.staff_hr`, which does not exist — the module is
  `…modules.domain.staff_hr`, with no `operations` segment. The bad import sat
  at line 162 of a `try:` block spanning lines 97–324 that holds 102 imports and
  ends in `except Exception`, so the `ModuleNotFoundError` aborted the
  **41 imports after it and the entire dispatch body**, logging an exception on
  every call. `gui_main.py` carried the same typo, breaking the staff-HR view.
  Six references corrected across four files; all 102 imports in the block now
  resolve.

### Fixed — layout migration follow-ups

- **The `platform` stdlib collision is gone, without renaming the package.** The
  university conftest added `education_system/` to `sys.path`, which made
  `education_system/platform/` importable as top-level `platform` and displaced
  the standard library module. That hack existed only for bare imports like
  `from core.paths import ...`; with those fully qualified, the `sys.path.insert`
  was removed and the collision disappeared. No naming decision needed.
- **Bare top-level imports eliminated.** Eight `from core...` imports plus
  `from infrastructure...` in `admin_tools_gui.py` now use the full package path,
  in both the live tree and `program/`. These resolved only when the system
  directory happened to be on `sys.path`.
- **The 15 files referencing relocated code repointed.**
  `systems.university.scripts` → `tools.university`, and
  `systems.university.tests.{run_all_tests,generate_test_report}` →
  `tests.systems.university._support.*`, matching where the migration puts them.
- **`infrastructure/paths.py` now writes to `var/`.** `DATA_DIR`, `LOG_DIR` and
  `BACKUP_DIR` resolve to `var/{data,logs,backups}/university` at the repository
  root instead of inside the package, and `REPO_ROOT` points at the actual
  repository root rather than being an alias for the package directory.
- **Root `docs/` links repointed at `docs/`** — 30 lines across
  `README.md` and `CHANGELOG.md`; all link targets verified to exist.

### Performance — Grade Tracking GUI opens faster

- **Opening Grade Tracking no longer loads the data-science stack.** 14 files in
  `academics/interfaces/gui/grade_tracking/` carried the same copy-pasted
  header importing numpy, `scipy.stats`, pandas, matplotlib/pyplot, seaborn and
  reportlab at module level. The launch buttons import the app on click, so
  every open paid for all of it. With the main university GUI already loaded,
  the import went from **5.8s to 0.21s**, and none of those libraries load
  until they are used.
- The unused block was removed from 12 files (`grade_tracking_app.py`,
  `grades/__init__.py`, `layout_manager.py`, `student_manager.py`,
  `module_manager.py`, `assessment_manager.py` and the six `dialogs/`).
  Each was checked with an AST scan: none reads any of the imported names.
- `analytics_manager/reports.py` now loads matplotlib when a chart is opened
  (`_load_matplotlib()`, still selecting the `TkAgg` backend), and the transcript
  PDF export and `analytics_manager/exports.py` import reportlab inside the
  export. The first chart in a session takes about 2s to appear; the
  "not installed" messages are unchanged.

### Fixed — Grade Tracking and Degree Audit

- **Risk model crashed when attendance or submissions were unavailable.**
  `grade_tracking/analytics_manager/predictions.py` called `logger.debug` in
  those fallback paths without ever defining `logger`, turning a handled query
  failure into a `NameError`. The module logger is now defined.
- **Degree Audit failed to open its course lists.** `load_courses()` still set
  `grad_program_combo`, which Degree Audit no longer builds since the
  graduation audit moved to the Graduation GUI, so every open showed "Failed to
  load courses: 'DegreeAuditGUI' object has no attribute 'grad_program_combo'".
  It now fills whichever programme combos the window has, which also keeps the
  Graduation GUI's headless graduation tab working.
- **The programme list offered only CS and DS.** Students on any of the other
  programmes could not select their own course, and the autofill never matched.
  The list is now every active course that has modules tagged to it.
- **Degree Progress showed 0 credits and a 0.00 GPA for students with marks.**
  `degree_audit/progress.py` read only `student_modules`, but Grade Tracking
  records final marks in `module_grades` and leaves the enrolment row
  'Enrolled' with no grade. The seeded modules also carry `credits = 0`.
  - A new `module_progress()` builds one row per module, merging the latest
    `module_grades` mark. A passing final grade earns the module whatever the
    enrolment row says. `earned_progress()` totals those rows and returns the
    same keys, so the graduation eligibility check and What-if analysis pick up
    the fix too.
  - A module with no credit value takes the programme requirement split across
    the programme's modules (360 over 18 = 20), the rule Academic Progress
    already uses.
  - `required_credits_for_course()` now prefers `degree_programs`, then
    `courses.credits`, then `credit_hours`. ACC carries credits 360 but
    credit_hours 400, so it had been reporting a 400-credit requirement.
  - The Degree Progress module table uses the same rows, so a marked module
    shows its grade, credits and 'Completed' instead of
    'Enrolled / 0 / Not Graded'.
  - Checked read-only against the live database: student 5189930 now reads 20
    credits earned (1 of 18 modules marked), GPA 4.00, 360 required, 5.6%
    complete.
- **What-if analysis reported 0 modules on every target programme.** It counted
  `modules` rows whose `module_type` equalled the programme code, but
  `module_type` holds 'Core' / 'Elective'. It now counts the programme's active
  modules by `modules.course` (18 for ACC and CS). The "modules that carry
  across" table reads through `module_progress()`, so a module marked in Grade
  Tracking shows its grade and 'Completed' instead of 'Not graded'.
- **What-if credited every earned credit toward any target programme.** The
  "Credits earned", "Still to earn" and "Toward the target" figures used the
  student's total, so switching to an unrelated programme claimed credit for
  modules the same window listed as not carrying across. They now count only
  passed modules that belong to the target, each valued at its own credits or,
  when it records none, the target programme's per-module share. The stat is
  relabelled "Credits carried across".

---

## [9.7.0] — 2026-07-23

Stabilisation and hardening pass driven by the education-system refactoring
plan, spanning security, testing, CI, packaging, dependencies and code quality.
No feature work — the focus is making the project safe to run, portable to
install, consistently tested across all five systems, and honest in its docs.

### Security — access-control gaps closed

- **Two privilege-escalation gaps in API role enforcement fixed.** Path-scoped
  role checks key off the `<system>` segment of `/api/v1/<system>/…`, but the
  set of recognised systems (`_KNOWN_SYSTEMS`) omitted **nursery**, and
  **sixth-form** routes mount under `/api/v1/sixthform/` while auth keys them
  `college`. In both cases the route read as *unscoped*, so `role_required`/
  `token_required` fell back to the user's best cross-system role — letting an
  admin on any system pass an admin-gated nursery/sixth-form route. Added
  `nursery` to the set and a `sixthform → college` path alias, with regression
  tests (`test_permission_isolation.py`).
- **Static-file exposure removed.** `run.py --web` served the repository root,
  exposing raw `auth.db` / `audit.db` / `student_records.db` over HTTP; it now
  serves only the selected system's `web/` directory. Removed the
  `university.html` "download auth.db / records DB" links and hardcoded DB path.
- **CORS no longer wildcarded.** `--web` pins CORS to the exact static-server
  origin; the unified server refuses to start with `API_CORS_ORIGINS=*` and now
  also requires a persistent `API_SECRET_KEY` in production (matching
  `JWT_SECRET_KEY`).
- **Forced password change for demo accounts.** New `must_change_password` flag
  (with migration) is seeded on the demo accounts and surfaced by login / the
  API; CLI and GUI login gates force a reset before first use.
- **GDPR Subject Access Report was silently incomplete.** Its report loop used a
  hardcoded four-system tuple that omitted nursery and used `secondary` where
  data is keyed `school`, dropping both from every SAR; now driven by the
  canonical `SYSTEM_ORDER`.
- Rate-limited `/mfa/verify`; recovery-code-in-password login kept as a guarded
  break-glass path but made opt-out via `EDU_DISABLE_RECOVERY_CODE_LOGIN=1`.

### Added — testing & CI

- **CI workflow** (`.github/workflows/ci.yml`): lint, security scan, tests
  (matrix Python 3.11/3.12), a per-system job that fails if any of the five
  systems has no runnable tests, package build + installed console-command
  smoke, offline docs-link check, a separate slow/integration job, and a single
  `ci-success` gate. Dependency caching throughout.
- **All five systems now in the test suite** (`testpaths` + Makefile `TESTS`).
  Added per-system smoke tests (import → temp-dir isolation → API-blueprint
  registration → auth-required check), a schema-migration test, and password-
  reset-token expiry/single-use tests. Separate coverage targets for shared/core
  vs. legacy code (`make coverage-shared`, `make coverage-percent`).

### Changed — packaging & dependencies

- **Portable install.** Makefile no longer hardcodes a developer venv path
  (`PYTHON ?= python`); `pyproject.toml` gained real `[project.urls]`, a
  `py-modules = ["run"]` entry so the `education-system` console script works
  after install, and the last machine-specific `sys.path` hack was removed.
  Added `.env.example`.
- **Dependency split.** Minimal default runtime + optional extras
  (`dev`/`test`/`security`/`perf`/`graphql`/`realtime`/`postgres`/`mysql`/`ai`/
  per-provider `cloud-*`/`integrations`/`remote`/`docs`/`viz`).
  `requirements.txt` is now a pure runtime lock; dev/CI tooling moved to
  `requirements-dev.txt`. **plotly** moved to the `viz` extra (imported only
  lazily; now guarded with an "install `[viz]`" message).
- **Fail-closed migrations.** A genuine Alembic upgrade failure now aborts
  startup instead of only warning (`EDU_ALLOW_SCHEMA_DRIFT=1` to override).
- **Lint.** Re-enabled Ruff `F821` (undefined names) — which caught and fixed 10
  real bugs (stranded imports after `return` causing `NameError`; missing
  `from typing import Any`); narrowed the blanket test-file `E`/`F` ignore so
  real defects surface in tests.
- Version corrected to `9.7.0` across `pyproject.toml`, and the package
  description now lists all five systems including Nursery.

### Removed

- Unused dependencies **fpdf2** and **recurring-ical-events** (zero references).
- Dead module `parking_compatibility.py` (504 lines; all exports referenced
  nowhere) and other dead scientific/compat imports.
- Tracked runtime SQLite `-wal`/`-shm` sidecar files (now git-ignored, alongside
  Python build artifacts).

## [9.6.0] — 2026-07-19

Staff HR fixes and cross-system reconciliation of the two staff lists. Several
Staff HR GUI areas (Reports, Directory search, staff profiles) queried the DB
correctly but joined incompatible `user_id` key styles or the wrong table, so
live data never surfaced. Staff identity (name/email) lives in the shared
`auth.db` while HR records live in `staff_profiles`, and the two were never
bridged — this release wires them together and makes account-less HR staff
visible in the main GUI's staff list.

### Fixed — Staff HR reports read live data

- **Attendance Report** (`TimeManager.get_attendance_report`) was built
  `FROM staff_profiles` and joined time entries on `p.user_id = te.user_id`,
  but `staff_profiles.user_id` stores the **username** while
  `time_entries.user_id` stores the **numeric `users.id`** — so the join never
  matched and every staff row showed 0 days. Rebuilt to run `FROM time_entries`
  (so anyone who clocked in appears, incl. users without a profile) and to
  bridge the two id styles via the `users` table for department resolution.
  Also fixed a wrong `users` join (`p.user_id = u.id`, username vs. id).
- **Leave Usage Summary** (`LeaveManager.get_leave_summary`) had the same
  username-vs-numeric-id mismatch joining `leave_balances` to `staff_profiles`;
  now bridged via `users` so departments resolve once balances exist.

### Fixed — Staff Directory search shows staff that exist in the DB

- Staff names/emails live in the shared `auth.db` (`users.display_name` /
  `email`), but `DirectoryManager` only joined the local university `users`
  table, which has no rows for most staff — so search results showed blank
  Name/Email and searching by a real name returned nothing.
  - Added `_enrich_identities()` to fill missing name/email from `auth.db`
    (best-effort; never raises), applied to `search_directory`,
    `get_department_staff`, and `get_staff_profile`.
  - Added `_usernames_matching()` and wired it into `search_directory` so a
    search by real name or email also matches (previously only the username /
    local columns were searched).
  - `get_staff_profile` now aliases `job_title` / `office_location` /
    `phone_extension` to the `position` / `office` / `phone` keys the GUI
    reads, so the profile dialog and My Profile tab populate.
- **Profile dialog crash fixed**: office-hours methods queried a non-existent
  `staff_office_hours` table; corrected to `staff_office_hours_directory` (the
  actual table, matching columns) across INSERT/SELECT/UPDATE/DELETE, so
  double-clicking a staff member and managing office hours no longer errors.

### Changed — Main GUI "View Staff Members" includes HR-profile staff

The main GUI's staff screen listed only `users` rows with a staff/instructor/
admin role (8 people), while the Staff HR Directory listed `staff_profiles`
(15) — the two shared a single record. "View Staff Members" now also shows HR
staff who have a profile but no local login account.

- New `_fetch_hr_profile_staff()` reads `staff_profiles`, resolves name/email
  from `auth.db`, de-duplicates against accounts already listed, and honours
  the search box (username, name, email, department).
- Appended rows are tagged/tinted and marked **"HR Profile"** with their job
  title as the role. Because they have no `users.id`, Edit/Delete are guarded
  with a message directing to Staff HR → Directory instead of failing silently;
  View Details still works.

## [9.5.0] — 2026-07-18

Built out the university system's Analytics module into a full institutional
analytics capability across all interfaces (service, CLI, GUI, REST API,
OpenAPI), reorganised the main GUI sidebar to separate non-university
"town/lifestyle" services into a dedicated pop-out window, and extracted the
timetable feature out of the Module Scheduling GUI into a standalone,
main-GUI-launchable Timetable Manager.

### Added — Institutional Analytics module

A new `institutional_analytics` sub-module under
`modules/domain/analytics/` that *computes* institution-wide metrics on
demand from the operational tables (`students`, `student_modules`,
`courses`, `payments`, `student_fees`, `student_finance_accounts`) —
complementing the existing `kpi_dashboard`, which only replays pre-recorded
KPI rows. All reads are non-destructive aggregate queries (no DDL, no writes).

- **Service** (`InstitutionalAnalyticsService`) with six analytics sections
  plus a combined overview:
  - **Enrolment** — head-count, current/completed/attrition split, by course.
  - **Retention** — retention / attrition / completion rates, overall and per
    course.
  - **Module performance** — per-module enrolment, pass rate and in-progress
    counts, with UK-grade + numeric-grade classification.
  - **Course capacity** — fill rate vs capacity, courses at capacity.
  - **Financial** — collected revenue by method/month, outstanding vs waived
    fees, account balances.
  - **Demographics** — gender split with age / UCAS-tariff / GPA summaries.
  - **Overview** — headline figures across every section; a section whose
    source table is absent is reported under `errors` rather than sinking the
    whole response.
- **Schema-tolerant and case-normalising**: every section guards on table /
  column presence and degrades gracefully; free-text statuses are normalised
  so `Active`/`active` and `Graduated`/`graduated` (and `Card`/`card`) no
  longer fragment counts.
- **CLI** — "Institutional Analytics" menu under NEW FEATURES in the launcher
  (`menu_router.py`), 7 options mirroring the service sections.
- **GUI** — tabbed Tk pop-out with a headline KPI strip, wired as a button
  under Analytics & Reporting in the main GUI.
- **REST API** — 7 read-only endpoints under `/api/analytics/*` (`overview`,
  `enrollment`, `retention`, `modules`, `capacity`, `finance`,
  `demographics`), registered on the unified university API. Gated with
  `@token_required` plus a `staff_only` check that returns **403** for the
  `student` role, since the data spans finance and whole cohorts.
- **OpenAPI** — documented all 7 endpoints (with the `modules` `limit` query
  param and the 403 response) under a new "Institutional Analytics" tag in
  `openapi_spec.py`, so they render in the Swagger UI.
- **Tests** — 14 service tests + 10 API route tests, covering the metric
  maths, case-normalisation, graceful degradation, and the role gate.

### Changed — Main GUI: non-university services moved to an "Other" window

The main GUI sidebar mixed genuine university functions with commercial
"town/lifestyle" simulations (shops, cafés, cinema, betting, taxi, etc.). A
new **🛒 Other** entry now collects these, keeping the core university
navigation focused.

- **New "🛒 Other" group**, pinned to the **very bottom** of the sidebar.
- Whole non-university categories moved out of "Campus Life" into it: Dining &
  Food, Shops & Retail, Personal Services, Entertainment, and Community.
- Mixed categories were **split** so the university functions stay put: `taxi`
  / `train` / `car rental` move to Other (Transport) while `parking` and
  `trips` remain under Campus Life; `gym` moves out of Health; `police_station`
  moves out of Security — grouped under a "Leisure & Civic" tab in Other.
- Unlike every other sidebar group (which expands inline), "Other" **opens a
  separate pop-out window** using a **balanced multi-column grid** (up to 3
  columns, sections greedily packed into the shortest column). Re-opening
  focuses the existing window; all buttons keep their right-click
  pin-to-sidebar affordance and remain reachable via Ctrl+K search.

### Changed — Timetable feature extracted into a standalone Timetable Manager

The timetable code was tangled inside the Module Scheduling GUI's "Timetables"
tab (`gui/module_scheduling/timetables_tab.py`) as monkeypatched
`ModuleSchedulingGUI` methods. It now lives in its own module and window.

- **New `academics/gui/timetable_management.py`** with a self-contained
  `TimetableManagementGUI` window: generate / display / email / export student
  & instructor timetables and the conflict view.
- **Launchable from the main GUI** via a new "Timetable Manager" sidebar button
  (under Scheduling), gated to instructor/staff/admin roles.
- **Module Scheduling GUI's Timetables tab is now a thin launcher** — just
  buttons that open the standalone window. Shared helpers that other tabs
  depend on (`_select_module_dialog`, `view_calendar`, `show_grid_view`,
  `_show_drag_drop_grid`) were deliberately kept on `ModuleSchedulingGUI`.
- **Single source of truth for schedule data**: the two duplicated
  `_get_*_schedule_data` implementations were collapsed into module-level
  `get_student_schedule_data` / `get_instructor_schedule_data` helpers (now
  imported by `exports.py` and `instructors_tab.py`). Both filter to
  `status='published'`, fixing an inconsistency where the on-screen/emailed
  timetable included draft schedule rows that exports correctly excluded.

## [9.4.2] — 2026-07-13

Bug fixes for the university system's Assignment Manager — saving/loading
templates and drafts was broken by a schema mismatch and an invalid dialog
argument.

### Fixed — Assignment templates and drafts save/load again

The Assignment Manager's template and draft operations all failed against an
existing `student_records.db`:

- **`no such column: draft_name`** (load) and **`table assignment_drafts has no
  column named draft_name`** (save draft). The `assignment_drafts` table was
  first created by the assignments service (`crud.py`) *without* a `draft_name`
  column, so the GUI's `CREATE TABLE IF NOT EXISTS` was a silent no-op and every
  `draft_name` reference failed. A new `_ensure_drafts_schema` helper now creates
  the table and runs `ALTER TABLE … ADD COLUMN draft_name` to migrate legacy
  tables in place; the load query uses `COALESCE(draft_name, 'Draft #' || id)` so
  service-created rows (which leave the name NULL) still display. `crud.py` now
  creates the table with `draft_name` and the same migration, so both writers
  converge on one schema regardless of which runs first.
- **`_QueryDialog.__init__() got an unexpected keyword argument 'initialfile'`**
  (save template). `simpledialog.askstring` takes `initialvalue`, not the
  file-dialog `initialfile` kwarg; fixed, with an explicit `simpledialog` import.
- A latent NOT NULL failure: the legacy table's `created_at` is `TEXT NOT NULL`
  with no default, but the GUI INSERTs omitted it. Both INSERTs now supply
  `created_at` explicitly.

## [9.4.1] — 2026-07-09

Bug fixes and startup-performance work for the university system's Course
Planning Assistant, plus two noisy startup log issues in the academic calendar.

### Fixed — Course Planning: created plans and added courses now appear

Creating a plan from the Course Planning GUI appeared to do nothing: the create
handler only refreshed the Dashboard listbox, never making the new plan current
or re-rendering the Semester Planner tab, so a user creating from the planner's
empty state was returned to that same "No plan loaded" screen. A new shared
`_activate_plan` helper now sets the plan active, loads it, updates the header,
renders the planner and switches to that tab; it is wired into both the create
and auto-generate flows. A freshly created (empty) plan previously rendered a
blank tab — `_display_planner_content` now shows a "no courses yet — add one"
prompt for a loaded-but-empty plan.

`get_semester_plan` inner-joined `planned_courses.course_id` to `courses.code`,
which silently dropped every course added from the Add Course dialog, since that
dialog stores **module** codes (e.g. `CIS0001`) that live in the `modules`
table, not `courses`. The query now LEFT JOINs both tables and COALESCEs the
name/credits/department, so both course- and module-based rows display.

### Performance — Course Planning GUI opens faster

Opening the GUI reopened a fresh SQLite connection per query, each paying ~100ms
(schema-parse on first access plus a WAL checkpoint on close) against
`student_records.db`. Reduced the connection churn on the open path:

- The window keeps one reusable read connection for its lifetime; the three hot
  `PlanningService` read methods take an optional `conn=` so callers can share
  it (4 reads: ~433ms → ~1ms).
- The plan list is memoized per screen instead of being refetched by the
  dashboard, planner and load/duplicate/delete flows separately.
- Prerequisites, Recommendations, Conflicts and Tools tabs are built lazily on
  first view rather than eagerly at open (keeps the Tools tab's DB queries off
  the open path).
- `PlanningService._ensure_tables_exist` is guarded by a per-process
  `_schema_ready` set so it no longer re-runs ~160ms of schema DDL on every
  construction.

### Fixed — academic-calendar startup noise

- The sidebar button style used `focuscolor='none'`, which is not a valid Tk
  colour and produced `Tk background error: unknown color name "none"` on every
  render; it now uses the button background colour so the focus ring stays
  invisible.
- `MobileAPIManager` built a Flask app and evaluated CORS in its constructor,
  emitting `CORS_ALLOWED_ORIGINS is not set and APP_ENV=production …` at every
  launch for an API server that is never actually served. The Flask app is now
  built lazily on first access to `.app`, so startup is quiet and the
  (legitimate) CORS warning only fires if the mobile API is genuinely used.


## [9.4.0] — 2026-07-06

Adds four new post-16 / post-18 systems — a **Playgroup (Early Years, 2–3)**
setting, a **College (Further Education)**, **Apprenticeships**, and **Higher &
Degree Apprenticeships** — each a launcher-integrated system with a GUI and CLI
dashboard, shared-auth login accounts, a superadmin-dashboard presence, and a
SQLite database with a per-feature module scaffold. Also fixes a GUI→CLI logout
routing bug and a spurious first-login password reset on seeded accounts.

### Added — Playgroup (Early Years, ages 2–3)

Retargeted the standalone EYFS desktop app into a 2–3 playgroup system under
`education_system/early_years/`. The end-of-Reception EYFS Profile / Early
Learning Goals / Good Level of Development (age-5 assessments) were removed in
favour of the statutory **Progress Check at Age Two** across the three prime
areas; age bands were restricted to the two relevant to under-3s, and children
are flagged Due / Overdue for their two-year check. The interface was rebuilt
from tabs into the shared button-driven layout (header · left-nav accordion ·
content · status bar) used by the other systems, a matching CLI was added, and
both were wired into the launcher (system key `playgroup`) with
`playadmin` / `playstaff` accounts and role-gated record deletion. Fifty
planned-feature module folders were scaffolded under `modules/domain/`.

### Added — College (Further Education)

New `post_16/college/` system (key `fecollege`): a button-driven FE-college
dashboard (GUI + CLI sharing one menu) covering learners, curriculum
(BTEC / T-Levels / GCSE resits), apprenticeships, assessment, progression, and
ESFA funding / compliance. Backed by a new `fecollege.db` (students, staff,
courses, enrolments, attendance, apprenticeships) and a 43-folder per-feature
module scaffold. Login accounts `fecadmin` / `fecstaff` / `fecstudent`.

### Added — Apprenticeships (post-16)

New `post_16/apprenticeship/` system (key `apprenticeship`): a
work-based-learning dashboard (GUI + CLI) covering apprentices, employers &
providers, standards & training (off-the-job 20%, KSBs, functional skills),
12-weekly reviews, Gateway & End-Point Assessment, and levy / ESFA / ILR
funding. Backed by `apprenticeship.db` (apprentices, staff, employers,
providers, standards, reviews, off_the_job_log, epa_records) and a 38-folder
module scaffold. Accounts `appadmin` / `appstaff` / `appstudent`.

### Added — Higher & Degree Apprenticeships (post-18)

New `post_18/higher_apprenticeship/` system (key `higherapprenticeship`): a
Levels 4–7 dashboard (GUI + CLI) covering degree-apprenticeship standards,
modules & credits, tripartite reviews, integrated EPA & degree classification,
and OfS / QAA / levy compliance. Backed by `higher_apprenticeship.db`
(apprentices, staff, employers, standards, modules, reviews, off_the_job_log,
epa_records) and a 46-folder module scaffold. Accounts
`haadmin` / `hastaff` / `hastudent`.

### Added — launcher, login & superadmin integration

Each new system is wired through the same points as the existing systems:

- Shared-auth `SYSTEMS` display names and default admin / staff / (student)
  accounts; the `superadmin` account gains admin access to all four. Accounts
  log straight in (see the password-reset fix below).
- Launcher dispatch (`launcher/systems.py` — `LAUNCHERS` +
  `AUTH_GUI/CLI_SYSTEMS`), role picker (`roles.py`), interactive system menu
  (`launcher/menus.py`), and `run.py` direct-launch flags (`--playgroup`,
  `--fecollege`, `--apprenticeship`, `--higher-apprenticeship`).
- Superadmin dashboard (`shared/gui/superadmin_dashboard.py`): launch tiles,
  the user-roles matrix column, and the colours / labels / order constants; plus
  the superadmin CLI (`shared/cli/superadmin_cli.py`) system list.
- Cross-system DB registry (`shared/database/paths.py`) and the admin-service
  health panel (`shared/admin_portal/admin_service.py`), which counts each
  system's learner table (`children` / `pupils` / `students` / `apprentices`)
  so the new systems appear as *online* with a live headcount. (The FE-college
  dashboard was initially added without a DB and later given one.)

### Fixed — GUI→CLI logout returned to the GUI login

Choosing "Switch to CLI" from any system's GUI ran the CLI inside the GUI
dispatch loop, so a subsequent logout was handled by `dispatch_gui` and always
reopened the **GUI** login. `dispatch_gui` / `dispatch_cli` now hand off to each
other whenever a switch flips the interface mode, so the CLI's login (and the
GUI's, in the mirror case) is used on the next logout. Covered by a new
regression test in `test_launcher.py`.

### Fixed — seeded accounts forced a password reset on first login

`_create_default_user` didn't set `password_changed_at`, so newly-seeded demo
accounts were treated as "never set = expired" and hit the mandatory
password-change screen on first login. It now stamps `password_changed_at` at
creation (matching the older accounts), so seeded accounts log straight in;
age-based expiry and admin-triggered resets are unchanged. The launcher
contract test's `AUTH_GUI/CLI_SYSTEMS` expectation was updated to the full set
of systems.


## [9.3.0] — 2026-07-05

University-system CLI ↔ GUI parity pass: the Facilities CLI is now a real,
working interface instead of a placeholder, gym check-out and event
creation are reachable from the GUI, and three pieces of orphaned/duplicate
code were removed.

### Added — Facilities & Space Management CLI

``campus/facilities/`` previously had a CLI menu whose every option just
printed "Feature available via Facilities managers" and did nothing. It now
delegates to a real interactive CLI (``facilities/cli/facilities_cli.py``)
wired to the service managers, which read/write the same
``student_records.db`` the Facilities GUI uses — so records created in one
front-end appear in the other. Nine areas are covered: Building Management
(buildings + rooms), Room Bookings (with conflict checking + cancel),
Maintenance Requests, Work Orders, Asset Inventory, Energy Usage Tracking,
Space Utilization Reports (occupancy + cleaning schedules), **Access
Cards**, and **Inspections**.

To back the CLI, the service layer (``facilities_management_core.py``)
gained list/read/update methods on the existing managers plus three new
managers: ``EnergyUsageManager``, ``AccessCardManager`` and
``InspectionManager``.

### Added — Admissions & Recruitment CRM CLI

Like Facilities, ``admissions``'s ``display_admissions_crm_menu`` was a
placeholder printing "Feature available via Admissions managers". It now
delegates to a real interactive CLI
(``admissions/cli/admissions_crm_cli.py``) wired to the CRM managers on the
shared ``student_records.db``. Seven areas: Prospects (list/add/view +
interactions/status/log), Applications (list/submit/view/status/decision),
Review Workflow (assign/review/view), Document Management, Recruitment
Campaigns (list/create/send), Campus Tours (list/schedule/register/view
registrations), and Yield Prediction Analytics. Backing this, the service
managers gained the read methods they were missing (``list_prospects``,
``list_applications``, ``list_campaigns``, ``list_tours``,
``list_predictions``, etc.).

### Fixed — schema-drift bugs surfaced during the parity work

Several staff_hr/achievement features raised `NOT NULL` / "no such column"
errors at runtime because the live DB schema had drifted from the code. Each
fix updates the schema definition **and** adds an idempotent, self-healing
migration (guarded by `PRAGMA table_info`; table rebuilds preserve rows) that
runs at `init_staff_hr_schemas()`, so both existing and fresh databases are
corrected.

- **Table-name collisions** — `student_badges` (achievement_badges vs
  student_union) and `peer_review_assignments` (staff_hr vs the academics
  assignment_system) each had two `CREATE TABLE IF NOT EXISTS` definitions with
  different schemas; the "other" module's table won, breaking the second. Moved
  achievement_badges onto its own `achievement_student_badges` table and
  renamed staff_hr's to `hr_peer_review_assignments` (academics tables
  untouched).
- **Bad NOT NULL constraints** — `sabbatical_approvals.approver_id`,
  `travel_approvals.approver_id`, `programme_approvals.reviewer_id` were
  `NOT NULL`, but approval rows are created at submit-time before an approver
  exists → made nullable (rebuild-migrate).
- **Missing columns** — added `updated_at` to `grant_budget_categories` /
  `grant_budget_transfers`, and `user_id` + `updated_at` to
  `faculty_schedule_templates` (also relaxed its legacy `created_by NOT NULL`).

Two further pre-existing issues (originally flagged out-of-scope) were then
also fixed:
- **Grant child-tables FK** — `grant_budget_allocations` / `grant_expense_items`
  / `grant_funding_alerts` / `grant_budget_transfers` declared their FK as
  `REFERENCES grant_applications(grant_application_id)`, but that column doesn't
  exist (the PK is `application_id`). Corrected the referenced column in the
  schema definitions (a fresh DB would otherwise reject every child insert with
  "foreign key mismatch"; the live DB already had the correct FK).
- **Seed-ordering crash on an empty DB** — `init_staff_hr_schemas()` aborted on
  a truly fresh database because several `_init_*` modules seeded reference
  tables owned by later-running modules. Two more dead `return True` statements
  (in the governance and workload inits) left `comm_hub_forums` uncreated and a
  commit unreachable; the default grant-category and forum seeds were moved to
  their owning modules (finance / governance), and the academic
  `schedule_activity_types` / `tax_brackets` seeds were guarded to match the
  existing core convention. A full init on an empty DB now completes and every
  reference table populates.

Also fixed three latent bugs found along the way: two premature `return True`
statements that made whole blocks of staff_hr `CREATE TABLE` calls dead code
(mentoring / peer-review / grant / payroll / travel tables were never created
in a fresh DB), and a `curriculum_manager` insert into a nonexistent
`submitted_by` column. (Two further pre-existing issues — a grant-tables FK
referencing a nonexistent `grant_applications` column, and a seed-ordering
deadlock on a truly empty DB — are noted but out of scope.)

### Added — many small CLI↔GUI parity deltas (P3)

After a verify-first pass (much of the audit was already closed), filled the
genuine minor gaps, each wired to the existing service the counterpart uses:
- **Academics** — academic_progress GUI (Progress Analytics, Comprehensive
  Report); study_matching GUI (Pomodoro timer, Q&A voting); tutor_groups GUI
  (member/meeting/pastoral lists + record meeting); ai_study GUI (Complete
  Task, Explanation History, Rate); plus two-way deltas on external_examiners,
  curriculum_specification, clearing_adjustment, mitigating_circumstances.
- **Campus** — equipment GUI (Refund Deposit, View Transactions, filter by
  status); parking CLI (wired the existing analytics dashboard, manual backup,
  refund); trips CLI (itinerary, expenses); housing CLI (Outstanding Balances).
- **Commerce / analytics** — marketplace (My Reviews + Statistics in GUI,
  photo attach in CLI); kpi_dashboard GUI (View KPI Detail, List Dashboards).
- **student_affairs** — GUI: achievement_badges (Progress/Statistics),
  employer_portal (Update Employer), social_matching (Update Interest Level),
  wellness (Check-in, Comprehensive Report), documentation (Revoke); CLI:
  portfolio (Delete/Edit item, Endorsement detail), documentation (Save-as-txt).
- **Portals** — added sidebar buttons (Academic Progress, Course Catalog, TA
  Management, Course Planning, Grocery Shop, To-Do) wiring the role portals to
  existing feature launchers.
- **Reporting (shared)** — CLI `export_to_json` + a Scheduled Reports menu.

Deferred as larger-than-delta: a Transfer-Credits GUI (no GUI exists at all),
the housing accommodation-registry subsystem → GUI, and research/grants
cross-porting (CLI and GUI run on separate backends).

### Added — CLIs for eight more GUI-only modules

Eight previously GUI-only modules gained text CLIs, wired into the main CLI
menu; each shares the same DB its GUI uses:

- **Finance** — `run_bank_rec_menu` (bank reconciliation: import / match /
  unmatch / discard), `run_ledger_menu` (trial balance, journals, period
  close/reopen/lock), `run_statements_menu` (statement runs). Wired to the
  existing service layers, no service changes.
- **Academics** — `run_apprenticeships_menu` (students / employers /
  listings / applications / APL evidence) and `run_placements_menu`
  (students / placement-hours log / export / APL evidence). Data logic
  factored out of the single-file GUIs into `apprenticeship_service.py` /
  `placement_service.py` (GUIs re-import them).
- **Health** — `run_first_aid_menu` and `run_health_safety_menu` (incident
  and hazard reporting, training records). Persistence factored into
  `first_aid_service.py` / `health_safety_service.py`; added
  `HSDatabase.update_hazard_status` (the GUI had no hazard-status update).
- **Commerce** — `run_bakery_menu` covering the bakery's core persisted
  domain (menu, orders/POS, pre-orders, inventory, production plans,
  subscriptions), via a new Tkinter-free `bakery_service.py`. The many
  peripheral GUI features (loyalty, HACCP, staffing, KDS, …) were left for
  later given the app's ~155-action size.

(Audit items "mobility CLIs" and "Advanced Search + Batch Operations" needed
no work — those CLIs already existed and were wired.)

### Added — CLIs for six compliance / case-management modules

Six previously GUI-only modules gained text CLIs, wired into the main CLI
menu under a new **⚖️ COMPLIANCE & CASE MANAGEMENT** section (guarded
lazy-import dispatch). Each reads/writes the same ``student_records.db`` its
GUI uses:

- **Safeguarding** (``student_affairs/safeguarding/cli``) — case lifecycle,
  submissions/triage queue, mandatory-reporting queue, SLA/escalation, DSL
  daily digest, SAR bundle export, retention purge. Honours the module's
  role-permission model (``require(...)``).
- **Visa Compliance** (``student_affairs/international_compliance/cli``) —
  visa records, CAS, right-to-study checks, status letters, expiry alerts.
- **Equality & Diversity** (``student_affairs/equality_diversity/cli``) —
  monitoring records, incidents, cross-tab / attainment-gap / trend reports,
  SAR export and right-to-erasure. Record/incident CRUD was factored into
  ``access.py`` so CLI and GUI share one audited path.
- **Disciplinary** (``operations/legal/disciplinary/cli``) — incidents,
  actions, academic-misconduct escalation, statistics.
- **Fitness to Practise** (``.../fitness_to_practise/cli``) — cases, stage
  changes, concerns, events, outcomes.
- **Risk Management** (``operations/legal/risk_management/cli``) — risk
  register, 5×5 matrix/heatmap, mitigation/outcome tracking. Its data layer
  (``Risk`` / ``RiskDB``) was factored out of the Tkinter GUI into
  ``risk_service.py`` (the GUI now re-imports it).

### Added — CLI ↔ GUI parity for wellbeing & lesson planning

- **Student Wellbeing** — the CLI (referral CRUD) and GUI (check-ins) were
  near-disjoint despite sharing ``wellbeing_service``. Added a "Wellbeing
  Check-ins" submenu to the CLI (log / list / summary) and a Referrals CRUD
  tab (create / view / update / delete) to the GUI, so both front-ends now
  cover the same actions.
- **Lesson Planner** — the timetable/lesson planner
  (``course_planning/lesson_planner.py``) was GUI-only. Added
  ``course_planning/services/lesson_service.py`` (per-row CRUD on the
  ``lesson_plans`` / ``lesson_courses`` tables the GUI persists to) and a
  ``lesson_planner_cli.py`` (Lessons CRUD, Courses CRUD, planned
  contact-hours summary), wired into the CLI menu as **Lesson Planner**
  beside the existing degree-planning **Course Planning**. (Degree planning
  already had both a CLI and a GUI; only the lesson side lacked a CLI.)

### Added — Gym check-out in the GUI

The Gym GUI had a Check-In button but no Check-Out (the CLI had both). Added
a **Check Out** button and ``MembershipManager.get_active_attendance()``,
which closes the member's open attendance record.

### Added — Create Event button in the Events GUI

The Events (Event Discovery) GUI shipped a complete ``create_event_dialog``
that no button ever called — so GUI users could not create events. Wired a
**Create Event** action into the header toolbar; submitting it inserts into
``unified_events``.

### Fixed — Facilities inspections reference a valid room

The Facilities GUI Inspections tab stored a ``rooms.id`` into
``housing_inspections.room_id``, whose foreign key requires a
``housing_rooms.room_id`` — so every GUI insert failed and the table stayed
empty. The new Inspections CLI references a valid ``housing_rooms.room_id``
(and lists inspectable rooms) so records actually persist. The GUI tab
still needs the same correction.

### Removed — orphaned and duplicate code

- **``campus/building_management/``** — an empty stub package (docstring-only
  ``__init__.py``) imported by nothing. Its functionality already lives in
  ``campus/facilities/`` (the ``building_management_app.py`` GUI + service
  managers + new CLI), so the stub was deleted.
- **``health/gui/health_portal/medical_accommodation/``** — a byte-for-byte
  duplicate of ``health/gui/medical_accommodation/`` (same code, import
  paths rewritten). Repointed the single importer
  (``health_portal/accessibility.py``) at the canonical tree and removed the
  copy.
- **``academics/assignments/``** — an orphaned stub (read-only GUI + thin
  service) imported by nothing. The real, fully-featured assignment system
  is ``academics/gui/assignment_system/`` (backed by
  ``academics/services/assignments/`` and the REST ``assignment_routes``),
  wired into the main GUI and the student/staff/instructor portals. Removed
  the stub and dropped it from ``academics.__init__.__all__``.


## [9.2.0] — 2026-07-03

Sixth-Form Advanced Search gains a large batch of power-user features in
the GUI, with matching CLI flows so both front-ends stay in step.

### Added — Advanced Search GUI: 25 new features

``sixthform_system/modules/domain/students/advanced_search/
advanced_search_views.py`` gains 25 features, surfaced through a new
feature toolbar (``Query ▾`` / ``View ▾`` / ``Compare ▾`` / ``Triage ▾`` /
``Watchlists ▾``), a pinned-query chip row, a Tools-tab scheduling
section, and key bindings (``Ctrl-K``, ``F1``, ``?``):

- **Query** — boolean query builder, phonetic/fuzzy matching (Soundex +
  fuzzy ratio, so "Catherine" finds "Katharine"), regex tester, hit-count
  estimate, and pinned-query chips.
- **Results & triage** — multi-column group-by (e.g. ``Year+Risk``),
  pivot/crosstab (scope × status), cross-scope overlap, diff-since-last-run
  highlighting, score heatmap, inline sparkline trends, and saved column
  layouts.
- **Workflow** — flag-with-reason codes, assign-to-workflow, bulk message
  send (not just draft), bulk PDF reports, an undo stack for bulk
  annotation edits, watchlists, and saved-search scheduling.
- **UX & safety** — command palette, keyboard-shortcut cheatsheet,
  high-contrast dark theme, safe-mode masking of sensitive preview fields,
  compare-A/B result sets, and an operator action log.

Overlay data (flags, workflow assignments, watchlists, layouts, pinned
queries, action log) is written to JSON documents alongside the existing
``advanced_search_ui.json`` / annotations store — never into the domain
tables — so this convenience layer cannot corrupt student records.

### Added — CLI parity for advanced search

``advanced_search_cli.py`` gains 24 new menu flows mirroring the GUI:
boolean/phonetic/regex/safe-redacted search and hit estimate; operations
on the current result set (random sample, filter-within, group-by, facets,
pivot, cross-scope overlap, new-since-last-run, message students,
compare A/B); annotations (flag, tag, note, assign owner, assign to
workflow, view, undo); bulk student-status change; watchlists; and the
operator action log.

The CLI reads and writes the **same** overlay JSON files as the GUI
(``advanced_search_annotations.json``, ``advanced_search_ui.json``,
``advanced_search_action_log.json`` under the sixth-form data dir), so a
flag or watchlist created in one front-end is visible in the other. The
overlay and phonetic helpers are re-implemented in the CLI module so it
carries no Tkinter dependency. Inherently graphical features (column
pinning, heatmap colouring, theming, hover popovers) are intentionally
not ported.


## [9.1.0] — 2026-07-02

Per-system forced password reset, with a dedicated dashboard in both the
GUI and CLI superadmin consoles.

### Added — Per-system forced-password-reset policy

Forced password reset is now controlled **per education system** instead
of a single global switch (``shared/auth/core.py``). A user shares one
password across every system they belong to, so a reset is forced if
*any* of their systems mandates it.

- ``check_password_expiry`` is now system-aware. Its signature is
  unchanged, so all existing login callers (``authenticate``,
  ``verify_mfa``, ``complete_mfa_login``) work untouched.
- New settings, backed by the existing ``auth_settings`` table:
  - ``force_password_reset:<system>`` — the age-based (>90 day /
    never-set) expiry policy toggle, falling back to the global
    ``force_password_reset`` default when a system has no override.
  - ``force_password_reset_pending:<system>`` — an admin-triggered reset
    epoch; any user in that system whose password predates it must reset
    at next login. Users who change their password afterwards clear
    themselves automatically.
- New ``UserAuth`` helpers: ``get_system_password_policy``,
  ``set_system_password_policy``, ``force_system_password_reset``,
  ``clear_system_password_reset``, ``get_password_policy_overview``, and
  a ``delete_setting``.

### Added — Password Reset Dashboard (GUI)

New ``shared/gui/password_reset_dashboard.py`` — a Tkinter dashboard
listing the five education systems (Nursery, Primary, Secondary, Sixth
Form College, University), wired to the ``UserAuth`` backend. It provides
an **ALL SYSTEMS** master switch, a per-system policy toggle, and a
per-system **Force now** action with a live "pending reset" indicator.
Split into ``PasswordResetDashboardFrame`` (embeddable) and
``PasswordResetDashboard`` (standalone, runnable directly). The superadmin
GUI dashboard's new **Password Policy** section embeds this frame.

### Added — Password Policy section in the superadmin CLI

``shared/cli/superadmin_cli.py`` gains menu option **15) Password
Policy**, a text-mode mirror of the dashboard: a per-system policy table,
toggle a system, turn all systems ON/OFF, force reset now (one system or
all), and clear a pending reset — all driving the same ``UserAuth``
backend so the GUI and CLI stay in sync.

### Changed — University forced-reset toggle is now university-scoped

The university admin's Security-window toggle
(``university_system/modules/shared/gui/main/admin/config_gui.py``) and
the auth CLI toggle
(``university_system/infrastructure/auth/cli/cli_menus/user_management.py``)
now read/write ``force_password_reset:university`` via the new helpers
instead of the global setting, so a university admin controls only the
university system.


## [9.0.1] — 2026-06-15

University-system fixes and a First Aid Portal refresh.

### Added — First Aid Portal Resources tab is now functional

The six cards on the First Aid Portal's **Resources** tab
(``university_system/modules/domain/health/first_aid/
first_aid_portal.py``) previously all shared one placeholder dialog
(*"This would link to the actual resource in a production system."*).
Each button now performs real work:

- **CPR Certification → Register** — opens a registration form
  pre-filled from the signed-in user and persists the sign-up to a new
  ``first_aid_training_registrations`` table in the central
  ``student_records.db``, returning a ``REG-NNNN`` reference.
- **First Aid Handbook → Download** — generates a handbook from the
  portal's own first-aid procedures and emergency contacts, writes it
  to the user's ``Downloads`` folder (falling back to the temp dir),
  and opens it with the OS default application.
- **Training Videos → Watch** — lists reputable first-aid videos
  (British Red Cross / BHF); each opens in the default browser.
- **Workshop Schedule → View Schedule** — shows upcoming workshops
  with dates computed relative to today.
- **First Aid Kit Locations → Open Map** — campus directory of first
  aid kit and AED locations, plus an "open campus map" link.
- **Mobile App → Get App** — Safety App details with App Store /
  Google Play links.

``IncidentDB._ensure_schema`` gained the new registrations table and an
``add_registration()`` method mirroring the existing incident-logging
pattern.

### Changed — First Aid Portal opens in a standalone window

``show_new_feature_first_aid_portal`` in
``university_system/modules/shared/gui/main/main_gui.py`` no longer
embeds the portal in the main content tab. It now launches in its own
``Toplevel`` sized like the main GUI (1400x900, centered, minsize
1200x800), matching the Safeguarding/Finance convention, with the same
load/start error handling.

### Fixed — Paid-at-till sales to non-students no longer fail the FK

Recording a gym (or other POS) sale for a non-student buyer logged:

```
WARNI record_paid_sale(admin, 480.0) failed: FOREIGN KEY constraint failed
```

Root cause: ``finance_bus.record_paid_sale`` writes to
``student_finance_transactions``, which has a foreign key to
``students(student_id)``. A staff/admin buyer isn't a student, so the
insert failed — and because the ``student_finance_accounts`` row (no FK)
was inserted first, it left an orphan account behind.

#### Fix

Added an ``_is_student()`` guard to ``finance_bus``. Both
``record_paid_sale`` and ``raise_charge`` now skip the ledger write
cleanly (debug log, return ``None``) when the buyer isn't a student,
rather than raising a FK error and orphaning an account row. The student
ledger is student-only by design, so a paid-in-full sale to staff/admin
simply has nothing to record there; the membership/sale flow is
unaffected (``commerce_bus.post_sale`` already wraps the finance call).

## [9.0.0] — 2026-06-13

Major release. Summarises all changes since 8.117.160: a new fifth
system (nursery), a large university-system domain reorganisation, and a
cross-system integration layer that links the five systems into one
platform. ~2,300 files touched (incl. ~370 pure renames from the reorg),
the complete nursery system added, and stale top-level docs removed.

### Added — Nursery system (new fifth system)

A complete Early Years / EYFS system under ``education_system/
nursery_system/`` (CLI + GUI + data layer), covering children &
admissions, EYFS learning & development, daily care/routines (bottle
feeds, nappy/sleep logs), safeguarding & welfare, accident logs, staff &
ratios, funding (funded hours, childcare vouchers), and compliance/
reporting. Includes a nursery→primary transfer flow. The unified
launcher, login and shared auth now treat ``nursery`` as a first-class
system alongside the existing four.

### Added — Cross-system integration: five systems, one platform

Links the five previously-independent systems (nursery → primary →
secondary → sixth-form → university) via the canonical
``student_journey`` registry and the durable cross-system event bus. All
additions are best-effort and non-breaking: a registry/bus failure is
logged but never blocks a local create, transfer, or save.

#### Journey spine & K-12 progression pipeline

- Every pupil/student create path now registers the learner into the
  canonical ``student_journey`` registry and stamps a ``journey_id`` FK
  onto its own row (``shared/cross_system/progression.py``,
  ``person.py``). Because the registry matches on (name + DOB), the same
  person created in two systems collapses to one ``journey_id``.
- Generalised the sixth-form→university intake to **every** adjacent
  phase: each transfer publishes ``student.progression.completed`` and
  each system runs an idempotent ``ProgressionIntake`` consumer
  (``primary_intake``, ``secondary_intake``, ``college_intake``), so a
  pupil aging out of one phase auto-creates a linked record in the next.
- ``identity_backfill`` now stamps ``journey_id`` onto existing rows too.

#### Shared Person model & single student view

- ``shared/cross_system/person.py`` — one identity (legal name, DOB,
  NHS/UPN) over the registry, with ``update_demographics`` as the single
  source of truth.
- ``shared/cross_system/student_view.py`` + ``GET /api/v1/journey/
  <journey_id>/overview`` (staff-gated) — a learner's whole history
  across all five systems in one read-only view, surfaced as a
  **Student Journey** GUI panel (with a one-click **Promote to next
  phase** action) and CLI command in every system.

#### Real-time bus, safeguarding, parents, staff, reporting

- **Real-time backbone**: a background drainer thread (suppressed in
  tests) plus a ``python -m …bus_drainer`` cron/systemd entrypoint, so
  events propagate continuously instead of only at launch.
- **Cross-system safeguarding** (``shared/safeguarding/``): a flag
  raised in one system is recorded against the ``journey_id`` and
  broadcast, so it follows the learner; wired into all real
  safeguarding modules.
- **Unified parent portal**: ``GET /parent/api/children/journey``
  aggregates every child across systems for one parent login.
- **Cross-system staff directory** (``shared/staff_directory/``): the HR
  parallel to ``student_journey`` — one identity for staff working
  across systems; wired into all ``create_staff`` paths.
- **Reporting warehouse** (``shared/analytics/warehouse.py``): ATTACHes
  all five databases read-only for org-wide headcounts, retention
  funnel and progression rates, exposed at ``/api/v1/warehouse/*`` and a
  **Reporting Warehouse** GUI panel.

#### Notes

- New cross-system API routes are staff-gated (``admin``/``staff``/
  ``teacher``) and read-only.
- Two tables added to the shared auth DB schema: ``safeguarding_alerts``
  and ``staff_directory``.
- Covered by new test suites under ``shared/tests/`` (progression,
  person/student-view, backfill+API, and the cross-system backbone).

### Changed — University-system domain reorganisation

The university ``modules/domain`` tree was consolidated from a flat list
of domains into higher-level groupings (≈370 pure file moves plus import
updates), with no behavioural change:

- ``research/`` → ``academics/research/``
- ``housing/`` and ``mobility/`` → ``campus/`` (``campus/housing``,
  ``campus/mobility``)
- ``communications/``, ``legal/`` and ``staff_hr/`` → ``operations/``
  (``operations/communications``, ``operations/legal``,
  ``operations/staff_hr``)
- ``events/``, ``portfolio``, ``student_jobs`` and related modules
  grouped under ``student_affairs/``

Old per-module test directories were replaced with a refreshed
``tests/core`` suite (activity logger, audio utils, console output,
defaults, error/exception handling, i18n, institution settings, logs,
legal services, …).

### Changed — Launcher, tooling & K-12 refinements

- Unified launcher (``launcher/``) and ``run.py`` reworked to register
  and dispatch all five systems (including the background bus drainer per
  system at startup); ``conftest.py`` suppresses the drainer thread in
  tests.
- ``pyproject.toml``, ``alembic.ini`` and docs (``TESTING.md``,
  ``PROJECT_STRUCTURE.md``) updated to match the new layout.
- Primary / secondary / sixth-form: staff-HR, enrolment, pupils,
  messages, safeguarding and custom-export modules refined, and the
  journey/safeguarding/staff-directory hooks wired into their create
  paths.

### Removed

- Stale top-level fix notes (``HELPDESK_EMAIL_LOOKUP_FIX.md``,
  ``HELPDESK_TEMPLATE_VARIABLES_FIX.md``, ``about.txt``) and obsolete
  university module/test files superseded by the reorganisation.

---
