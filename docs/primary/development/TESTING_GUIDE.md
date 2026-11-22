# Testing Guide

Last Updated: October 2026

This guide covers testing practices for the Primary School Management System.

---

## Running Tests

All commands use the project virtualenv:

```bash
# Run all primary school unit tests
python -m pytest tests/unit/systems/primary/ -v

# The launcher runs the same directory
python -m education_system --primary --test

# Run the smoke test
python -m pytest tests/smoke/primary/ -v

# Run a specific test file
python -m pytest tests/unit/systems/primary/test_paths.py -v

# Run a specific test
python -m pytest tests/unit/systems/primary/test_cli_main.py::test_categories_catalogue_shape -v

# Run with coverage report
python -m pytest tests/unit/systems/primary/ \
    --cov=education_system.systems.primary --cov-report=term-missing -v

# Run with HTML coverage report
python -m pytest tests/unit/systems/primary/ \
    --cov=education_system.systems.primary --cov-report=html -v

# Run tests matching a keyword
python -m pytest tests/unit/systems/primary/ -k "categories" -v

# Stop on first failure
python -m pytest tests/unit/systems/primary/ -x -v
```

---

## Test Directory Structure

Tests live in the top-level `tests/` tree, not inside the system package.

```
tests/
├── unit/systems/primary/
│   ├── conftest.py                # Shared fixtures (fresh_data_dir)
│   ├── test_cli_main.py           # CLI catalogue, guards and helpers
│   ├── test_gui_viewmodel.py      # Display-free GUI helpers
│   └── test_paths.py              # Primary section of education_system.paths
└── smoke/primary/
    └── test_smoke.py              # Imports, path redirection, blueprint registration
```

### Naming Conventions

| Element           | Convention                              | Example                         |
|-------------------|-----------------------------------------|---------------------------------|
| Test file         | `test_<module>.py`                      | `test_cli_main.py`              |
| Test function     | `test_<action>_<scenario>`              | `test_create_requires_name`     |
| Fixture           | Descriptive noun                        | `fresh_data_dir`, `temp_db`     |

---

## Writing Tests

### Basic Test Structure

Each test file targets one module. Use pytest fixtures for setup and teardown. Primary data layers are modules of functions, and most of them connect through `domain/learners/pupils/pupils.py`, so redirect that module's database.

```python
"""Tests for the pupils data layer."""

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils
from education_system.systems.primary.domain.learners.pupils.pupils import ValidationError


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point the data layer at a temporary database."""
    monkeypatch.setattr(pupils, "DB_PATH", tmp_path / "primary.db")
    monkeypatch.setattr(pupils, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(pupils, "_DB_READY", False)


def test_list_is_empty_on_a_new_database():
    assert pupils.list_pupils() == []
```

---

## Testing Patterns

### Temporary Database Fixture

Never run a test against `var/data/primary/primary.db`. Each data module caches its setup in `_DB_READY` and reads its location from `DB_PATH`, so a redirect must reset both:

- Set `DB_PATH` on the module that owns the connection (usually `pupils`).
- Set `_DB_READY` to `False` on every data module the test uses. If you skip this, `init_db()` returns early and the tables are never created in the temporary file.

`tmp_path` is cleaned up by pytest, so the fixture needs no teardown.

### Redirecting the Data Directory

To test path handling itself, use the `fresh_data_dir` fixture in `tests/unit/systems/primary/conftest.py`. It sets `EDU_PRIMARY_DATA_DIR`, reloads `education_system.paths`, and restores the module afterwards.

### Seeding Test Data

Create records through the data layer rather than with raw SQL, so the tests exercise the same validation as the application:

```python
@pytest.fixture
def activity():
    return data.create({"name": "Chess", "category": "Games"})
```

### Testing Exceptions

Use `pytest.raises` to verify error handling:

```python
def test_create_requires_name():
    with pytest.raises(ValidationError):
        data.create({"name": "", "category": "Games"})
```

### Testing GUI Logic

GUI testing with tkinter requires a display. The recommended approach:

1. **Test the data layer directly**. It holds the rules, so most coverage belongs there.
2. **Test module-level helpers without a window**. Importing `gui_main` never constructs one, as `tests/unit/systems/primary/test_gui_viewmodel.py` shows:

```python
from education_system.systems.primary import gui_main


def test_safe_count_formats_value():
    assert gui_main._safe_count(lambda: 42) == "42"
```

3. **Mark tests that need a real window** with `pytest.mark.gui`, because the default run deselects them with `-m "not gui"`. Use a `Tk()` root with `withdraw()` to hide the window:

```python
@pytest.fixture
def root():
    """Create a hidden Tk root for GUI testing."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()
```

### Testing CLI Handlers

CLI handlers can be tested by mocking `input()` and capturing output:

```python
from unittest.mock import patch

from education_system.systems.primary.interfaces.cli.academics.enrichment.clubs import clubs_cli


def test_dispatch_rejects_unknown_label():
    assert clubs_cli.dispatch("Not A Menu Item") is False


def test_prompt_treats_eof_as_empty():
    with patch("builtins.input", side_effect=EOFError):
        assert clubs_cli._prompt("Name: ") == ""
```

---

## What to Test

### Data Layer (highest priority)

Every public function should have tests covering:

| Scenario               | Example                                              |
|------------------------|------------------------------------------------------|
| **Happy path**         | Create a record, verify it exists                    |
| **Invalid input**      | Empty required field raises `ValidationError`        |
| **Not found**          | Get with non-existent ID returns `None`              |
| **Duplicate handling** | Creating a duplicate raises appropriate error        |
| **Update**             | Changed fields persist, unchanged fields are kept    |
| **Delete**             | Record is removed, related records are cleaned up    |
| **Edge cases**         | Boundary values, empty lists, special characters     |

### API Routes

Follow `tests/smoke/primary/test_smoke.py`: register `ALL_BLUEPRINTS` on a Flask app, then check that a protected endpoint refuses an unauthenticated request.

### Validation

- Each validator accepts valid input and returns the cleaned value
- Each validator raises `ValidationError` on invalid input

---

## Coverage Targets

| Layer          | Target |
|----------------|--------|
| Data layer     | 90%+   |
| Validation     | 95%+   |
| CLI handlers   | 70%+   |
| GUI            | 50%+   |
| Overall        | 80%+   |

The data layer carries the most business logic and should have the highest coverage. GUI coverage is lower because tkinter widget interactions are difficult to automate reliably.

### Viewing Coverage

```bash
# Terminal summary with missing lines highlighted
python -m pytest tests/unit/systems/primary/ \
    --cov=education_system.systems.primary \
    --cov-report=term-missing -v

# Generate an HTML report (open htmlcov/index.html in a browser)
python -m pytest tests/unit/systems/primary/ \
    --cov=education_system.systems.primary \
    --cov-report=html -v

# Fail the run if coverage drops below threshold
python -m pytest tests/unit/systems/primary/ \
    --cov=education_system.systems.primary \
    --cov-fail-under=80 -v
```

---

## Shared Test Fixtures (conftest.py)

For fixtures used across multiple test files, add them to `tests/unit/systems/primary/conftest.py`. Fixtures there are automatically discovered by pytest and available to all test files in the same directory without explicit imports.

---

## Tips

- **Keep tests fast**: each test should complete in under 1 second. Temporary SQLite databases are effectively instant.
- **One assertion per concept**: test one behaviour per test. Multiple asserts are fine if they verify the same logical outcome.
- **Test names are documentation**: `test_create_pupil_with_empty_name_raises_validation_error` is better than `test_create_error`.
- **Do not test third-party code**: trust that `sqlite3`, `tkinter`, and `flask` work correctly. Test your logic around them.
- **Avoid testing private functions**: test through the public API. If a private function needs direct testing, consider making it a public utility.
- **Clean up after tests**: use `yield` in fixtures to ensure temp files and database connections are properly closed and removed.
