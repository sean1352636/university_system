# Testing Guide

Last Updated: March 2026

This guide covers testing practices for the Primary School Management System.

---

## Running Tests

All commands use the project virtualenv:

```bash
# Run all primary school tests
python -m pytest education_system/primary_school/tests/ -v

# Run a specific test file
python -m pytest education_system/primary_school/tests/test_pupil_service.py -v

# Run a specific test class or method
python -m pytest education_system/primary_school/tests/test_pupil_service.py::TestPupilService -v
python -m pytest education_system/primary_school/tests/test_pupil_service.py::TestPupilService::test_create_pupil -v

# Run with coverage report
python -m pytest education_system/primary_school/tests/ \
    --cov=education_system.primary_school --cov-report=term-missing -v

# Run with HTML coverage report
python -m pytest education_system/primary_school/tests/ \
    --cov=education_system.primary_school --cov-report=html -v

# Run tests matching a keyword
python -m pytest education_system/primary_school/tests/ -k "attendance" -v

# Stop on first failure
python -m pytest education_system/primary_school/tests/ -x -v
```

---

## Test Directory Structure

```
education_system/primary_school/tests/
├── __init__.py
├── test_pupil_service.py          # Tests for academics/pupils
├── test_subject_service.py        # Tests for academics/subjects
├── test_attendance_service.py     # Tests for academics/attendance
├── test_assessment_service.py     # Tests for academics/assessment
├── ...                            # One test file per service
├── conftest.py                    # Shared fixtures (optional)
└── fixtures/                      # Test data files (optional)
```

### Naming Conventions

| Element           | Convention                              | Example                         |
|-------------------|-----------------------------------------|---------------------------------|
| Test file         | `test_<module>_service.py`              | `test_pupil_service.py`         |
| Test class        | `Test<Service>`                         | `TestPupilService`              |
| Test method       | `test_<action>_<scenario>`              | `test_create_pupil`             |
| Fixture           | Descriptive noun                        | `db_path`, `service`, `sample_pupil` |

---

## Writing Tests

### Basic Test Structure

Each test file targets one service class. Use pytest fixtures for setup and teardown.

```python
"""Tests for the PupilService."""

import os
import sqlite3
import tempfile
import pytest

from education_system.primary_school.modules.domain.academics.pupils.services.pupil_service import (
    PupilService,
)
from education_system.primary_school.core.exceptions import PupilError


@pytest.fixture
def db_path():
    """Create a temporary database with the required schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pupils (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            year_group TEXT NOT NULL,
            key_stage TEXT,
            preferred_name TEXT,
            date_of_birth TEXT,
            gender TEXT,
            class_name TEXT,
            ethnicity TEXT,
            first_language TEXT DEFAULT 'English',
            eal INTEGER DEFAULT 0,
            pupil_premium INTEGER DEFAULT 0,
            free_school_meals INTEGER DEFAULT 0,
            sen_status TEXT DEFAULT 'No SEN',
            looked_after INTEGER DEFAULT 0,
            parent1_name TEXT,
            parent1_email TEXT,
            parent1_phone TEXT,
            parent1_relationship TEXT DEFAULT 'Parent',
            parent2_name TEXT,
            parent2_email TEXT,
            parent2_phone TEXT,
            parent2_relationship TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            emergency_contact_relationship TEXT,
            address TEXT,
            medical_notes TEXT,
            dietary_requirements TEXT,
            photo_consent INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


@pytest.fixture
def service(db_path):
    """Return a PupilService wired to the temporary database."""
    return PupilService(db_path)


class TestPupilService:
    """Tests for PupilService CRUD operations."""

    def test_create_pupil(self, service):
        """Creating a pupil returns its database ID."""
        result = service.create_pupil("Alice", "Smith", "Year 3")
        assert result is not None

    def test_create_pupil_generates_id_with_prefix(self, service, db_path):
        """New pupils get a PRI-prefixed ID."""
        service.create_pupil("Alice", "Smith", "Year 3")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT pupil_id FROM pupils LIMIT 1").fetchone()
        conn.close()
        assert row["pupil_id"].startswith("PRI")

    def test_list_pupils(self, service):
        """Listing pupils returns all created records."""
        service.create_pupil("Alice", "Smith", "Year 3")
        service.create_pupil("Bob", "Jones", "Year 5")
        pupils = service.list_pupils()
        assert len(pupils) == 2

    def test_get_pupil(self, service):
        """Retrieving a pupil by ID returns correct data."""
        service.create_pupil("Alice", "Smith", "Year 3")
        pupil = service.get_pupil(1)
        assert pupil["first_name"] == "Alice"
        assert pupil["last_name"] == "Smith"
        assert pupil["year_group"] == "Year 3"
        assert pupil["key_stage"] == "KS2"

    def test_update_pupil(self, service):
        """Updating a pupil changes the stored values."""
        service.create_pupil("Alice", "Smith", "Year 3")
        service.update_pupil(1, first_name="Alicia")
        pupil = service.get_pupil(1)
        assert pupil["first_name"] == "Alicia"

    def test_delete_pupil(self, service):
        """Deleting a pupil removes it from the database."""
        service.create_pupil("Alice", "Smith", "Year 3")
        service.delete_pupil(1)
        assert service.get_pupil(1) is None

    def test_create_pupil_empty_name_raises(self, service):
        """Creating a pupil with empty first name raises an error."""
        with pytest.raises(Exception):
            service.create_pupil("", "Smith", "Year 3")

    def test_create_pupil_invalid_year_group_raises(self, service):
        """Creating a pupil with invalid year group raises an error."""
        with pytest.raises(Exception):
            service.create_pupil("Alice", "Smith", "Year 99")
```

