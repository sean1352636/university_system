# College System -- Testing Guide

This document covers the test infrastructure, conventions, and practices for the Sixth Form College Management System.

---

## Test Framework

The project uses **pytest** (>= 7.0) with the following additional packages:

| Package         | Purpose                              |
|-----------------|--------------------------------------|
| `pytest-cov`    | Code coverage reporting              |
| `pytest-xdist`  | Parallel test execution (`-n auto`)  |
| `pytest-mock`   | `mocker` fixture for mocking         |

Configuration is in `pyproject.toml` under `[tool.pytest.ini_options]`. Tests run in parallel by default (`-n auto`).


## Running Tests

### Full Suite

```bash
# Via the unified launcher
python -m education_system --college --test

# Or directly with pytest
python -m pytest tests/unit/systems/sixth_form/ -v --tb=short

# Smoke test
python -m pytest tests/smoke/sixth_form/ -v
```

### Single Test File

```bash
python -m pytest tests/unit/systems/sixth_form/domain/academics/library/test_library.py -v
```

### Single Test Function

```bash
python -m pytest tests/unit/systems/sixth_form/interfaces/api/test_api.py::test_health -v
```

### With Coverage

```bash
python -m pytest tests/unit/systems/sixth_form/ \
  --cov=education_system.systems.sixth_form \
  --cov-report=html \
  --cov-report=term-missing
```

Coverage configuration is in `pyproject.toml` under `[tool.coverage.*]`. Branch coverage is enabled. The HTML report is written to `htmlcov/`.

### Serial Execution

```bash
python -m pytest tests/unit/systems/sixth_form/ -n0
```

### Using Markers

```bash
# Run only slow tests
python -m pytest -m slow

# Exclude slow tests
python -m pytest -m "not slow"

# Run only integration tests
python -m pytest -m integration
```

Available markers include: `slow`, `integration`, `unit`, `contract`, `end_to_end`, `smoke`, `gui`, `security`, `performance`.


## Test Organisation

Sixth form tests live in `tests/unit/systems/sixth_form/`, mirroring the package:

```
tests/unit/systems/sixth_form/
    conftest.py                         # Shared fixtures
    domain/                             # academics/, admissions/, assessment/, finance/,
                                        # governance/, learners/, operations/, progression/
    domains/                            # communications/, finance/, operations/
    infrastructure/                     # test_log_store.py, test_paths.py
    interfaces/
        api/test_api.py                 # Standalone REST API tests
        cli/
        gui/

tests/smoke/sixth_form/test_smoke.py    # Imports the package and registers the API blueprints
```

Test packages are not stored inside the production package. Tests have no `__init__.py` files, and run in pytest's `importlib` mode, so test file names may repeat across folders.


## Fixtures (conftest.py)

The shared `conftest.py` provides fixtures that tests can use. Understanding these fixtures is essential for writing new tests.

### Database Fixtures

There is no shared `db_path` fixture. Each domain module holds its location in a `DB_PATH` attribute, so a fixture redirects that attribute to a temporary file and resets the module's `_DB_READY` flag. Any test that misses this writes to the live `var/data/sixth_form/sixthform.db`.

#### `fresh_ay_db`

Points the Academic Year data module at a new SQLite file, and returns the module so tests can call its API directly:

```python
@pytest.fixture
def fresh_ay_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ay.db"
    from education_system.systems.sixth_form.domain.academics.academic_year import (
        academic_year as data,
    )
    monkeypatch.setattr(data, "DB_PATH", str(db_path))
    monkeypatch.setattr(data, "_DB_READY", set())
    ...
    data.init_db()
    return data
```

#### `feature_db`

Redirects every module in `_FEATURE_MODULES` at one temporary database, points the parent portal's auth mirror at a temporary `auth.db`, builds the schemas through the real `init_db` chains, and seeds two students. It returns a namespace holding the imported modules (`feature_db.mods`) and the seeded ids.

### Signed-In Principal

`_signed_in_records_writer` is an autouse fixture. Student and other record writes check the signed-in principal and refuse an anonymous call, so tests run as a staff member with the capabilities to manage records. A test can sign someone else in through `access._current`, or bind `access.ANONYMOUS` to check a refusal.

