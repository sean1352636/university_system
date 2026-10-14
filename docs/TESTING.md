# Testing Guide

This is the **top-level entry point** for running the Education
System's test suite. The repository contains 800+ test files organized first
by test scope and then by the production code that owns the behavior.

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

The Makefile uses the active `python` by default. Override it when needed, for
example with `make test PYTHON=python3.12`.

---

## Make targets

| Target | What it runs |
|--------|--------------|
| `make test` | Full suite, **excludes** `slow` and `gui` markers, 60 s per-test timeout |
| `make test-all` | Full suite **including** slow tests, 120 s timeout |
| `make test-cov` | Full suite with coverage report (term + HTML in `htmlcov/`) |
| `make test-coverage` | Same as `test-cov` |
| `make test-coverage-report` | Open the HTML coverage report in your browser |
| `make test-shared` | Platform unit tests (`tests/unit/platform/`) |
| `make test-university` | University tests across unit, integration, contract, end-to-end, smoke, and performance scopes |
| `make test-security` | Independent security tests plus university authentication and security units |
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

### Test layout

Default discovery starts at `tests/`. The first directory is the test scope;
within a scope, directories mirror the owning source package:

```
tests/
├── unit/             # isolated behavior, mirroring src/education_system/
├── integration/      # multi-component and migration tests
├── contract/         # executable API, plugin, portal, and boundary contracts
├── end_to_end/       # browser and full user journeys
├── smoke/            # broad startup and availability checks by system
├── security/         # independent adversarial and fail-closed checks
├── performance/      # benchmarks and Locust load scenarios
└── fixtures/         # reusable fixture bundles; local conftest.py files stay scoped
```

University units mirror the current package pillars at
`tests/unit/systems/university/{application,domains,infrastructure,services,shell}`.
Domain-owned API, CLI, and GUI tests live below that domain's `interfaces/`
directory; application-wide interface tests live below `shell/`.

Tests are not Python packages except for the small `tests.fixtures` support
namespace. Discovery uses `--import-mode=importlib`, so duplicate test basenames
can coexist safely.

### Markers

| Marker | Use |
|--------|-----|
| `slow` | Long-running tests; excluded from `make test`, included in `make test-all` |
| `integration` | Multi-component integration tests |
| `unit` | Pure unit tests |
| `contract` | Executable interface and boundary contracts |
| `end_to_end` | Browser and full user journeys |
| `smoke` | Broad startup and availability checks |
| `gui` | Tests that require tkinter (mocked); excluded from `make test`, run via `make test-gui` |
| `security` | Security-focused tests; run via `make test-security` |
| `performance` | Performance benchmark tests |

Markers are **strict** (`--strict-markers`) — using an undeclared
marker will fail the run, so register any new ones in `pyproject.toml`
first.

### Shared fixtures

The shared `tests/conftest.py` monkey-patches `threading.Thread.start` to
suppress daemon threads (MaintenanceScheduler, LogProcessor, etc.) that
otherwise cause CI timeouts. **Do not remove it** unless you have
verified the underlying schedulers no longer auto-start at import time.

It also loads `tests/fixtures/university.py`. Its autouse database and working
directory behavior is conditional on university-owned paths, preserving
isolation after those tests are separated across multiple top-level scopes.

---

## Running individual tests

The Makefile targets are wrappers around pytest, but you can always
invoke pytest directly for tighter feedback loops:

```bash
# Single test file
python -m pytest \
    tests/unit/platform/identity/auth/test_auth_core.py -v --timeout=60

# Single test class
python -m pytest \
    tests/unit/platform/identity/auth/test_auth_core.py::TestPasswordPolicy -v

# Single test method
python -m pytest \
    tests/unit/platform/identity/auth/test_auth_core.py::TestPasswordPolicy::test_min_length -v

# Filter by name (substring)
python -m pytest -k "password" -v

# Filter by marker
python -m pytest -m "security and not slow" -v
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

1. Choose the scope first, then mirror the owning source package below it.
2. Name it `test_*.py`, classes `Test*`, functions `test_*`.
3. Apply markers as needed (`@pytest.mark.slow`, `@pytest.mark.integration`, etc.).
4. If the test needs a database, use a temporary SQLite file via the existing fixtures rather than the real `student_records.db` / `auth.db`.
5. Run `make test` locally before pushing — CI runs the same target.

For detailed conventions per subsystem (test fixtures, mock helpers,
domain-specific guidelines), follow the per-system links at the top
of this document.
