# Secondary School Management System - Testing Guide

> Last Updated: March 2026

This guide covers how to run, write, and organize tests for the Secondary School Management System.

## Table of Contents

- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Shared Fixtures](#shared-fixtures)
- [Writing Tests](#writing-tests)
- [Testing Patterns](#testing-patterns)
- [Naming Conventions](#naming-conventions)
- [Coverage](#coverage)

---

## Running Tests

All commands use the project virtual environment.

### Basic Commands

```bash
# Run all secondary school tests
python -m pytest education_system/secondary_school/tests/ -v

# Run a specific test file
python -m pytest education_system/secondary_school/tests/test_student_service.py -v

# Run a specific test class
python -m pytest education_system/secondary_school/tests/test_student_service.py::TestStudentService -v

# Run a single test method
python -m pytest education_system/secondary_school/tests/test_student_service.py::TestStudentService::test_create_student -v
```

### Useful Flags

```bash
# Stop on first failure
python -m pytest education_system/secondary_school/tests/ -x

# Show print output
python -m pytest education_system/secondary_school/tests/ -s

# Run tests matching a keyword
python -m pytest education_system/secondary_school/tests/ -k "student"

# Verbose with short traceback
python -m pytest education_system/secondary_school/tests/ -v --tb=short

# Parallel execution (if pytest-xdist is installed)
python -m pytest education_system/secondary_school/tests/ -n auto
```

### Coverage

```bash
# Run with coverage report
python -m pytest education_system/secondary_school/tests/ \
    --cov=education_system.secondary_school \
    --cov-report=term-missing \
    -v

# Generate HTML coverage report
python -m pytest education_system/secondary_school/tests/ \
    --cov=education_system.secondary_school \
    --cov-report=html:education_system/secondary_school/tests/htmlcov

# Coverage for a specific module
python -m pytest education_system/secondary_school/tests/test_grade_service.py \
    --cov=education_system.secondary_school.modules.domain.academics.grades \
    --cov-report=term-missing
```

---

## Test Structure

```
secondary_school/tests/
├── conftest.py                      # Shared fixtures (db_path, services, sample data)
├── __init__.py
├── test_student_service.py          # Student service tests
├── test_subject_service.py          # Subject service tests
├── test_enrollment_service.py       # Enrollment service tests
├── test_grade_service.py            # Grade service tests
├── test_attendance_service.py       # Attendance service tests
├── test_auth.py                     # Authentication tests
└── test_api.py                      # REST API endpoint tests
```

Tests are organized by service. Each test file corresponds to a service class and contains a test class grouping related test methods.

---

## Shared Fixtures

All shared fixtures live in `tests/conftest.py`. Pytest automatically discovers and makes them available to every test file in the directory.

### `db_path` -- Temporary Database

The most important fixture. Creates a fresh SQLite database in a temp directory for each test, initializes the schema, seeds default users, and cleans up afterward.

```python
@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for each test."""
    path = str(tmp_path / "test_secondary.db")
    set_db_path(path)
    initialise_database(path)
    seed_default_users(path)
    yield path
    set_db_path(None)
```

Key points:
- Uses pytest's built-in `tmp_path` fixture for automatic cleanup.
- Calls `set_db_path(path)` to override the global DB path so services use the test database.
- Resets the override to `None` after the test completes.
- Each test gets a completely isolated database -- no cross-test contamination.

### Service Fixtures

Pre-configured service instances using the test database:

```python
@pytest.fixture
def student_service(db_path):
    return StudentService(db_path)

@pytest.fixture
def subject_service(db_path):
    return SubjectService(db_path)

@pytest.fixture
def enrollment_service(db_path):
    return EnrollmentService(db_path)

@pytest.fixture
def grade_service(db_path):
    return GradeService(db_path)

@pytest.fixture
def attendance_service(db_path):
    return AttendanceService(db_path)
```

### Sample Data Fixtures

Pre-created records for tests that need existing data:

```python
@pytest.fixture
def sample_student(student_service):
    """A Year 9 student for testing."""
    return student_service.create_student(
        first_name="John", last_name="Doe",
        email="john.doe@school.local",
        year_group="9", form_group="9A",
    )

@pytest.fixture
def sample_subject(subject_service):
    """A KS3 Mathematics subject for testing."""
    return subject_service.create_subject(
        subject_code="MAT01", title="Mathematics",
        department="Maths", key_stage="KS3",
        is_core=True, capacity=30,
    )

@pytest.fixture
def enrolled_student(sample_student, sample_subject, enrollment_service):
    """A student enrolled in a subject."""
    enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
    return sample_student
```

### API Fixtures

For testing REST API endpoints:

```python
@pytest.fixture
def api_client(db_path):
    """Flask test client."""
    from education_system.secondary_school.api.api_server import create_app
    app = create_app(db_path)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def api_token(api_client):
    """JWT token from admin login."""
    response = api_client.post("/api/auth/login", json={
        "username": "admin", "password": "Admin@123",
    })
    return response.get_json()["token"]

@pytest.fixture
def auth_headers(api_token):
    """Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {api_token}"}
```

---

## Writing Tests

### Example: Testing a Service

Here is a complete example following the project's established patterns.

```python
"""Tests for RewardsService."""

import pytest
from education_system.secondary_school.core.exceptions import RewardsError, ValidationError
from education_system.secondary_school.modules.domain.pastoral_care.rewards.services.rewards_service import (
    RewardsService,
)


@pytest.fixture
def rewards_service(db_path):
    """Create a RewardsService with the test database."""
    return RewardsService(db_path)


@pytest.fixture
def sample_reward(rewards_service, sample_student):
    """Create a sample reward for testing."""
    return rewards_service.award_reward(
        student_id=sample_student["id"],
        category="achievement",
        points=5,
    )


class TestRewardsService:
    """Group all reward-related tests in a class."""

    # -- Happy path tests -----------------------------------------

    def test_award_reward(self, rewards_service, sample_student):
        """Test creating a reward returns correct data."""
        reward = rewards_service.award_reward(
            student_id=sample_student["id"],
            category="effort",
            points=3,
        )
        assert reward["student_id"] == sample_student["id"]
        assert reward["category"] == "effort"
        assert reward["points"] == 3

    def test_get_reward(self, rewards_service, sample_reward):
        """Test retrieving a reward by ID."""
        found = rewards_service.get_reward(sample_reward["id"])
        assert found is not None
        assert found["id"] == sample_reward["id"]

    def test_list_rewards_filtered(self, rewards_service, sample_student):
        """Test listing rewards with a filter."""
        rewards_service.award_reward(student_id=sample_student["id"], category="effort")
        rewards_service.award_reward(student_id=sample_student["id"], category="homework")
        results = rewards_service.list_rewards(student_id=sample_student["id"])
        assert len(results) == 2

    def test_delete_reward(self, rewards_service, sample_reward):
        """Test deleting a reward removes it."""
        rewards_service.delete_reward(sample_reward["id"])
        assert rewards_service.get_reward(sample_reward["id"]) is None

    # -- Validation tests -----------------------------------------

    def test_award_reward_invalid_type(self, rewards_service, sample_student):
        """Test that invalid reward type raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid reward type"):
            rewards_service.award_reward(
                student_id=sample_student["id"],
                category="effort",
                reward_type="nonexistent",
            )

    def test_award_reward_empty_category(self, rewards_service, sample_student):
        """Test that empty category raises ValidationError."""
        with pytest.raises(ValidationError):
            rewards_service.award_reward(
                student_id=sample_student["id"],
                category="",
            )

    # -- Error path tests -----------------------------------------

    def test_award_reward_nonexistent_student(self, rewards_service):
        """Test that awarding to missing student raises RewardsError."""
        with pytest.raises(RewardsError, match="not found"):
            rewards_service.award_reward(student_id=9999, category="effort")

    def test_delete_nonexistent_reward(self, rewards_service):
        """Test deleting missing reward raises RewardsError."""
        with pytest.raises(RewardsError, match="not found"):
            rewards_service.delete_reward(9999)

    def test_get_nonexistent_reward(self, rewards_service):
        """Test get returns None for missing reward."""
        assert rewards_service.get_reward(9999) is None
```

### Test Anatomy

Every test method follows this structure:

1. **Arrange** -- Set up data (often handled by fixtures)
2. **Act** -- Call the service method
3. **Assert** -- Verify the result

```python
def test_create_student(self, student_service):
    # Arrange: nothing extra needed (db_path fixture provides clean DB)

    # Act
    student = student_service.create_student(
        first_name="Alice", last_name="Smith",
        email="alice@school.local", year_group="7",
    )

    # Assert
    assert student["first_name"] == "Alice"
    assert student["student_id"].startswith("SEC")
    assert student["key_stage"] == "KS3"
    assert student["status"] == "active"
```

---

## Testing Patterns

### 1. Database Isolation

Every test gets a fresh temporary database via the `db_path` fixture. No manual cleanup is needed.

```python
def test_independent_a(self, student_service):
    student_service.create_student(first_name="A", last_name="A")
    assert len(student_service.list_students()) == 1

def test_independent_b(self, student_service):
    # This test has a clean DB -- the student from test_a does not exist
    assert len(student_service.list_students()) == 0
```

### 2. Testing Validation Errors

Use `pytest.raises` with the `match` parameter to verify the error message:

```python
def test_validates_email(self, student_service):
    with pytest.raises(ValidationError):
        student_service.create_student(
            first_name="Alice", last_name="Smith",
            email="not-an-email",
        )
```

### 3. Testing Domain Errors

```python
def test_get_nonexistent_student(self, student_service):
    assert student_service.get_student(9999) is None

def test_delete_nonexistent_raises(self, service):
    with pytest.raises(SomeModuleError, match="not found"):
        service.delete_item(9999)
```

### 4. Testing with Related Data

Use fixture composition to build up test scenarios:

```python
@pytest.fixture
def enrolled_student(sample_student, sample_subject, enrollment_service):
    """Student enrolled in a subject -- depends on both sample fixtures."""
    enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
    return sample_student

def test_grade_requires_enrollment(self, grade_service, enrolled_student, sample_subject):
    grade = grade_service.record_grade(
        student_id=enrolled_student["id"],
        subject_id=sample_subject["id"],
        score=85,
    )
    assert grade["grade"] == "8"  # GCSE scale: 80-89 = grade 8
```

### 5. Mocking the GUI

GUI tests are not required for service-level coverage. If you need to test GUI components, mock the service layer:

```python
from unittest.mock import MagicMock, patch

def test_panel_refresh_calls_service():
    """Verify the panel calls list_rewards on refresh."""
    with patch(
        "education_system.secondary_school.modules.domain.pastoral_care."
        "rewards.services.rewards_service.RewardsService"
    ) as MockService:
        mock_service = MockService.return_value
        mock_service.list_rewards.return_value = []

        # Create a minimal Tk root for testing
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            panel = RewardsPanel(root)
            mock_service.list_rewards.assert_called()
        finally:
            root.destroy()
```

In practice, focus your testing effort on service-layer tests. GUI tests are optional and should only verify wiring, not business logic.

### 6. Testing API Endpoints

Use the `api_client` and `auth_headers` fixtures:

```python
def test_list_students_api(self, api_client, auth_headers):
    response = api_client.get("/api/students", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)

def test_create_student_api(self, api_client, auth_headers):
    response = api_client.post("/api/students", headers=auth_headers, json={
        "first_name": "Alice",
        "last_name": "Smith",
        "year_group": "9",
    })
    assert response.status_code == 201
    assert response.get_json()["student_id"].startswith("SEC")

def test_unauthorized_access(self, api_client):
    response = api_client.get("/api/students")
    assert response.status_code == 401
```

---

## Naming Conventions

### Files

| Pattern | Example |
|---------|---------|
| Service tests | `test_student_service.py` |
| Auth tests | `test_auth.py` |
| API tests | `test_api.py` |
| Module-specific | `test_<module>_service.py` |

### Classes

```python
class TestStudentService:       # Group by service class
class TestStudentCreation:      # Or by feature area (for large modules)
class TestStudentValidation:
```

### Methods

Use descriptive names that explain what is being tested and what the expected outcome is:

```python
# Good -- clearly states what is tested and expected
def test_create_student(self, ...):
def test_create_student_ks4(self, ...):
def test_create_student_validates_name(self, ...):
def test_create_student_validates_email(self, ...):
def test_get_nonexistent_student(self, ...):
def test_list_students_filter_year(self, ...):
def test_delete_student(self, ...):

# Bad -- too vague
def test_student(self, ...):
def test_error(self, ...):
def test_it_works(self, ...):
```

### Fixture Names

```python
# Service fixtures: match the service class name in snake_case
def student_service(db_path): ...
def rewards_service(db_path): ...

# Sample data: prefix with "sample_"
def sample_student(student_service): ...
def sample_subject(subject_service): ...

# Composite: describe the state
def enrolled_student(sample_student, sample_subject, enrollment_service): ...
```

---

## Coverage

### Targets

| Area | Minimum | Target |
|------|---------|--------|
| Service layer | 80% | 90%+ |
| API routes | 70% | 85%+ |
| Core utilities | 80% | 90%+ |
| GUI | -- | Not required |
| CLI menus | -- | Not required |

Focus testing effort on the service layer, where all business logic lives. GUI and CLI are thin presentation layers that delegate to services.

### What to Cover

For each service method, aim to test:

1. **Happy path** -- valid inputs produce correct output
2. **Validation** -- invalid inputs raise `ValidationError`
3. **Domain errors** -- business rule violations raise the module's error type
4. **Edge cases** -- empty results, boundary values, duplicate entries
5. **Filtering/search** -- query parameters return correct subsets

### Measuring Coverage

```bash
# Quick summary
python -m pytest education_system/secondary_school/tests/ \
    --cov=education_system.secondary_school.modules.domain \
    --cov-report=term-missing -q

# Identify untested files
python -m pytest education_system/secondary_school/tests/ \
    --cov=education_system.secondary_school \
    --cov-report=term:skip-covered -q
```

### Adding a New Fixture to `conftest.py`

When adding tests for a new module, add the service fixture to `conftest.py` if it will be reused across multiple test files:

```python
# In tests/conftest.py, add:

from education_system.secondary_school.modules.domain.pastoral_care.rewards.services.rewards_service import (
    RewardsService,
)

@pytest.fixture
def rewards_service(db_path):
    """Create a RewardsService with the test database."""
    return RewardsService(db_path)
```

If the fixture is only used in a single test file, define it locally in that file instead.
