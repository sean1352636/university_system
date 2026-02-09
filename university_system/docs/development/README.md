# Developer Documentation

Complete guide for developers contributing to the University Management System.

## 📋 Quick Links

- [Development Setup](SETUP.md) - Set up your development environment
- [Architecture Overview](ARCHITECTURE.md) - System design and patterns
- [API Documentation](API.md) - REST API reference
- [Database Schema](DATABASE.md) - Database structure
- [Contributing Guidelines](CONTRIBUTING.md) - How to contribute
- [Code Style Guide](CODE_STYLE.md) - Coding standards

## 🚀 Getting Started

### Prerequisites

- Python 3.8+ (3.9+ recommended)
- Git
- Make (optional but recommended)
- SQLite3
- Text editor or IDE (VS Code, PyCharm recommended)

### Quick Setup

```bash
# Clone repository
git clone <repository-url>
cd university_system

# Complete development setup
make setup

# This will:
# 1. Install all dependencies
# 2. Install development tools (pytest, black, ruff, mypy)
# 3. Set up pre-commit hooks
# 4. Create necessary directories
```

### Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/your-feature-name

# 2. Make changes and test
make test

# 3. Format and lint code
make format
make lint

# 4. Run all quality checks
make check

# 5. Commit changes
git add .
git commit -m "Add your feature"

# 6. Push and create pull request
git push origin feature/your-feature-name
```

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────┐
│         User Interfaces                 │
│  ┌─────────┬──────────┬──────────┐     │
│  │   GUI   │   CLI    │  Web API │     │
│  └────┬────┴────┬─────┴────┬─────┘     │
└───────┼─────────┼──────────┼───────────┘
        │         │          │
┌───────▼─────────▼──────────▼───────────┐
│        Domain Layer (Business Logic)    │
│  ┌─────────┬──────────┬──────────┐     │
│  │Academic │Financial │ Student  │     │
│  │Services │Services  │ Affairs  │     │
│  └────┬────┴────┬─────┴────┬─────┘     │
└───────┼─────────┼──────────┼───────────┘
        │         │          │
┌───────▼─────────▼──────────▼───────────┐
│     Infrastructure Layer                │
│  ┌─────────┬──────────┬──────────┐     │
│  │  Auth   │  Email   │ Database │     │
│  └────┬────┴────┬─────┴────┬─────┘     │
└───────┼─────────┼──────────┼───────────┘
        │         │          │
┌───────▼─────────▼──────────▼───────────┐
│          Data Layer                     │
│  SQLite Databases | File Storage        │
└─────────────────────────────────────────┘
```

### Key Design Patterns

- **Centralized Authentication**: Single UserAuth system across 92 files
- **Centralized Email**: Unified SMTP service for all notifications
- **Layered Architecture**: Clear separation of concerns
- **Repository Pattern**: Data access abstraction
- **Dependency Injection**: Testable, modular code

## 🔧 Development Tools

### Make Commands

```bash
# Installation
make install          # Install production dependencies
make install-dev      # Install dev dependencies
make setup            # Complete setup

# Code Quality
make lint             # Run linter (ruff)
make lint-fix         # Auto-fix linting issues
make format           # Format code (black, isort)
make format-check     # Check formatting
make type-check       # Run MyPy type checking
make security-check   # Run security scans
make check            # Run all quality checks

# Testing
make test             # Run all tests
make test-coverage    # Run tests with coverage
make test-fast        # Run tests in parallel
make test-unit        # Run unit tests only
make test-integration # Run integration tests
make test-security    # Run security tests

# Running
make run              # Interactive menu
make run-gui          # GUI mode
make run-cli          # CLI mode

# Database
make db-backup        # Backup database
make db-restore       # Restore database
make db-reset         # Reset database (WARNING)

# Utilities
make clean            # Remove cache files
make logs             # View logs
make info             # Show project info
make help             # Show all commands
```

### Code Quality Tools

#### Ruff (Linter)
Fast Python linter configured in `pyproject.toml`:
```bash
make lint      # Check code
make lint-fix  # Auto-fix issues
```

#### Black (Formatter)
Code formatter (100-character lines):
```bash
make format        # Format code
make format-check  # Check formatting
```

#### MyPy (Type Checker)
Static type checking:
```bash
make type-check
```

#### Pre-commit Hooks
Automatically run on `git commit`:
- Format with Black
- Lint with Ruff
- Check for secrets
- Validate YAML/JSON

