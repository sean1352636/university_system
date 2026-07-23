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

- [x] Serve only the selected web application's static directory. *(run.py serves `web_dir` only)*
- [x] Do not use the repository root as the `SimpleHTTPRequestHandler` directory.
- [x] Replace wildcard CORS with an explicit list of trusted origins. *(server fails closed on `*`; run.py no longer injects `*`)*
- [x] Ensure local web mode permits only its exact frontend origin, such as `http://localhost:8000`. *(pinned to the static-server port)*
- [x] Require persistent `API_SECRET_KEY` and `JWT_SECRET_KEY` values outside development mode. *(both now enforced)*
- [x] Refuse to start in production when required secrets are missing.
- [x] Remove default passwords from production setup. *(demo seeding gated behind `EDU_DEV_SEED`; not seeded in production)*
- [x] If demo accounts are created, require their passwords to be changed at first login. *(`must_change_password` flag: seeded on demo accounts, surfaced by login/API, enforced by CLI/GUI gates, cleared by `change_password`)*
- [x] Confirm that `.env`, databases, JWT secrets, encryption keys, recovery codes, reports and uploads are ignored by Git. *(verified in `.gitignore`)*
- [x] Check Git history for secrets or real personal data that may previously have been committed. *(a `student_records.db` was committed historically, removed in `f16a8f97`; no auth.db/keys/.env ever tracked — history purge needs sign-off)*
- [~] Return a startup failure when an essential database migration, authentication component or route registration fails. *(auth init raises; optional routes are intentionally non-fatal; Alembic upgrade currently only warns — revisit)*
- [x] Continue treating optional integrations as non-fatal, but log clearly which functionality was disabled.
- [~] Review recovery-code authentication and keep it separate from the normal password field if possible. *(reviewed: `/mfa/verify` uses a dedicated code field; the login path also accepts a recovery code in the password field as a one-time bypass — kept for now)*
- [x] Add permission tests proving that users cannot access systems or records outside their assigned role. *(`test_permission_isolation.py`: RBAC + API 401/403 checks; also fixed `_KNOWN_SYSTEMS` omitting nursery)*
- [x] Add rate limiting to login, password reset, MFA verification and recovery-code endpoints. *(MFA verify added this pass; login/register/forgot-password already limited)*

## Phase 2: Portable installation and configuration

- [x] Remove `/home/seancatchpole989/venv/bin` from the `Makefile`. *(replaced with `PYTHON ?= python`)*
- [x] Use the active Python environment:

  ```make
  PYTHON ?= python
  PIP := $(PYTHON) -m pip
  PYTEST := $(PYTHON) -m pytest
  ```

  *(all tools — pip, pytest, ruff, mypy, bandit, locust — now run via `$(PYTHON) -m …`)*
- [~] Verify installation in a brand-new virtual environment. *(verified `pip install -e .` + console command in an existing venv with `--no-deps`; a full clean-venv install of all runtime deps was not re-run this pass)*
- [x] Verify that `pip install -e .` succeeds. *(builds `education_system-9.3.0` editable wheel cleanly)*
- [x] Verify that the `education-system` console command works after installation. *(`education-system --help` runs from outside the repo root)*
- [x] Include `run.py` correctly in the installed package or move its entry function inside `education_system`. *(`[tool.setuptools] py-modules = ["run"]`)*
- [x] Keep machine-specific paths out of source code and configuration committed to Git. *(Makefile + `_smoke_test.py` fixed; no `/home/...` paths remain in tracked `.py`/`.toml`/`.html`)*
- [x] Put development defaults in `.env.example`. *(added; git-ignored `.env` loaded via python-dotenv)*
- [x] Validate environment variables at startup and produce clear error messages. *(unified server fails closed on missing `API_SECRET_KEY`/`JWT_SECRET_KEY`/`API_CORS_ORIGINS` in production with explicit messages; dev defaults documented in `.env.example`)*
- [x] Add the real homepage, repository and issue tracker URLs to `pyproject.toml`. *(`[project.urls]` → sean1352636/university_system)*
- [x] Change the package version from `8.117.72` to the actual current release. *(→ `9.3.0`)*
- [x] Update the package description to include Nursery and all five systems.

## Phase 3: Dependency cleanup

Audited and reworked on 23 July 2026. `pyproject.toml` now separates a minimal
default runtime from optional feature tiers; `requirements.txt` is a pure runtime
lock and dev/CI tooling moved to a new `requirements-dev.txt`.

