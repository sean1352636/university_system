# Testing Guide

Comprehensive guide to testing the University Management System.

## 📊 Test Suite Overview

University tests are organised by scope, then by owner:

- **Unit**: `tests/unit/systems/university/` (`application/`, `domains/`, `infrastructure/`, `services/`, `shell/`)
- **Integration**: `tests/integration/systems/university/`
- **Contract**: `tests/contract/university/`
- **End to end**: `tests/end_to_end/university/`
- **Smoke**: `tests/smoke/university/`
- **Security**: `tests/security/`
- **Performance**: `tests/performance/benchmarks/`

## 🚀 Quick Start

### Running Tests

```bash
# Run all tests
make test

# Run with coverage report
make test-coverage

# Run the university suite
make test-university

# Run specific test category
make test-security
make test-gui
```

### Using Python Directly

```bash
# All tests with pytest
python -m pytest tests/

# Specific test file
python -m pytest tests/unit/platform/identity/auth/test_auth_core.py -v --timeout=60

# University unit tests
python -m pytest tests/unit/systems/university/ -m "not slow and not gui" --timeout=60
```

## 📁 Test Organization

### Directory Structure

```
tests/
├── conftest.py
├── fixtures/                     # Shared fixtures, including university DB isolation
├── unit/
│   ├── platform/                 # Includes identity/auth/
│   └── systems/university/
│       ├── _support/             # Includes run_all_tests.py
│       ├── application/
│       ├── domains/              # One folder per slice; see the note below
│       ├── infrastructure/
│       ├── services/
│       └── shell/
├── integration/systems/university/
├── contract/university/
├── end_to_end/university/
├── smoke/university/
├── security/
└── performance/benchmarks/
```

`tests/unit/systems/university/domains/` still has `academics/` and `pastoral/` folders from before those slices were split, alongside folders for the current slices.

## 🧪 Test Types

### Unit Tests

Test individual functions and methods in isolation.

```python
# Example: a test under tests/unit/platform/identity/auth/
import unittest
from education_system.platform.identity.auth.password_manager import hash_password, verify_password

class TestPasswordHashing(unittest.TestCase):
    def test_password_hashing(self):
        """Test that passwords are properly hashed"""
        password = "SecurePass123!"
        hashed = hash_password(password)
        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))

    def test_wrong_password(self):
        """Test that a wrong password does not verify"""
        hashed = hash_password("SecurePass123!")
        self.assertFalse(verify_password("wrong_password", hashed))
```

**Run unit tests only**:
```bash
python -m pytest -m unit tests/unit/systems/university/
```

### Integration Tests

Test how modules work together.

```python
# Example: a test under tests/integration/systems/university/
import unittest
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.email.smtp import send_email_via_smtp

class TestEmailIntegration(unittest.TestCase):
    def test_registration_email(self):
        """Test that user registration sends confirmation email"""
        auth = UserAuth()

        # Create user
        user = auth.create_user("newuser", "password123", "user@example.com")

        # Verify email was queued
        # (In database_only_mode, emails are saved to database)
        self.assertIsNotNone(user)
```

**Run integration tests only**:
```bash
python -m pytest -m integration tests/integration/systems/university/
```

### Security Tests

Test security features and protections.

```python
# Example: a test under tests/security/injection/
import unittest
from education_system.systems.university.infrastructure.validation.sanitizers import sanitize_input

class TestInputSanitization(unittest.TestCase):
    def test_sql_injection_prevention(self):
        """Test SQL injection attempts are sanitized"""
        malicious = "'; DROP TABLE students; --"
        sanitized = sanitize_input(malicious)
        self.assertNotIn("DROP TABLE", sanitized)

    def test_xss_prevention(self):
        """Test XSS attempts are sanitized"""
        malicious = "<script>alert('XSS')</script>"
        sanitized = sanitize_input(malicious)
        self.assertNotIn("<script>", sanitized)
```

**Run security tests only**:
```bash
python -m pytest -m security tests/security/
```

### GUI Tests

Test graphical interface components.

```python
# Example: a test under tests/unit/systems/university/shell/gui/main/
import unittest
from unittest.mock import Mock
from education_system.systems.university.shell.gui.main.main_gui import UnifiedManagementGUI

class TestGUIInitialization(unittest.TestCase):
    def test_main_window_creation(self):
        """Test main window initializes correctly"""
        gui = UnifiedManagementGUI(Mock())
        self.assertIsNotNone(gui)
```

**Run GUI tests only**:
```bash
python -m pytest -m gui tests/unit/systems/university/shell/ -n 0
```

## 📈 Test Coverage

### Generating Coverage Reports

```bash
# Generate HTML coverage report
make test-coverage

# View report in browser
open htmlcov/index.html
```

### Coverage Configuration