## 📝 Coding Standards

### Python Style (PEP 8)

```python
# Good: Clear function names, type hints, docstrings
def calculate_student_gpa(student_id: str, semester: str) -> float:
    """
    Calculate GPA for a student in a specific semester.

    Args:
        student_id: Unique student identifier
        semester: Semester code (e.g., "2025-SPRING")

    Returns:
        Calculated GPA on 4.0 scale

    Raises:
        ValueError: If student_id not found
    """
    # Implementation
    pass

# Bad: No types, unclear names, no docstring
def calc(sid, sem):
    # Implementation
    pass
```

### Docstring Format (Google Style)

```python
def send_notification(user_email: str, subject: str, message: str) -> bool:
    """
    Send email notification to user.

    Args:
        user_email: Recipient email address
        subject: Email subject line
        message: Email body content

    Returns:
        True if email sent successfully, False otherwise

    Example:
        >>> send_notification("user@example.com", "Test", "Hello")
        True
    """
```

### Import Organization

```python
# Standard library imports
import os
import sys
from datetime import datetime

# Third-party imports
import pandas as pd
from flask import Flask

# Local imports
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.email import send_email_via_smtp
```

## 🧪 Testing

### Writing Tests

```python
# tests/test_feature.py
import unittest
from university_system.modules.domain.feature import FeatureService

class TestFeatureService(unittest.TestCase):
    """Test suite for FeatureService"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = FeatureService()

    def test_feature_creation(self):
        """Test creating a new feature"""
        result = self.service.create_feature("test")
        self.assertTrue(result)

    def test_feature_validation(self):
        """Test feature input validation"""
        with self.assertRaises(ValueError):
            self.service.create_feature("")

    def tearDown(self):
        """Clean up after tests"""
        self.service.cleanup()
```

### Test Organization

- **Unit Tests**: Test individual functions/methods
- **Integration Tests**: Test module interactions
- **Security Tests**: Test authentication, permissions
- **GUI Tests**: Test interface components

### Running Tests

```bash
# All tests
make test

# With coverage
make test-coverage

# Fast (parallel)
make test-fast

# Specific category
make test-unit
make test-integration
make test-security
```

## 🗄️ Database Development

### Schema Changes

1. **Create Migration**
   ```python
   # migrations/002_add_new_table.py
   def upgrade(conn):
       conn.execute("""
           CREATE TABLE new_table (
               id INTEGER PRIMARY KEY,
               name TEXT NOT NULL
           )
       """)
   ```

2. **Test Migration**
   ```bash
   make db-backup  # Backup first!
   python migrations/run_migrations.py
   ```

3. **Update Models**
   ```python
   # Update corresponding models
   ```

### Database Best Practices

- Always backup before schema changes
- Use parameterized queries
- Add indexes for frequently queried columns
- Document schema changes
- Test migrations thoroughly

## 📚 Documentation

### Documentation Standards

- Update documentation with code changes
- Include code examples
- Add screenshots for GUI features
- Keep documentation up-to-date
- Use clear, concise language

### Writing Documentation

```markdown
# Feature Name

## Overview
Brief description of the feature.

## Usage
How to use the feature with examples.

## API Reference
Technical details and parameters.

## Examples
Real-world usage examples.
```

## 🔄 Git Workflow

### Branch Naming

- `feature/` - New features
- `bugfix/` - Bug fixes
- `hotfix/` - Critical fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring

### Commit Messages

```
<type>: <subject>

<body>

<footer>
```

**Types**: feat, fix, docs, style, refactor, test, chore

**Example**:
```
feat: Add student GPA calculation

- Implement GPA calculation for 4.0 scale
- Add semester filtering
- Include grade validation

Closes #123
```

## 🚀 Deployment

See [Deployment Guide](../deployment/DEPLOYMENT.md) for production deployment instructions.

## 📖 Additional Resources

- [Module Documentation](../modules/README.md) - All system modules
- [API Documentation](API.md) - REST API reference
- [Testing Guide](../testing/TESTING_GUIDE.md) - Complete testing guide
- [Troubleshooting](../troubleshooting/COMMON_ISSUES.md) - Common issues

---

**For Questions**: Check [FAQ](../troubleshooting/FAQ.md) or open an issue
**For Contributions**: See [Contributing Guide](CONTRIBUTING.md)
