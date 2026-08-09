# Testing Guide

This is the **top-level entry point** for running the Education
System's test suite. The repository contains 450+ test files spread
across the four subsystems and the shared infrastructure layer.

For deeper, system-specific testing notes, see:

- [`docs/university/development/TESTING_GUIDE.md`](university/development/TESTING_GUIDE.md)
- [`docs/sixth_form/development/TESTING_GUIDE.md`](sixth_form/development/TESTING_GUIDE.md)
- [`docs/secondary/development/TESTING_GUIDE.md`](secondary/development/TESTING_GUIDE.md)
- [`docs/primary/development/TESTING_GUIDE.md`](primary/development/TESTING_GUIDE.md)

---

## Quick start

```bash
# Install dev dependencies (pytest, pytest-cov, pytest-timeout, ruff, mypy, bandit)
make install-dev

# Run the full test suite (excludes slow + GUI tests)
make test

# Run everything including slow tests (longer timeout)
make test-all
```

The venv used by the Makefile lives at `/home/seancatchpole989/venv/bin/`.
If your venv is elsewhere, edit `VENV` at the top of the `Makefile` or
invoke pytest directly.

---

## Make targets

| Target | What it runs |
|--------|--------------|
| `make test` | Full suite, **excludes** `slow` and `gui` markers, 60 s per-test timeout |
| `make test-all` | Full suite **including** slow tests, 120 s timeout |
| `make test-cov` | Full suite with coverage report (term + HTML in `htmlcov/`) |
| `make test-coverage` | Same as `test-cov` |
| `make test-coverage-report` | Open the HTML coverage report in your browser |
| `make test-shared` | Only the shared infrastructure tests (`education_system/shared/tests/`) |
| `make test-university` | Only the university subsystem tests |
| `make test-college` | Only the college subsystem tests |
| `make test-secondary` | Only the secondary school subsystem tests |
| `make test-primary` | Only the primary school subsystem tests |
| `make test-integration` | Cross-system integration tests (`shared/tests/test_cross_system.py`) |
| `make test-security` | Tests marked `@pytest.mark.security` only |
| `make test-gui` | Tests marked `@pytest.mark.gui` only (mocked tkinter) |
| `make test-auth` | Auth-infrastructure tests (auth core, password manager, MFA, sessions, security) |
| `make check` | Lint + run the default test suite (CI gate) |

Run `make help` for the full target list.

---

## Pytest configuration

The project uses **pytest** with parallel execution via **pytest-xdist**
(`-n auto --dist worksteal`) and a 60-second per-test timeout via
**pytest-timeout**. Markers and other settings live in
`pyproject.toml` under `[tool.pytest.ini_options]`.

### Test paths

The default test discovery covers all five test roots:

```
education_system/shared/tests
education_system/university_system/tests
education_system/sixth_form/tests
education_system/secondary/tests
education_system/primary/tests
```

### University test layout (feature-first)

`university_system/tests/` mirrors the source `modules/` tree — one folder
per feature, holding CLI **and** GUI tests together. Interface type is a
**marker**, not a directory:

```
university_system/tests/
├── core/            # cli/core utility tests
├── domain/          # one folder per feature (finance, academics, health …)
│   └── finance/     #   CLI + GUI tests co-located; GUI files carry pytest.mark.gui
├── infrastructure/  # auth, database, email, security, validation
├── services/        # cross-cutting services (was modules/services)
├── shared/          # university-shared (analytics, gui widgets, utils)
├── integration/     # cross-feature journeys, e2e, performance
├── sal/             # the SAL subsystem suite
├── scripts/         # tests for one-off maintenance scripts
├── smoke/           # broad smoke tests
└── _support/        # non-pytest helpers (report/runner scripts)
```

GUI tests declare `pytestmark = pytest.mark.gui` at module level, so
`-m gui` / `-m "not gui"` select them reliably regardless of location.
There are no `__init__.py` packages — discovery uses
`--import-mode=importlib`.

