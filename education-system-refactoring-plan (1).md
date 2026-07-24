# Education System Refactoring Plan

This document lists the recommended changes for the Education System project and proposes a cleaner package structure. The order is intentional: fix security and reliability first, then reorganise the code without breaking working features.

## Main goals

- Make the project safe to run on a local network.
- Make installation work on computers other than the developer's machine.
- Test all five education systems consistently.
- Separate business logic from the GUI, CLI and API.
- Reduce duplicated implementations across systems.
- Make the documentation accurately reflect the current state of the project.
- Stabilise existing functionality before adding more major features.

## Current repository status

This plan was updated after reviewing the current `main` branch at commit
`d08495d` on 23 July 2026. The project now contains Nursery, Primary School,
Secondary School, Sixth Form College and University systems.

The latest update moved Sixth Form into
`education_system/post_16/sixthform_system`, moved University into
`education_system/post_18/university_system`, added Nursery, and expanded the
Git exclusions for runtime data and secrets.

Phase 1 (security) was audited and fixed on 23 July 2026. Resolved this pass:

- `run.py` now serves **only** the selected system's `web/` directory, not the
  repository root (which had exposed the raw `auth.db`, `audit.db` and
  `student_records.db` over HTTP);
- the `university.html` "Download auth.db / audit.db / records DB" links and the
  hardcoded absolute DB path were removed;
- `run.py` no longer sets `API_CORS_ORIGINS=*` — `--web` now pins CORS to the
  exact static-server origin (`http://localhost:<web-port>`), and quiet mode no
  longer touches CORS at all;
- the unified server now refuses to start in production when `API_SECRET_KEY`
  is missing (previously it silently fell back to a random per-process key),
  matching the existing `JWT_SECRET_KEY` behaviour;
- the `/mfa/verify` endpoint is now rate limited by client IP and by target user.

Phase 2 (portable installation & configuration) was audited and fixed on 23 July
2026. Resolved this pass:

- the `Makefile` no longer hardcodes `/home/seancatchpole989/venv/bin` — it now
  uses `PYTHON ?= python` with `PIP`/`PYTEST`/`ruff`/`mypy`/`bandit`/`locust`
  invoked as `$(PYTHON) -m …`, so it runs against whatever environment is active;
- `pyproject.toml` version bumped `8.117.72` → `9.3.0` (matches README/CHANGELOG),
  and the description + keywords now list all five systems including Nursery;
- real `Homepage`/`Repository`/`Issues` URLs added under `[project.urls]`;
- `run.py` is now declared via `[tool.setuptools] py-modules = ["run"]` so the
  `education-system` console script (`run:main`) is importable after install;
- the last machine-specific path in source (`sys.path.insert(0, "/home/…")` in
  `analytics/kpi_dashboard/_smoke_test.py`) now derives the repo root from
  `__file__`;
- added `.env.example` documenting development defaults for secrets, DB, email
  and optional integrations.

Verified: `pip install -e .` succeeds, and the installed `education-system`
console command runs `--help` from outside the repo root (proving `run` is
packaged, not just found on `cwd`).

Remaining confirmed issues (later phases):

- the default test command covers shared and University tests, not all five systems (Phase 4);
- the roadmap still describes four systems in several places (Documentation);
- Ruff ignores undefined names and disables all `E`/`F` checks in tests (Phase 6);
- default `admin` / `admin123` credentials remain documented (Phase 1 follow-up — see below).

Phase 1 follow-ups resolved on 23 July 2026:

- **Force password change at first login** is now implemented. A
  `must_change_password` column was added to the `users` table (with a migration
  for existing DBs); seeded demo accounts are created with the flag set; `login`
  / `verify_mfa` / `complete_mfa_login` surface `must_change_password` in their
  result (and the shared API `/auth/login` response); the CLI and GUI login gates
  force a password change when it is set; and `change_password` clears the flag.
- **Permission / access-isolation tests** were added
  (`shared/tests/test_permission_isolation.py`): RBAC-layer checks that a
  single-system user reports no access to the other four systems, plus
  API-layer checks that `token_required` / `role_required` / `system_required`
  return 401/403 for out-of-scope requests. This surfaced and fixed a real gap:
  `_KNOWN_SYSTEMS` in `shared/api/auth.py` omitted `nursery`, so nursery routes
  (mounted under `/api/v1/nursery/`) bypassed path-scoped role enforcement — an
  admin on *any* system would have passed an admin-gated nursery route. `nursery`
  is now in the scoped-system set. Tests for the flag live in
  `shared/tests/test_must_change_password.py`.