- [~] Keep only essential runtime dependencies in the default installation. *(dev/test/security/perf tooling, alt DB backends, cloud, graphql, realtime, LMS integrations and deep-learning AI all moved to extras. **Caveat:** the scientific stack — numpy/pandas/scipy/scikit-learn/matplotlib/seaborn/plotly — stays in the default install because it is imported unconditionally across core academics (42 files) and finance (41 files) domains; it is NOT an optional `analytics` extra as the template suggested — see "further investigation")*
- [x] Move testing, formatting and security tools into the `dev` extra. *(`dev` = pytest/ruff/mypy/black/isort/hypothesis/…; also `security` and `perf` extras, and `requirements-dev.txt`)*
- [x] Create separate extras for optional functionality. *(defined: `dev`, `test`, `security`, `perf`, `graphql`, `realtime`, `postgres`, `mysql`, `ai`, `cloud-aws`/`cloud-azure`/`cloud-gcp`/`cloud`, `integrations`, `remote`, `docs`)*
- [x] Do not install packages such as Locust, Semgrep, Bandit and pytest for ordinary users. *(removed from `requirements.txt`; now only in `requirements-dev.txt` / `[dev]` / `[security]` / `[perf]`)*
- [x] Avoid requiring all cloud providers when only one integration is needed. *(per-provider `cloud-aws` / `cloud-azure` / `cloud-gcp`; `cloud` remains as an opt-in "all providers" convenience)*
- [x] Decide whether `requirements.txt` is a lock file or a flexible dependency list. *(kept as a pinned **runtime lock**; ranges live in `pyproject.toml`)*
- [x] If it is a lock file, use exact versions throughout. *(runtime pins are exact `==`; a few security-sensitive/optional lines use `>=` floors deliberately)*
- [x] Keep development and production lock files separate. *(`requirements.txt` = runtime, `requirements-dev.txt` = dev/CI, the latter starting with `-r requirements.txt`)*
- [~] Remove libraries that duplicate the same purpose unless both are genuinely required. *(documented the overlaps — see "further investigation"; not removed yet because each needs a per-call-site code audit)*
- [x] Document the smallest supported installation and optional feature installations. *(README "Installation" now shows the minimal install plus every extra; `requirements.txt` header explains the split)*

Verified: `pyproject.toml` parses, `pip install -e .` still builds `9.3.0`, the 16
extras appear in the installed metadata, and `education-system --help` still runs.

## Phase 4: Testing

Audited and worked on 23 July 2026. All five systems are now collected by the
test suite; per-system smoke tests, migration tests and password-reset-token
tests were added; and separate coverage targets were wired up.