---

## Testing Patterns

### Temporary Database Fixture

Every test uses its own temporary SQLite database. This avoids interference between tests and prevents changes to the real database.

```python
@pytest.fixture
def db_path():
    """Create a fresh temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    # Create only the tables your service needs
    conn.execute("CREATE TABLE IF NOT EXISTS ...")
    conn.commit()
    conn.close()

    yield path

    # Cleanup: remove the temp file
    os.unlink(path)
```

Key points:
- Use `tempfile.mkstemp()` for a unique file per test.
- Create only the tables your specific test needs.
- `yield` the path so cleanup runs after the test, even on failure.
- Always `os.unlink()` in the teardown to avoid temp file accumulation.

### Service Fixture

Build on the `db_path` fixture to provide a ready-to-use service:

```python
@pytest.fixture
def service(db_path):
    """Return a service instance connected to the temp database."""
    return SomeService(db_path)
```

### Using `set_db_path()` for Integration Tests

For tests that need to exercise code paths that call `get_db_path()` internally (rather than accepting `db_path` as a parameter):

```python
from education_system.primary_school.infrastructure.database.db import set_db_path

@pytest.fixture(autouse=True)
def override_db(db_path):
    """Point the global DB path at the temp database."""
    set_db_path(db_path)
    yield
    set_db_path(None)  # Reset to default
```

### Seeding Test Data

For tests that need pre-existing data, create a helper fixture:

```python
@pytest.fixture
def sample_pupils(service):
    """Seed a set of test pupils and return their IDs."""
    ids = []
    for name, year in [("Alice", "Year 1"), ("Bob", "Year 3"), ("Charlie", "Year 6")]:
        result = service.create_pupil(name, "Test", year)
        ids.append(result)
    return ids
```

### Testing Exceptions

Verify that domain exceptions are raised with appropriate messages:

```python
def test_create_with_invalid_data_raises_domain_error(self, service):
    with pytest.raises(PupilError, match="First name"):
        service.create_pupil("", "Smith", "Year 3")
```

### Mocking the GUI

GUI classes should not be tested directly via tkinter (which requires a display). Instead:

1. **Test the service layer thoroughly** -- the GUI is a thin wrapper.
2. **For GUI unit tests**, mock the service and verify calls:

```python
from unittest.mock import MagicMock, patch


def test_gui_on_add_calls_service(self):
    """Verify the GUI delegates to the service on add."""
    mock_service = MagicMock()
    mock_service.list_activities.return_value = []

    with patch(
        "education_system.primary_school.modules.domain.pupil_life.enrichment"
        ".gui.enrichment_gui.EnrichmentService",
        return_value=mock_service,
    ):
        # Instantiation and interaction would go here
        # In practice, focus testing effort on the service layer
        pass
```

