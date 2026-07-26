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

Configuration is in `pyproject.toml` under `[tool.pytest.ini_options]`.


## Running Tests

### Full Suite

```bash
# Via the unified launcher
python run.py --college --test

# Or directly with pytest
python -m pytest education_system/college_system/tests/ -v --tb=short
```

### Single Test File

```bash
python -m pytest education_system/college_system/tests/test_student_service.py -v
```

### Single Test Class or Method

```bash
# Run one class
python -m pytest education_system/college_system/tests/test_student_service.py::TestStudentService -v

# Run one test method
python -m pytest education_system/college_system/tests/test_student_service.py::TestStudentService::test_create_student -v
```

### With Coverage

```bash
python -m pytest education_system/college_system/tests/ \
  --cov=education_system.college_system \
  --cov-report=html \
  --cov-report=term-missing
```

Coverage configuration is in `pyproject.toml` under `[tool.coverage.*]`. Branch coverage is enabled. The HTML report is written to `htmlcov/`.

### Parallel Execution

```bash
python -m pytest education_system/college_system/tests/ -n auto
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

Available markers: `slow`, `integration`, `unit`, `gui`, `security`, `performance`.


## Test Organisation

All tests live in `education_system/college_system/tests/`:

```
tests/
    conftest.py                         # Shared fixtures
    __init__.py
    test_api.py                         # REST API integration tests
    test_auth.py                        # Authentication tests
    test_student_service.py             # StudentService unit tests
    test_course_service.py              # CourseService unit tests
    test_enrollment_service.py
    test_grade_service.py
    test_attendance_service.py
    test_department_service.py
    test_finance_service.py
    test_funding_service.py
    test_cpd_service.py
    test_observations_service.py
    test_markbook_service.py
    test_emergency_service.py
    test_surveys_service.py
    ... (77 test files total)
```

Each test file typically contains a single test class (`TestXxxService` or `TestXxxAPI`) with multiple `test_*` methods.


## Fixtures (conftest.py)

The shared `conftest.py` provides fixtures that all tests can use. Understanding these fixtures is essential for writing new tests.

### Database Fixtures

#### `db_path`

Creates a **temporary SQLite database** for each test using `tmp_path`. The database is initialised with `init_db()` and `seed_default_data()` so that schema tables and default records (admin user, demo student) exist. After the test, the path override is cleared.

```python
@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test_sixthform.db")
    set_db_path(path)
    init_db(path)
    seed_default_data(path)
    yield path
    set_db_path(None)
```

Every service fixture and the API client fixture depend on `db_path`, so each test gets a completely isolated database.

### Service Fixtures

Service fixtures create an instance of the service class pointed at the test database. The pattern is consistent:

```python
@pytest.fixture
def student_service(db_path):
    return StudentService(db_path)

@pytest.fixture
def course_service(db_path):
    return CourseService(db_path)

@pytest.fixture
def enrollment_service(db_path):
    return EnrollmentService(db_path)
```

There are service fixtures for all major modules: `grade_service`, `attendance_service`, `timetable_service`, `assignment_service`, `notification_service`, `mfa_service`, `department_service`, `finance_service`, `funding_service`, `destination_service`, `student_support_service`, `room_service`, `cpd_service`, `observations_service`, `appraisals_service`, `resource_booking_service`, `markbook_service`, `staff_wellbeing_service`, `lesson_plans_service`, `data_dashboard_service`, `absence_requests_service`, `intervention_tracking_service`, `visitors_service`, `policies_service`, `gdpr_service`, `quality_assurance_service`, `bulk_operations_service`, `emergency_service`, `academic_year_service`, `kpi_dashboard_service`, `audit_reports_service`, `user_management_service`, `portfolio_service`, `study_planner_service`, `enrichment_service`, `peer_mentoring_service`, `surveys_service`, `skills_passport_service`, `progress_dashboard_service`, `meal_ordering_service`, `print_credits_service`, `work_journal_service`, `announcements_service`, `document_hub_service`, `advanced_search_service`, `feedback_service`, `accessibility_service`, `mobile_dashboard_service`, `attachments_service`, `activity_feed_service`, `sms_email_service`, `multi_language_service`.

### Sample Data Fixtures

These fixtures create records that tests can reference:

```python
@pytest.fixture
def sample_student(student_service):
    return student_service.create_student(
        first_name="John", last_name="Doe",
        email="john.doe@sixthform.ac.uk",
        year_group="12", form_group="12A",
    )

@pytest.fixture
def sample_course(course_service):
    return course_service.create_course(
        course_code="TEST101", title="Intro to Computer Science",
        guided_learning_hours=3, capacity=30, subject_area="Computer Science",
    )