A handful of import-heavy directories under `university_system/tests/domain/`
and `.../infrastructure/email/gui` are excluded by `--ignore` flags in
`addopts` so the fast suite never imports them. See `pyproject.toml` for
the current list.

### Markers

| Marker | Use |
|--------|-----|
| `slow` | Long-running tests; excluded from `make test`, included in `make test-all` |
| `integration` | Multi-component integration tests |
| `unit` | Pure unit tests |
| `gui` | Tests that require tkinter (mocked); excluded from `make test`, run via `make test-gui` |
| `security` | Security-focused tests; run via `make test-security` |
| `performance` | Performance benchmark tests |

Markers are **strict** (`--strict-markers`) — using an undeclared
marker will fail the run, so register any new ones in `pyproject.toml`
first.

### conftest.py at the repo root

The root `conftest.py` monkey-patches `threading.Thread.start` to
suppress daemon threads (MaintenanceScheduler, LogProcessor, etc.) that
otherwise cause CI timeouts. **Do not remove it** unless you have
verified the underlying schedulers no longer auto-start at import time.

---

## Running individual tests

The Makefile targets are wrappers around pytest, but you can always
invoke pytest directly for tighter feedback loops:

```bash
# Single test file
/home/seancatchpole989/venv/bin/pytest \
    education_system/shared/tests/test_auth_core.py -v --timeout=60

# Single test class
/home/seancatchpole989/venv/bin/pytest \
    education_system/shared/tests/test_auth_core.py::TestPasswordPolicy -v

# Single test method
/home/seancatchpole989/venv/bin/pytest \
    education_system/shared/tests/test_auth_core.py::TestPasswordPolicy::test_min_length -v

# Filter by name (substring)
/home/seancatchpole989/venv/bin/pytest -k "password" -v

# Filter by marker
/home/seancatchpole989/venv/bin/pytest -m "security and not slow" -v
```

> **Tip:** disable parallelism with `-n0` when debugging a single
> failing test — xdist's worker capture can hide print/debugger output.

---

## Coverage

```bash
make test-cov              # generates htmlcov/ and prints term-missing
make test-coverage-report  # opens htmlcov/index.html in browser
```

Coverage configuration lives in `pyproject.toml` under
`[tool.coverage.run]` and `[tool.coverage.report]`. Tests, `__pycache__`,
and venvs are excluded from the source tree.

---

## CI helpers

| Target | Used by |
|--------|---------|
| `make ci` | `clean + lint + test-cov + security-scan` — full CI gate |
| `make check` | `lint + test` — quick local pre-commit check |
| `make security-scan` | `bandit -r education_system/ -c pyproject.toml -lll` |
| `make lint` | `ruff check education_system/` |
| `make type-check` | `mypy education_system/ --ignore-missing-imports` |

---

## Common issues

| Problem | Fix |
|---------|-----|
| `tkinter` errors in non-GUI tests | The tests use `monkeypatch` to mock `tkinter`; if you see real tk errors, you're probably missing `gui` marker on a tk-using test |
| Test timeouts on slow machines | Increase the timeout: `--timeout=120` or `--timeout=300` |
| `xdist` worker crashes | Run with `-n0` to disable parallelism and isolate the failure |
| `database is locked` errors | A previous test left a connection open; run in serial mode or check for missing `conn.close()` calls |
| Import errors for optional libs (`spacy`, `transformers`, `pyaudio`, `pyttsx3`, `speech_recognition`) | Optional features; install only if needed for the specific tests you're running |

---

## Adding new tests

1. Place the test file under the matching subsystem's `tests/` directory.
2. Name it `test_*.py`, classes `Test*`, functions `test_*`.
3. Apply markers as needed (`@pytest.mark.slow`, `@pytest.mark.integration`, etc.).
4. If the test needs a database, use a temporary SQLite file via the existing fixtures rather than the real `student_records.db` / `auth.db`.
5. Run `make test` locally before pushing — CI runs the same target.

For detailed conventions per subsystem (test fixtures, mock helpers,
domain-specific guidelines), follow the per-system links at the top
of this document.