### Sample Data

Create records through the domain module's own functions, in the test or in a fixture local to its folder. Several folders have their own `conftest.py`, including `domain/admissions/` and `domain/academics/attendance/`.

### API Test Fixtures

For testing the standalone REST API:

```python
@pytest.fixture
def client(feature_db):
    from education_system.api.sixth_form import create_app
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()
```

For blueprints, `tests/smoke/sixth_form/test_smoke.py` registers them on a bare Flask app.


## Writing New Tests

### Domain-Level Tests

Domain tests validate business logic directly, without going through the API layer.

```python
"""Tests for the foo module."""

import pytest


@pytest.fixture
def foo(tmp_path, monkeypatch):
    from education_system.systems.sixth_form.domain.academics.foo import foo as data
    monkeypatch.setattr(data, "DB_PATH", str(tmp_path / "sixthform.db"))
    monkeypatch.setattr(data, "_DB_READY", False)
    data.init_db()
    return data


def test_create_foo(foo):
    result = foo.create_foo({"name": "Test Foo"})
    assert result.name == "Test Foo"
    assert result.foo_id is not None


def test_create_foo_missing_name(foo):
    with pytest.raises(foo.ValidationError):
        foo.create_foo({"name": ""})


def test_get_foo_not_found(foo):
    assert foo.get_foo(9999) is None


def test_list_foos(foo):
    foo.create_foo({"name": "A"})
    foo.create_foo({"name": "B"})
    assert len(foo.list_foos()) >= 2


def test_update_foo(foo):
    created = foo.create_foo({"name": "Original"})
    updated = foo.update_foo(created.foo_id, {"name": "Updated"})
    assert updated.name == "Updated"


def test_delete_foo(foo):
    created = foo.create_foo({"name": "ToDelete"})
    foo.delete_foo(created.foo_id)
    assert foo.get_foo(created.foo_id) is None
```

### API-Level Tests

API tests exercise the full request/response cycle through Flask's test client.

```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_parent_routes_require_a_token(client):
    assert client.get("/api/parent/me").status_code == 401
```

### Key Conventions

1. **Group tests by module**, in a folder that mirrors the package. Plain functions and `TestXxx` classes are both used.
2. **Test function names** start with `test_` and describe the scenario: `test_create_student`, `test_create_student_validates_name`, `test_get_student_not_found`.
3. **Use fixtures** rather than creating data manually in each test. Add new fixtures to a `conftest.py` if they will be reused.
4. **Assert specific values**, not just truthiness. For example, check `student.year_group == 12` rather than `assert student.year_group`.
5. **Test error paths** using `pytest.raises` for expected exceptions.
6. **Each test is independent.** A fixture that redirects `DB_PATH` to `tmp_path` gives every test a fresh database.


## Mocking Patterns

Use `pytest-mock` (provides the `mocker` fixture) when you need to isolate a unit from its dependencies.

### Mocking a Domain Function

```python
def test_route_handles_missing_student(client, mocker):
    mocker.patch(
        "education_system.systems.sixth_form.domain.learners.students.students.get_student",
        return_value=None,
    )
    ...
```

### Mocking Database Connections

If you need to test behaviour when the database is unavailable:

```python
import sqlite3


def test_handles_db_failure(foo, mocker):
    mocker.patch.object(foo, "_connect", side_effect=sqlite3.OperationalError("unavailable"))
    with pytest.raises(sqlite3.OperationalError):
        foo.list_foos()
```

### General Guidelines for Mocking

- Prefer testing against the real (temporary) database when possible. Mocking should be reserved for external services, error conditions, or situations where using the real dependency is impractical.
- Patch at the point of use, not at the point of definition.
- Keep mocked return values realistic -- use the same dataclass or dict structure the real code returns.


## Coverage

Coverage settings in `pyproject.toml`:

- **Source**: `src/education_system`
- **Omitted**: test files, `__pycache__`, virtual environments
- **Branch coverage**: enabled
- **Report**: shows missing lines, does not skip covered files

Generate an HTML coverage report:

```bash
python -m pytest tests/unit/systems/sixth_form/ \
  --cov=education_system.systems.sixth_form \
  --cov-report=html
open htmlcov/index.html
```