3. **For end-to-end GUI tests**, use the `Tk()` root with `withdraw()` to hide the window:

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

### Testing CLI Menus

CLI menus can be tested by mocking `input()` and `print()`:

```python
from unittest.mock import patch


def test_cli_list_pupils(service, db_path):
    """CLI list option displays pupils."""
    service.create_pupil("Alice", "Smith", "Year 3")

    with patch("builtins.input", side_effect=["1", "0"]):
        with patch("builtins.print") as mock_print:
            from education_system.primary_school.cli.menus.pupil_cli import pupils_menu
            pupils_menu(None)

    output = " ".join(str(c) for c in mock_print.call_args_list)
    assert "Alice" in output
```

---

## What to Test

### Service Layer (highest priority)

Every service method should have tests covering:

| Scenario               | Example                                              |
|------------------------|------------------------------------------------------|
| **Happy path**         | Create a record, verify it exists                    |
| **Invalid input**      | Empty required field raises `ValidationError`        |
| **Not found**          | Get with non-existent ID returns `None`              |
| **Duplicate handling** | Creating a duplicate raises appropriate error        |
| **Update**             | Changed fields persist, unchanged fields are kept    |
| **Delete**             | Record is removed, related records are cleaned up    |
| **Edge cases**         | Boundary values, empty lists, special characters     |

### Infrastructure Layer

- `connect()` returns a connection with `row_factory = sqlite3.Row`
- `transaction()` commits on success, rolls back on exception
- `set_db_path()` / `get_db_path()` override works correctly
- Schema `initialise_database()` creates all tables without error

### Validation

- Each validator accepts valid input and returns the cleaned value
- Each validator raises `ValidationError` on invalid input

---

## Coverage Targets

| Layer          | Target |
|----------------|--------|
| Service layer  | 90%+   |
| Infrastructure | 80%+   |
| Validation     | 95%+   |
| CLI menus      | 70%+   |
| GUI            | 50%+   |
| Overall        | 80%+   |

The service layer carries the most business logic and should have the highest coverage. GUI coverage is lower because tkinter widget interactions are difficult to automate reliably.

### Viewing Coverage

```bash
# Terminal summary with missing lines highlighted
python -m pytest education_system/primary_school/tests/ \
    --cov=education_system.primary_school \
    --cov-report=term-missing -v

# Generate an HTML report (open htmlcov/index.html in a browser)
python -m pytest education_system/primary_school/tests/ \
    --cov=education_system.primary_school \
    --cov-report=html -v

# Fail the run if coverage drops below threshold
python -m pytest education_system/primary_school/tests/ \
    --cov=education_system.primary_school \
    --cov-fail-under=80 -v
```

---

## Shared Test Fixtures (conftest.py)

For fixtures used across multiple test files, create a `conftest.py` in the tests directory:

```python
"""Shared test fixtures for the Primary School Management System."""

import os
import sqlite3
import tempfile
import pytest

from education_system.primary_school.infrastructure.database.db import set_db_path


@pytest.fixture
def base_db_path():
    """Create a temporary database with core tables only."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'teacher',
            display_name TEXT,
            email TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

    set_db_path(path)
    yield path
    set_db_path(None)
    os.unlink(path)
```

Fixtures in `conftest.py` are automatically discovered by pytest and available to all test files in the same directory without explicit imports.

---

## Tips

- **Keep tests fast**: each test should complete in under 1 second. Temporary SQLite databases are effectively instant.
- **One assertion per concept**: test one behaviour per method. Multiple asserts are fine if they verify the same logical outcome.
- **Test names are documentation**: `test_create_pupil_with_empty_name_raises_validation_error` is better than `test_create_error`.
- **Do not test third-party code**: trust that `sqlite3`, `tkinter`, and `flask` work correctly. Test your logic around them.
- **Avoid testing private methods**: test through the public API. If a private method needs direct testing, consider making it a public utility.
- **Clean up after tests**: use `yield` in fixtures to ensure temp files and database connections are properly closed and removed.