Coverage settings in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src/education_system"]
omit = ["tests/*", "*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
precision = 2
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
]
```

### Coverage Goals

- **Overall Coverage**: Aim for 80%+
- **Critical Modules**: 90%+ (auth, email, database)
- **Business Logic**: 85%+ (academic, financial services)
- **GUI**: 70%+ (harder to test, focus on logic)

## ✍️ Writing Tests

### Test File Structure

```python
#!/usr/bin/env python3
"""
Test module for [feature name].

Tests cover:
- Feature functionality
- Edge cases
- Error handling
- Integration with other modules
"""

import unittest
from education_system.systems.university.domains.<slice>.domain.feature import Feature

class TestFeature(unittest.TestCase):
    """Test suite for Feature"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for entire class"""
        cls.shared_resource = SomeResource()

    def setUp(self):
        """Set up before each test"""
        self.feature = Feature()

    def test_basic_functionality(self):
        """Test basic feature operation"""
        result = self.feature.do_something()
        self.assertTrue(result)

    def test_edge_case(self):
        """Test edge case handling"""
        result = self.feature.handle_edge_case([])
        self.assertEqual(result, expected_value)

    def test_error_handling(self):
        """Test error conditions"""
        with self.assertRaises(ValueError):
            self.feature.invalid_operation()

    def tearDown(self):
        """Clean up after each test"""
        self.feature.cleanup()

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        cls.shared_resource.cleanup()

if __name__ == '__main__':
    unittest.main()
```

### Test Best Practices

1. **Descriptive Names**: Use clear test function names
   ```python
   # Good
   def test_user_login_with_invalid_password_fails(self):

   # Bad
   def test_login(self):
   ```

2. **One Assertion Per Test**: Focus each test on one thing
   ```python
   # Good
   def test_password_length_validation(self):
       self.assertFalse(validate_password("short"))

   def test_password_complexity_validation(self):
       self.assertFalse(validate_password("noupppercase"))

   # Bad
   def test_password_validation(self):
       self.assertFalse(validate_password("short"))
       self.assertFalse(validate_password("noupppercase"))
       self.assertFalse(validate_password("nonumbers"))
   ```

3. **Test Isolation**: Tests should not depend on each other
   ```python
   # Good: Each test creates its own data
   def setUp(self):
       self.student = create_test_student()

   # Bad: Tests share state
   class_student = None
   def test_a(self):
       self.class_student = create_test_student()
   def test_b(self):
       # Depends on test_a running first!
       self.class_student.enroll()
   ```

4. **Clean Up**: Always clean up test data
   ```python
   def tearDown(self):
       """Remove test data"""
       delete_test_student(self.student.id)
       close_test_database()
   ```

5. **Use Test Fixtures**: Reuse common setup
   ```python
   @classmethod
   def setUpClass(cls):
       """One-time setup for all tests"""
       cls.test_db = create_test_database()
       cls.auth = UserAuth(cls.test_db)
   ```

## 🏃 Continuous Integration

### Local CI Simulation

```bash
# Run the full CI pipeline locally
make ci

# This runs:
# 1. clean - Remove cache files
# 2. lint - Check code style
# 3. test-cov - Run tests with coverage
# 4. security-scan - Run bandit
# 5. supply-chain-check - Check locks and dependencies
```

### Pre-commit Checks

Before committing code:

```bash
# Format code
make format

# Run lint and tests
make check
```

## 🐛 Debugging Failed Tests

### Running Individual Tests

```bash
# Run specific test file
python -m pytest tests/unit/platform/identity/auth/test_auth_core.py -v

# Run specific test function
python -m pytest tests/unit/platform/identity/auth/test_auth_core.py::TestClassName::test_name -v

# Show print statements (useful for debugging)
python -m pytest tests/unit/platform/identity/auth/test_auth_core.py -s

# Drop into debugger on failure
python -m pytest tests/unit/platform/identity/auth/test_auth_core.py --pdb
```

### Common Test Failures

1. **Database Locks**
   - Ensure tests clean up database connections
   - Use unique test databases
   - Add `tearDown()` methods

2. **Import Errors**
   - Check the project is installed (`make install-dev`) or `src/` is on `PYTHONPATH`
   - Ensure `__init__.py` files exist
   - Verify package structure

3. **File Not Found**
   - Use absolute paths or path resolution
   - Check working directory
   - Ensure test data files exist

4. **Timing Issues**
   - Add appropriate wait times for async operations
   - Don't rely on system time
   - Use mock time when possible

## 📊 Test Metrics

### Current Coverage (as of v5.0.0)

| Module Category | Coverage | Test Files |
|----------------|----------|------------|
| Authentication | 92% | 5 files |
| Email System | 88% | 2 files |
| Database | 85% | 6 files |
| Academic | 82% | 8 files |
| Financial | 80% | 5 files |
| Student Union | 78% | 3 files |
| GUI | 65% | 9 files |
| **Overall** | **80%** | **103 files** |

## 📚 Related Documentation

- [Contributing Guide](../../../CONTRIBUTING.md) - Contribution guidelines

---

**Coverage Goal**: 80%+ overall, 90%+ critical modules
**Test Runner**: pytest with unittest framework
