# Testing Guide

Comprehensive guide to testing the University Management System.

## 📊 Test Suite Overview

The system includes **103 comprehensive test files** covering all major components:

- **Core Functionality**: 11 tests (authentication, enrollment, courses)
- **Database**: 6 tests (integrity, consistency, backup/restore)
- **Security**: 5 tests (password hashing, encryption, input sanitization)
- **Services**: 5 tests (authentication, authorization, payment)
- **Domain**: 5 tests (entities, aggregates, policies)
- **Infrastructure**: 10 tests (cache, config, logging, migrations)
- **API**: 5 tests (endpoints, rate limiting, headers)
- **CLI**: 5 tests (workflows, error rendering, help)
- **GUI**: 9 tests (initialization, accessibility, screens)
- **Feature Modules**: 19 tests (academic, finance, health, union)
- **Analytics**: 4 tests (datasets, models, engineering)
- **Integration**: 5 tests (email, storage, event bus)
- **Email**: 2 tests (service, validation)
- **Reporting**: 3 tests (generation, charts, PDF)
- **Jobs**: 1 test (schedulers)
- **Utilities**: 8 tests (logging, performance, search)

## 🚀 Quick Start

### Running Tests

```bash
# Run all tests
make test

# Run with coverage report
make test-coverage

# Run tests in parallel (faster)
make test-fast

# Run specific test category
make test-unit
make test-integration
make test-security
```

### Using Python Directly

```bash
# All tests with pytest
python -m pytest university_system/tests/

# Specific test file
python university_system/tests/test_authentication.py

# Test suite runner
python university_system/tests/run_all_tests.py
```

## 📁 Test Organization

### Directory Structure

```
university_system/tests/
├── run_all_tests.py           # Master test runner
├── README.md                  # Test documentation
│
├── Core Functionality Tests
├── test_authentication.py
├── test_student_enrollment.py
├── test_course_management.py
├── test_modules.py
├── test_instructors.py
│
├── Database Tests
├── test_database.py
├── test_database_integrity.py
├── test_data_consistency.py
├── test_backup_restore.py
│
├── Security Tests
├── test_security_password_hashing.py
├── test_security_encryption_fernet.py
├── test_security_input_sanitization.py
│
├── GUI Tests
├── test_gui_initialization.py
├── test_gui_login_flow.py
├── test_widget_safety.py
│
└── [90+ more test files...]
```

## 🧪 Test Types

### Unit Tests

Test individual functions and methods in isolation.

```python
# Example: test_authentication.py
import unittest
from university_system.infrastructure.auth import UserAuth

class TestAuthentication(unittest.TestCase):
    def setUp(self):
        self.auth = UserAuth()

    def test_password_hashing(self):
        """Test that passwords are properly hashed"""
        password = "SecurePass123!"
        hashed = self.auth.hash_password(password)
        self.assertNotEqual(password, hashed)
        self.assertTrue(self.auth.verify_password(password, hashed))

    def test_invalid_login(self):
        """Test failed login with wrong password"""
        result = self.auth.login("user", "wrong_password")
        self.assertFalse(result)
```

**Run unit tests only**:
```bash
python -m pytest -m unit university_system/tests/
```

### Integration Tests

Test how modules work together.

```python
# Example: test_integration.py
import unittest
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.email import send_email_via_smtp

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
python -m pytest -m integration university_system/tests/
```

### Security Tests

Test security features and protections.

```python
# Example: test_security_input_sanitization.py
import unittest
from university_system.utils.security import sanitize_input

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
python -m pytest -m security university_system/tests/
```

### GUI Tests

Test graphical interface components.

```python
# Example: test_gui_initialization.py
import unittest
from tkinter import Tk
from university_system.modules.interfaces.gui.main_gui import MainGUI

class TestGUIInitialization(unittest.TestCase):
    def setUp(self):
        self.root = Tk()

    def test_main_window_creation(self):
        """Test main window initializes correctly"""
        gui = MainGUI(self.root)
        self.assertIsNotNone(gui)
        self.assertEqual(gui.root.title(), "University Management System")

    def tearDown(self):
        self.root.destroy()
```

**Run GUI tests only**:
```bash
python -m pytest -m gui university_system/tests/
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
source = ["university_system"]
omit = ["*/tests/*", "*/__pycache__/*"]
branch = true

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
from university_system.modules.feature import Feature

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
# 2. install-dev - Install dependencies
# 3. lint - Check code style
# 4. type-check - Check types
# 5. test-coverage - Run tests with coverage
```

### Pre-commit Checks

Before committing code:

```bash
# Run all quality checks
make pre-commit

# This runs:
# 1. format - Format code
# 2. lint - Check style
# 3. test - Run tests
```

## 🐛 Debugging Failed Tests

### Running Individual Tests

```bash
# Run specific test file
python -m pytest university_system/tests/test_authentication.py -v

# Run specific test function
python -m pytest university_system/tests/test_authentication.py::TestAuth::test_login -v

# Show print statements (useful for debugging)
python -m pytest university_system/tests/test_authentication.py -s

# Drop into debugger on failure
python -m pytest university_system/tests/test_authentication.py --pdb
```

### Common Test Failures

1. **Database Locks**
   - Ensure tests clean up database connections
   - Use unique test databases
   - Add `tearDown()` methods

2. **Import Errors**
   - Check PYTHONPATH is set correctly
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

- [Contributing Guide](../../../../CONTRIBUTING.md) - Contribution guidelines

---

**Test Suite**: 103 test files
**Coverage Goal**: 80%+ overall, 90%+ critical modules
**Test Runner**: pytest with unittest framework