- [x] Include tests for all five systems in `pyproject.toml`. *(`testpaths` now lists shared + nursery + primary + secondary + sixth-form + university; the Makefile `TESTS` var mirrors it. Also fixed two stale sixth-form tests that asserted 9 nav/CLI categories before the "Cross-System" category was added.)*
- [x] Create a consistent test directory for each system. *(all five have a `tests/` dir; each smaller system gained a `test_smoke.py`)*
- [~] Add a per-system smoke test (import → temp DB → services → API routes → CRUD). *(added `test_smoke.py` for nursery/primary/secondary/sixth-form: imports the package + CLI, redirects the system's data dir to a temp path (isolation), registers its API blueprints and asserts a protected endpoint returns 401/403. University already has 567 tests incl. API/service CRUD, and shared auth has a full create/read/update lifecycle. **Deferred:** authenticated CRUD-through-API per small system — kept write-free by design to avoid any chance of touching a real system DB.)*
- [x] Test shared authentication independently of university databases. *(shared/tests use an isolated template auth.db)*
- [x] Test successful and unsuccessful login. *(test_auth_core)*
- [x] Test account lockout and unlock timing. *(test_auth_core / test_security)*
- [x] Test MFA setup, challenge, recovery codes and replay prevention. *(test_mfa_service)*
- [x] Test session creation, expiry, refresh and forced logout. *(test_session_manager)*
- [x] Test password reset token expiry and single use. *(new `test_password_reset.py`: request/validate, single-use-after-reset, expiry on validate & reset, and token rotation invalidating the previous token)*
- [~] Test role and system-access enforcement on every API group. *(`test_permission_isolation` covers RBAC + API 401/403 generically and for nursery; the new smoke tests now assert each of the five systems' API rejects unauthenticated access. **Still partial:** exhaustive role-per-endpoint coverage across every blueprint.)*
- [x] Test migrations from at least the previous supported schema version. *(new `test_migrations.py`: builds a pre-column-add users table, runs `initialise_auth_db`, asserts new columns added, rows preserved, idempotent)*
- [ ] Add GUI tests for controllers and view models without a physical display. *(still only import-level `test_gui_imports` + sixth-form nav-structure checks; controller/view-model logic tests not yet added — see "further investigation")*
- [x] Use temporary directories and databases so tests never modify development data. *(all new tests use `tmp_path`/template copies; smoke tests are write-free and redirect data dirs to temp)*
- [x] Add API integration tests using Flask's test client. *(test_permission_isolation + the five per-system smokes drive a Flask test client; sixth-form `test_api`)*
- [x] Add a small end-to-end test covering login and a protected operation. *(test_permission_isolation: login → JWT → protected route returns 200 for the right principal, 403 otherwise)*
- [~] Publish the real coverage percentage rather than only a Codecov badge. *(added `make coverage-percent`, which prints the real total %; actually publishing it belongs to CI — Phase 5)*
- [x] Set separate coverage targets for shared/core code and legacy interface code. *(`make coverage-shared` enforces `--cov-fail-under=70` on shared/ + core/; interface/legacy code is measured but not gated; documented in `pyproject.toml`)*

## Phase 5: Continuous integration

Added `.github/workflows/ci.yml` on 23 July 2026 (CodeQL and Dependabot already
existed). Jobs: `lint`, `security`, `test`, `systems`, `build`, `docs-links`,
`slow-tests`, and a `ci-success` gate.

- [x] Add a GitHub Actions workflow. *(`ci.yml`, triggered on push/PR to main + manual dispatch, with concurrency cancellation)*
- [x] Run tests on supported Python versions. *(`test` job matrix over Python 3.11 and 3.12)*
- [~] Run Ruff, mypy and security checks in CI. *(all three run; **ruff + mypy are non-blocking** because the codebase carries pre-existing star-import (F405, ~2000 hits) and formatting debt that Phase 6 pays down — flip them to gating there. Bandit high-severity scan (`-lll`, project config) runs in the `security` job; pip-audit runs advisory/non-blocking)*
- [x] Build the package in CI. *(`build` job runs `python -m build` → sdist + wheel)*
- [x] Install the built package and run a console-command smoke test. *(`build` job installs the wheel into a fresh venv and runs `education-system --help`)*
- [~] Check that documentation links are valid. *(`docs-links` job runs lychee offline over the top-level docs — README/CONTRIBUTING/SECURITY/CODE_OF_CONDUCT, verified link-clean. The wider `docs/**` tree has pre-existing broken relative links and is not gated yet — see "further investigation")*
- [x] Cache dependencies to keep builds reasonably fast. *(`actions/setup-python` `cache: pip`, keyed on `requirements*.txt`)*
- [x] Run fast tests on every pull request. *(`test` job runs the `not slow and not gui` suite across all five systems on every PR)*
- [x] Run slow, integration and performance tests separately. *(`slow-tests` job runs `-m "slow or integration"` only on push-to-main / manual dispatch, not on every PR)*
- [x] Add Dependabot or an equivalent dependency update process. *(pre-existing `.github/dependabot.yml`: weekly pip + github-actions updates)*
- [x] Do not allow the main branch to report success when one of the five systems was not tested. *(the `systems` matrix runs shared + all five systems individually and fails a leg that collects zero tests; the `ci-success` gate `needs` it. **Note:** enabling branch protection to make `ci-success` a required check is a repo-settings step, not something the workflow file can do — see "further investigation")*

## Phase 6: Code-quality improvements

- [ ] Re-enable Ruff `F821` checks for undefined names.
- [ ] Stop ignoring all `E` and `F` rules in test files.
- [ ] Gradually enable unused-import and unused-variable checks.
- [ ] Replace broad `except Exception` handlers with specific exceptions where practical.
- [ ] Do not use `except Exception: pass` for tests, migrations, authentication or startup.
- [ ] Add type annotations to all new shared and service-layer code.
- [ ] Keep gradual typing for legacy GUI modules instead of blocking all progress.
- [ ] Use consistent names for each system in flags, package names, routes and internal identifiers.
- [ ] Remove obsolete compatibility wrappers after confirming that nothing imports them.
- [ ] Keep functions small enough to test independently.
- [ ] Move direct SQL out of Tkinter windows, CLI menus and Flask route handlers.
- [ ] Keep logging useful without recording passwords, tokens, recovery codes or sensitive student data.

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

- **Git history purge.** A `student_records.db` blob was committed historically
  and removed from tracking in `f16a8f97` (`auth.db`, encryption keys and `.env`
  were never tracked). Removing the blob from history needs a destructive rewrite
  (git-filter-repo/BFG), a force-push, and coordination with everyone holding
  clones. Decide whether the blob contained real personal data or only demo data
  before spending the rewrite. *(Phase 1)*

### Partially resolved — revisit

- **Fail-fast on essential startup failures.** Auth initialisation raises and
  optional integrations are intentionally non-fatal, but the **Alembic
  `upgrade` step currently only logs a warning** on failure instead of aborting
  startup. Decide whether a failed migration should be fatal (and, if so, how to
  distinguish "essential" from "optional" migrations). *(Phase 1)*
- **Recovery-code authentication path.** `/mfa/verify` uses a dedicated code
  field, but the **login path also accepts a recovery code in the password
  field** as a one-time bypass. Kept for now; confirm whether this dual-purpose
  password field is acceptable or should be split into an explicit
  recovery-code flow. *(Phase 1)*
- **Clean-venv install verification.** `pip install -e .` and the
  `education-system` console command were verified in an existing venv with
  `--no-deps`; a **full install of all runtime dependencies into a brand-new
  virtual environment has not been run** this pass. Worth doing once to catch
  any missing/renamed transitive dependency. *(Phase 2)*

### Worth auditing (surfaced while fixing other items)

- **Five-system consistency in the API/auth layer.** Fixing `_KNOWN_SYSTEMS`
  (which omitted `nursery`) shows this class of "four-of-five-systems" bug
  exists. Sweep for other places that enumerate systems by hand — route
  registration, role/permission maps, `_DEFAULT_ACCOUNTS`, CLI flags, launcher
  dispatch — and confirm nursery (and every system) is present in each. *(Phase 6:
  consistent naming)*
- **Documented default credentials.** The README/docs still list
  `admin`/`admin123` and the other demo logins. These accounts now force a
  password change on first login (`must_change_password`), so the risk is
  reduced, but the docs should either say so explicitly or stop publishing the
  literal passwords. *(Phase 1 follow-up / Documentation)*
- **`analytics` as a true optional extra.** The refactoring template proposed an
  `analytics` extra, but numpy/pandas/scipy/scikit-learn/matplotlib/seaborn are
  imported unconditionally by ~80 core academics/finance modules, so they can't
  be optional without breaking shipped features. Making analytics genuinely
  optional needs those imports guarded (lazy `import` inside functions +
  graceful "install `[analytics]`" messaging) first — a Phase 6 code change.
  Until then the scientific stack stays in the default install. *(Phase 3)*
- **Duplicate-purpose libraries.** Candidates for consolidation, each needing a
  per-call-site audit before removal: **PDF** — `reportlab` (86 files),
  `fpdf2`, `pypdf` and `python-docx` (Word) serve overlapping output needs;
  **plotting** — `matplotlib`, `seaborn` and `plotly` all render charts;
  **fuzzy matching** — `fuzzywuzzy` + `python-Levenshtein` (the latter is a
  speed-up for the former, so probably keep both); **iCal** — `ics`,
  `icalendar` and `recurring-ical-events` overlap. Decide a single library per
  purpose, migrate call sites, then drop the rest. *(Phase 3 / Phase 6)*
- **Transitive security pins vs. optional features.** `aiohttp` and `mcp` carry
  detailed CVE-fix pins but have zero non-test imports in the codebase; they are
  now commented in `requirements.txt`. Confirm whether any optional feature (or
  transitive dep) actually pulls them before deciding to delete the pins
  outright. *(Phase 3)*
- **GUI controller / view-model tests.** Testing is currently import-level
  (`test_gui_imports`) plus a couple of sixth-form nav-structure assertions.
  Extracting controller/view-model logic from the Tkinter windows so it can be
  unit-tested without a display is a real gap — it depends on the interface/
  application-layer separation in the proposed architecture (Phase 6 / migration
  Step 2), so it is best tackled alongside that refactor rather than bolted on. *(Phase 4)*
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