Phase 1 item still open (needs explicit sign-off, not just code):

- **Git history** contains a `student_records.db` committed historically and
  removed from tracking in `f16a8f97`; `auth.db`, encryption keys and `.env`
  were never tracked. Purging the historical DB blob requires a destructive
  history rewrite (git-filter-repo/BFG), a force-push, and coordination with
  anyone holding clones — deliberately **not** performed automatically.

## Phase 1: Security fixes

_All items complete (see the Phase 1 summaries in "Current repository status" above). Only the git-history purge remains — it needs human sign-off, not code; tracked under "Needs further investigation"._

## Phase 2: Portable installation and configuration

_All items complete (see the Phase 2 summary in "Current repository status" above)._

## Phase 3: Dependency cleanup

Audited and reworked on 23 July 2026. `pyproject.toml` now separates a minimal
default runtime from optional feature tiers; `requirements.txt` is a pure runtime
lock and dev/CI tooling moved to a new `requirements-dev.txt`.

Most items complete (extras structure, dev/prod lock split, per-provider cloud, smallest-install docs). Remaining:

- [~] Keep only essential runtime dependencies in the default installation. *(dev/test/security/perf tooling, alt DB backends, cloud, graphql, realtime, LMS integrations and deep-learning AI moved to extras; **plotly moved to a new `viz` extra** — it's only imported lazily inside two dashboard methods, now guarded with an "install `[viz]`" message. **Caveat:** numpy/pandas/scipy/scikit-learn/matplotlib/seaborn stay in the default install because they're imported at module load across core academics/finance; making those an optional `analytics` extra is the remaining follow-up — see "further investigation")*
- [~] Remove libraries that duplicate the same purpose unless both are genuinely required. *(removed **fpdf2** and **recurring-ical-events** — both had zero references anywhere. The rest are not true duplicates: reportlab (generate) / pypdf (read) / python-docx (Word) serve distinct purposes; matplotlib+seaborn are complementary and plotly is interactive; fuzzywuzzy+python-Levenshtein is lib+speedup. The only remaining genuine overlap is **ics vs icalendar** (both used in ~2 files) — see "further investigation".)*

## Phase 4: Testing

Audited and worked on 23 July 2026. All five systems are now collected by the
test suite; per-system smoke tests, migration tests and password-reset-token
tests were added; and separate coverage targets were wired up.

Most items complete (all five systems collected, auth/login/MFA/session/reset/migration tests, temp-DB isolation, Flask-client integration + e2e, separate coverage targets). Remaining:

- [~] Add a per-system smoke test (import → temp DB → services → API routes → CRUD). *(smoke tests added for all four smaller systems, but **authenticated CRUD-through-API per small system is deferred** — kept write-free to avoid touching a real system DB.)*
- [~] Test role and system-access enforcement on every API group. *(RBAC + auth-required asserted for all five systems; **exhaustive role-per-endpoint coverage across every blueprint still partial**.)*
- [~] Add GUI tests for controllers and view models without a physical display. *(established the pattern and added **20 display-free view-model tests** (`test_gui_viewmodel.py` in sixth-form/primary/secondary) covering the dashboard KPI/attendance logic. They run in the **default** suite (not `@pytest.mark.gui`) by exercising the pure helpers directly — module-level functions, or instance methods on a bare `__new__` instance so no Tk window/display is needed. Broader controller coverage across all GUI modules is still open — see "further investigation".)*
- [~] Publish the real coverage percentage rather than only a Codecov badge. *(`make coverage-percent` prints the real total; actually publishing it belongs to CI — Phase 5)*

## Phase 5: Continuous integration

Added `.github/workflows/ci.yml` on 23 July 2026 (CodeQL and Dependabot already
existed). Jobs: `lint`, `security`, `test`, `systems`, `build`, `docs-links`,
`slow-tests`, and a `ci-success` gate.

Most items complete (workflow, py3.11/3.12 matrix, build + install smoke, pip caching, fast-on-PR, separate slow job, Dependabot, per-system "all five tested" gate). Remaining:

- [~] Run Ruff, mypy and security checks in CI. *(all three run; **ruff + mypy are non-blocking** pending the Phase 6 F405/formatting cleanup — flip them to gating there. Bandit + pip-audit run in the `security` job.)*
- [~] Check that documentation links are valid. *(lychee gates the top-level docs; the wider `docs/**` tree has pre-existing broken links and isn't gated yet — see "further investigation")*

## Phase 6: Code-quality improvements

Worked on 23 July 2026. This is the ongoing/gradual phase; the cheap high-value
wins are done, the large refactors are scoped and documented.

Cheap high-value wins complete (F821 re-enabled — caught & fixed 10 real bugs; test-file E/F ignore narrowed; auth `except Exception: pass` swallows fixed; sensitive-data logging audited clean; typing config confirmed). Remaining:

- [~] Gradually enable unused-import and unused-variable checks. *(mechanism documented; `F401`/`F841` stay globally ignored for now — see "further investigation")*
- [~] Replace broad `except Exception` handlers with specific exceptions where practical. *(done for the auth paths; the wider sweep across domain/services is ongoing)*
- [x] Use consistent names for each system in flags, package names, routes and internal identifiers. *(**Converged on the plan's canonical keys — `secondary` and `sixth_form`** (was `school`/`college`). Added a central `canonical_system_key()` normaliser (`shared/core/system_keys.py`); renamed the auth seed + `_KNOWN_SYSTEMS` + the `SYSTEM_DB_PATHS`/`ORDER`/`LABELS` registry + launcher dispatch + ~96 consumer files onto canonical; added an idempotent `user_systems.system_key` DB migration (`college→sixth_form`, `school→secondary`). Legacy keys stay accepted everywhere via the normaliser (auth lookups, `_system_key_from_path`) so old JWTs/DBs/URLs keep resolving — per the plan's "temporary aliases at the boundary". Route URL prefixes (`/api/v1/sixthform/`, `/school/`) and package dirs (`sixthform_system`, `secondarysch_system`) deliberately remain as compat aliases (the plan permits this). CLI flags already accept both. Verified: 791 shared tests + the four-system suites pass.)*
- [ ] Keep functions small enough to test independently. *(ongoing; tied to the interface/application-layer split in the proposed architecture)*
- [ ] Move direct SQL out of Tkinter windows, CLI menus and Flask route handlers. *(GUI/CLI largely SQL-free; the real debt is **~111 Flask route files** with embedded SQL — see "further investigation")*

## Proposed project structure

The safest approach is an incremental structure that retains one package per education system while moving reusable behaviour into shared domain and application layers. The current `post_16` and `post_18` paths can remain temporarily as compatibility paths, but the final package naming should be consistent across all five systems.

```text
university_system/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── SECURITY.md
├── CONTRIBUTING.md
├── Makefile
├── .env.example
├── migrations/
├── docs/
├── scripts/
│   ├── seed_demo_data.py
│   └── check_installation.py
├── src/
│   └── education_system/
│       ├── __init__.py
│       ├── __main__.py
│       ├── launcher.py
│       ├── config/
│       │   ├── settings.py
│       │   ├── logging.py
│       │   └── paths.py
│       ├── domain/
│       │   ├── users/
│       │   ├── students/
│       │   ├── staff/
│       │   ├── courses/
│       │   ├── attendance/
│       │   ├── assessment/
│       │   ├── safeguarding/
│       │   └── reporting/
│       ├── application/
│       │   ├── commands/
│       │   ├── queries/
│       │   ├── services/
│       │   └── dto/
│       ├── infrastructure/
│       │   ├── auth/
│       │   ├── database/
│       │   ├── repositories/
│       │   ├── email/
│       │   ├── files/
│       │   ├── integrations/
│       │   └── security/
│       ├── systems/
│       │   ├── nursery/
│       │   │   ├── config.py
│       │   │   ├── policies.py
│       │   │   └── services/
│       │   ├── primary/
│       │   │   ├── config.py
│       │   │   ├── policies.py
│       │   │   └── services/
│       │   ├── secondary/
│       │   │   ├── config.py
│       │   │   ├── policies.py
│       │   │   └── services/
│       │   ├── sixth_form/
│       │   │   ├── config.py
│       │   │   ├── policies.py
│       │   │   └── services/
│       │   └── university/
│       │   │   ├── config.py
│       │   │   ├── policies.py
│       │   │   └── services/
│       └── interfaces/
│           ├── api/
│           │   ├── app.py
│           │   ├── auth/
│           │   ├── shared/
│           │   ├── nursery/
│           │   ├── primary/
│           │   ├── secondary/
│           │   ├── sixth_form/
│           │   └── university/
│           ├── cli/
│           │   ├── app.py
│           │   ├── menus/
│           │   └── presenters/
│           ├── gui/
│           │   ├── app.py
│           │   ├── views/
│           │   ├── controllers/
│           │   └── widgets/
│           └── web/
│               ├── static/
│               └── templates/
└── tests/
    ├── unit/
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    ├── integration/
    │   ├── auth/
    │   ├── database/
    │   └── api/
    ├── systems/
    │   ├── nursery/
    │   ├── primary/
    │   ├── secondary/
    │   ├── sixth_form/
    │   └── university/
    ├── gui/
    ├── end_to_end/
    ├── performance/
    └── fixtures/
```

## Responsibility of each layer

### `domain`

Contains education rules and entities without Tkinter, Flask or direct database access.

Examples:

- calculating grades;
- validating attendance records;
- student enrolment rules;
- assessment policies;
- safeguarding case rules.

### `application`

Coordinates use cases using domain objects and repository interfaces.

Examples:

- `EnrolStudent`;
- `RecordAttendance`;
- `AssignGrade`;
- `GenerateStudentReport`;
- `SuspendUser`.

Each use case should be callable from the GUI, CLI and API.

### `infrastructure`

Implements technical details.

Examples:

- SQLite/PostgreSQL repositories;
- password hashing;
- email delivery;
- file storage;
- external LMS clients;
- audit logging.

### `systems`

Contains behaviour specific to an institution type. It should configure and extend shared capabilities rather than duplicate them.

Examples:

- nursery ratios, funded hours, EYFS observations and learning journeys;
- university modules and degree classifications;
- sixth-form T Levels and UCAS;
- secondary-school GCSE and form-group rules;
- primary-school EYFS, phonics and KS1/KS2 rules.

### `interfaces`

Translates user or HTTP input into application use cases and formats the result. Interface code should not contain core education rules or lengthy SQL.

## Example shared use case

The GUI, CLI and API should all call the same application service:

```python
class RecordAttendance:
    def __init__(self, attendance_repository, student_repository):
        self.attendance_repository = attendance_repository
        self.student_repository = student_repository

    def execute(self, request):
        student = self.student_repository.get(request.student_id)
        record = student.record_attendance(
            date=request.date,
            status=request.status,
        )
        self.attendance_repository.save(record)
        return record
```

The interfaces should only collect input, create the request and display or serialise the returned record.

## Naming standard

Use one canonical identifier everywhere:

| Institution | Internal key | Package | URL prefix | CLI flag |
|---|---|---|---|---|
| Nursery / Early Years | `nursery` | `systems.nursery` | `/api/v1/nursery` | `--nursery` |
| Primary School | `primary` | `systems.primary` | `/api/v1/primary` | `--primary` |
| Secondary School | `secondary` | `systems.secondary` | `/api/v1/secondary` | `--secondary` |
| Sixth Form | `sixth_form` | `systems.sixth_form` | `/api/v1/sixth-form` | `--sixth-form` |
| University | `university` | `systems.university` | `/api/v1/university` | `--university` |

Old aliases and the current `post_16`/`post_18` imports can temporarily remain at the launcher boundary for backward compatibility.

## Migration approach

Do not move thousands of files in one change. That would create import failures that are difficult to diagnose.

### Step 1: Establish boundaries

- [ ] Create the new `domain`, `application`, `infrastructure`, `systems` and `interfaces` packages.
- [ ] Keep existing modules working.
- [ ] Add architecture rules to documentation.
- [ ] Add tests before moving code.

### Step 2: Migrate one complete feature

Use attendance or student records as the first vertical slice:

- [ ] Move its business rules into `domain`.
- [ ] Create an application service.
- [ ] Create repository interfaces and SQLite implementations.
- [ ] Change one GUI screen, CLI command and API route to call the same service.
- [ ] Add unit and integration tests.
- [ ] Confirm behaviour before migrating another feature.

### Step 3: Consolidate shared features

- [ ] Compare the five systems' child, pupil and student implementations.
- [ ] Move genuinely common behaviour into shared domain modules.
- [ ] Keep institution-specific fields and rules under `systems`.
- [ ] Repeat for attendance, staff, courses, reporting and safeguarding.

### Step 4: Remove old paths

- [ ] Add temporary import adapters where necessary.
- [ ] Mark old modules as deprecated.
- [ ] Search for remaining imports before deleting adapters.
- [ ] Remove adapters in a documented breaking release.

## Documentation changes

- [ ] Keep the README synchronised with the current repository version.
- [ ] Keep the README focused on installation, main features and basic usage.
- [ ] Move detailed module inventories into generated documentation.
- [ ] Generate file, module, route and test counts automatically if they are displayed.
- [ ] Remove contradictions between the README, roadmap and changelog.
- [ ] Clearly label features as complete, partial, experimental or planned.
- [ ] Replace `enterprise-grade` while the roadmap states that production deployment is not recommended.
- [ ] Add screenshots of the GUI and web interfaces.
- [ ] Add a concise architecture diagram.
- [ ] Document which features are available in each system and interface.
- [ ] Document the supported database engines and which ones are actually tested.
- [ ] Keep one current changelog and archive older major-version changelogs.
- [ ] Use fewer, meaningful releases instead of releasing every small internal edit.

## Repository maintenance

- [ ] Identify large tracked files and generated artefacts.
- [ ] Remove databases, reports, exports and test output from version control.
- [ ] Check whether Git LFS is required for legitimate large assets.
- [ ] Add issue and pull-request templates.
- [ ] Add a code of conduct only if external contributions are expected.
- [ ] Add release notes for meaningful versions.
- [ ] Define the supported Python versions.
- [ ] Define a deprecation policy for renamed modules and launcher flags.

## Recommended order of work

1. Fix static-file exposure and wildcard CORS.
2. Remove machine-specific Makefile paths.
3. Align the version and five-system description across `pyproject.toml`, README and roadmap.
4. Make a clean installation succeed.
5. Add smoke tests for Nursery, Primary, Secondary, Sixth Form and University.
6. Add or repair GitHub Actions.
7. Split production and development dependencies.
8. Re-enable important lint rules.
9. Decide whether `post_16`/`post_18` are permanent concepts or temporary compatibility paths.
10. Migrate one feature through the proposed architecture.
11. Consolidate duplicated features gradually.
12. Remove obsolete modules only after tests confirm they are unused.

## Definition of done

The refactoring effort is successful when:

- a new contributor can clone and run the application without editing paths;
- the server does not expose repository files;
- production cannot start with missing security configuration;
- CI tests all five systems;
- GUI, CLI and API interfaces reuse the same application services;
- common education features are implemented once;
- institution-specific rules remain clearly separated;
- documentation matches the code;
- releases represent stable, tested changes.

## Needs further investigation

Open questions and partially-resolved items, collected here so they aren't lost
between phases. Each links back to the checklist item it came from.

### Requires explicit human sign-off (not a code change)

- **Git history purge — investigated; no privacy risk, so optional.** The
  historical `student_records.db` blob (added in `031c0a06`, removed from tracking
  in `f16a8f97`) was extracted and inspected: **1405 tables but zero data rows** —
  the only non-empty tables are SQLite's internal `sqlite_stat1` (optimizer stats)
  and `alembic_version` (a version marker). It is a **blank schema-only DB with no
  personal or demo data** (`auth.db`, encryption keys and `.env` were never
  tracked either). So the rewrite is **not** needed for data protection — the only
  reason left is to drop a ~10 MB blob from history to shrink the repo, which is a
  low-priority maintenance call. If done, it still needs a destructive rewrite
  (git-filter-repo/BFG), a force-push, and coordination with clone holders —
  deliberately not performed automatically. *(Phase 1)*

### Worth auditing (surfaced while fixing other items)

- **Migration runs for every launch.** `_run_alembic_upgrade` (now fail-closed)
  runs unconditionally at startup, but the migrations only cover the university
  `student_records.db`. So a broken university migration blocks a nursery/primary
  launch unless `EDU_ALLOW_SCHEMA_DRIFT=1` is set. The cleaner fix is to defer the
  university migration until the university system is actually selected. *(Phase 1)*

- **`analytics` as a true optional extra.** `plotly` is already moved to the
  `viz` extra; making the rest (numpy/pandas/scipy/scikit-learn/matplotlib/
  seaborn) optional is more feasible than first thought — ruff finds ~139 unused
  scientific imports and ~71 are already `try/except ImportError` probes — but it
  is **not** a mechanical `ruff --fix F401` sweep: a trial removal broke
  `batch_operations` because import-aggregator modules (`constants.py`,
  `_imports.py`, `_common.py`) re-export `np`/`pd`/`plt` in multi-line blocks that
  ruff flags as "unused" in the defining file. The real work is per-module —
  verify each removal against downstream consumers and wrap genuinely-used imports
  in the probe pattern — so the compute stack stays in the default install for
  now. *(Phase 3 / Phase 6)*
- **`ics` vs `icalendar` consolidation.** The only remaining duplicate after the
  Phase 3 dependency audit (fpdf2 / recurring-ical-events already removed; the
  other overlaps were not true duplicates). Two iCal libraries, each used in ~2
  files — pick one and migrate the handful of call sites to drop the other. *(Phase 3 / Phase 6)*
- **GUI controller / view-model tests — pattern established, coverage partial.**
  Display-free view-model tests now exist for three systems' dashboards
  (`test_gui_viewmodel.py`) using a bare `__new__` instance / module-level pure
  functions, so no display is needed and they run in the default suite. What
  remains is breadth: most GUI windows still mix controller logic with widget
  code, so extending this needs those pure helpers extracted per module (cleanest
  alongside the interface/application-layer split). Do it module-by-module using
  the established pattern. *(Phase 4)*
- **Per-endpoint role coverage.** System-access enforcement (auth required) is
  now asserted for all five systems' APIs, but exhaustive role-per-endpoint
  checks across every blueprint are not. A data-driven test that walks each
  registered route and asserts the expected minimum role would close this. *(Phase 4)*
- **Authenticated CRUD smoke per small system.** The nursery/primary/secondary/
  sixth-form smokes stop at API registration + auth rejection (write-free, to
  avoid touching real system DBs). A full create→read→update→delete through the
  API needs a per-system temp-DB fixture that guarantees the data dir is
  redirected before any DB module imports (safest via a subprocess or an
  autouse session fixture). *(Phase 4)*
- **Make CI lint/format gating.** `ci.yml` runs ruff and mypy as non-blocking
  because `ruff check education_system/` currently reports ~2000 F405
  (star-import) findings and ~5900 files are unformatted. As Phase 6 pays this
  down, drop `continue-on-error` from the ruff steps (and add a real mypy gate on
  `shared/`/`core/`) so lint becomes a required check. *(Phase 5 / Phase 6)*
- **Wider docs link debt.** The CI link check is scoped to the top-level docs
  because `docs/**` has many pre-existing broken relative links (e.g.
  `QUICK_START.md → INSTALLATION.md`, and most `MODULE_GUIDES.md` targets). Fix
  or prune those, then widen the `docs-links` job to cover `docs/**/*.md`. *(Phase 5 / Documentation)*
- **Branch protection is a repo setting.** `ci.yml` exposes a single `ci-success`
  gate job, but making it a *required* status check (so main can't merge/report
  green while it's red or a system is untested) must be enabled in GitHub repo
  settings — the workflow file cannot enforce it itself. *(Phase 5)*
- **Sixth-form F821 (~180).** F821 is enforced everywhere except sixth-form.
  Its ~180 findings are a mix of trivially-fixable missing imports
  (`simpledialog`, `Path`) and domain names (`placement`, `project`,
  `booking`, `medication`, …) that look like the same stranded-import-after-return
  pattern fixed in primary/secondary. Work through them, then drop the
  `post_16/sixthform_system/**` F821 per-file-ignore. *(Phase 6)*
- **Enable F401 / F841 gradually.** Un-ignore them one rule at a time and
  scope-ignore the legacy trees (the pattern now used for F821), starting with
  `shared/` (~92 F401, ~11 F841). F401 needs care — several are side-effect or
  re-export imports that `--fix` would wrongly strip. *(Phase 6)*
- **System-naming rename — DONE (24 Jul 2026).** Converged Secondary and Sixth
  Form onto the plan's canonical keys `secondary` / `sixth_form` (were
  `school` / `college`) via a central `canonical_system_key()` normaliser + a
  `user_systems.system_key` DB migration + a ~96-file consumer sweep. Legacy keys
  and the legacy route/package names remain accepted as boundary aliases. See the
  Phase 6 checklist for detail. *Residual (out of scope, pre-existing):* the
  `sixthform` route prefix is doubled (`/api/v1/sixthform/sixthform/…`) in the
  blueprint definitions, and `scripts/generate_openapi_spec.py`'s `BUILDERS` only
  registers `university`+`unified` (a test expects five) — both predate this work.
- **Direct SQL in ~111 Flask route files.** GUI/CLI are largely clean, but route
  handlers embed SQL. Extract each into the service/repository layer so the same
  logic is reusable by GUI/CLI/API — best done alongside the application-layer
  work in the proposed architecture. *(Phase 6 / migration Step 2)*
- **Broad `except Exception` sweep.** The auth paths are fixed; a codebase-wide
  pass to narrow catch-all handlers (and eliminate remaining silent `pass`
  swallows outside auth) is still outstanding. *(Phase 6)*