```

### API Test Fixtures

For testing the REST API:

```python
@pytest.fixture
def api_client(db_path):
    """Create a Flask test client."""
    app = create_app(db_path)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def api_token(api_client):
    """Get a JWT token by logging in as admin."""
    response = api_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "Admin@123",
    })
    return response.get_json()["token"]

@pytest.fixture
def auth_headers(api_token):
    """Authorization headers with JWT token."""
    return {"Authorization": f"Bearer {api_token}"}
```


## Writing New Tests

### Service-Level Tests

Service tests validate business logic directly, without going through the API layer.

```python
"""Tests for FooService."""

import pytest
from education_system.college_system.core.exceptions import FooError, ValidationError


class TestFooService:
    def test_create_foo(self, foo_service):
        result = foo_service.create_foo(name="Test Foo")
        assert result["name"] == "Test Foo"
        assert result["id"] is not None

    def test_create_foo_missing_name(self, foo_service):
        with pytest.raises(ValidationError):
            foo_service.create_foo(name="")

    def test_get_foo_not_found(self, foo_service):
        assert foo_service.get_foo(9999) is None

    def test_list_foos(self, foo_service):
        foo_service.create_foo(name="A")
        foo_service.create_foo(name="B")
        results = foo_service.list_foos()
        assert len(results) >= 2

    def test_update_foo(self, foo_service):
        created = foo_service.create_foo(name="Original")
        updated = foo_service.update_foo(created["id"], name="Updated")
        assert updated["name"] == "Updated"

    def test_delete_foo(self, foo_service):
        created = foo_service.create_foo(name="ToDelete")
        foo_service.delete_foo(created["id"])
        assert foo_service.get_foo(created["id"]) is None
```

### API-Level Tests

API tests exercise the full request/response cycle through Flask's test client.

```python
class TestFooAPI:
    def test_create_foo(self, api_client, auth_headers):
        resp = api_client.post("/api/foo", headers=auth_headers, json={
            "name": "Test Foo",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["data"]["name"] == "Test Foo"

    def test_list_foos(self, api_client, auth_headers):
        api_client.post("/api/foo", headers=auth_headers, json={"name": "A"})
        resp = api_client.get("/api/foo", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["total"] >= 1

    def test_unauthorized(self, api_client):
        resp = api_client.get("/api/foo")
        assert resp.status_code == 401
```

### Key Conventions

1. **One test class per service or API resource.** Name it `TestXxxService` or `TestXxxAPI`.
2. **Test method names** start with `test_` and describe the scenario: `test_create_student`, `test_create_student_validates_name`, `test_get_student_not_found`.
3. **Use fixtures** rather than creating data manually in each test. Add new fixtures to `conftest.py` if they will be reused.
4. **Assert specific values**, not just truthiness. For example, check `student["student_id"] == "SFC0002"` rather than `assert student["student_id"]`.
5. **Test error paths** using `pytest.raises` for expected exceptions.
6. **Each test is independent.** The `db_path` fixture gives every test a fresh database.


## Mocking Patterns

Use `pytest-mock` (provides the `mocker` fixture) when you need to isolate a unit from its dependencies.

### Mocking a Service Method

```python
def test_route_handles_service_error(api_client, auth_headers, mocker):
    mocker.patch(
        "education_system.college_system.modules.domain.students.services.student_service.StudentService.get_student",
        side_effect=StudentError("Database unavailable"),
    )
    resp = api_client.get("/api/students/1", headers=auth_headers)
    assert resp.status_code == 400
```

### Mocking Database Connections

If you need to test behaviour when the database is unavailable:

```python
def test_handles_db_failure(student_service, mocker):
    mocker.patch(
        "education_system.college_system.infrastructure.database.db.connect",
        side_effect=DatabaseError("Connection failed"),
    )
    with pytest.raises(DatabaseError):
        student_service.list_students()
```

### General Guidelines for Mocking

- Prefer testing against the real (temporary) database when possible. Mocking should be reserved for external services, error conditions, or situations where using the real dependency is impractical.
- Patch at the point of use, not at the point of definition.
- Keep mocked return values realistic -- use the same dict structure the real code returns.


## Coverage

Coverage settings in `pyproject.toml`:

- **Source**: `education_system`
- **Omitted**: test files, `__pycache__`, virtual environments
- **Branch coverage**: enabled
- **Report**: shows missing lines, does not skip covered files

Generate an HTML coverage report:

```bash
python -m pytest education_system/college_system/tests/ \
  --cov=education_system.college_system \
  --cov-report=html
open htmlcov/index.html
```
