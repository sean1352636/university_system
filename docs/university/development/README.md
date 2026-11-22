# Developer Documentation

Complete guide for developers contributing to the University Management System.

## Quick Links

- [Development Setup](#quick-setup) - Set up your development environment
- [Architecture Overview](#architecture) - System design and patterns
- [API Documentation](API.md) - REST API reference
- [Database Schema](../infrastructure/DATABASE.md) - Database structure
- [Migration Guide](MIGRATION_GUIDE.md) - Module restructuring reference (v5.41-v5.42)
- [Coding Standards](#coding-standards) - Style guide and conventions

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Git
- Make (optional but recommended)
- SQLite3
- Text editor or IDE (VS Code, PyCharm recommended)

### Quick Setup

```bash
# Clone repository
git clone <repository-url>
cd education-system

# Complete development setup
make install-dev

# This will install all dependencies and development tools
# (pytest, ruff, mypy) from requirements-dev.lock
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

### Module Restructuring (v5.41–v5.42)

In v5.41–v5.42, 49 single-file modules that had grown to 1,000–4,500 lines were decomposed into package directories. Each original `.py` file was replaced by a directory with focused submodules. Imports stayed backward-compatible at the time via `__init__.py` re-exports. See the [Migration Guide](MIGRATION_GUIDE.md) for that file mapping and the refactoring patterns used.

### Key Design Patterns

- **Centralized Authentication**: Shared auth for all seven systems (`src/education_system/platform/identity/auth/`)
- **Centralized Email**: Unified SMTP service for all notifications
- **Layered Architecture**: Clear separation of concerns
- **Repository Pattern**: Data access abstraction
- **Dependency Injection**: Testable, modular code
- **Package-Based Decomposition**: Large modules split into focused subpackages (mixin, tab/dialog, and functional patterns)

## 🔧 Development Tools

### Make Commands

```bash
# Installation
make install          # Install production dependencies
make install-dev      # Install dev dependencies

# Code Quality
make lint             # Run linter (ruff)
make lint-fix         # Auto-fix linting issues
make format           # Format code (ruff format)
make type-check       # Run MyPy type checking
make security-scan    # Run security scans
make check            # Run lint and tests

# Testing
make test             # Run the default fast, non-GUI suite
make test-all         # Run every test, including slow and GUI tests
make test-coverage    # Run tests with coverage
make test-university  # Run the university suite
make test-security    # Run security tests

# Running
make run              # Interactive menu
make run-gui          # GUI mode
make run-cli          # CLI mode

# Utilities
make clean            # Remove cache files
make help             # Show all commands
```

### Code Quality Tools

#### Ruff (Linter)
Fast Python linter configured in `pyproject.toml`:
```bash
make lint      # Check code
make lint-fix  # Auto-fix issues
```

#### Ruff (Formatter)
Code formatter (100-character lines):
```bash
make format        # Format code
```

#### MyPy (Type Checker)
Static type checking:
```bash
make type-check
```

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
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.email.smtp import send_email_via_smtp
```

## 🧪 Testing

### Writing Tests

```python
# tests/unit/systems/university/domains/<slice>/test_feature.py
import unittest
from education_system.systems.university.domains.<slice>.domain.feature import FeatureService

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

Tests are organised by scope, then by owner:

- **Unit Tests**: Test individual functions/methods (`tests/unit/systems/university/`)
- **Integration Tests**: Test module interactions (`tests/integration/systems/university/`)
- **Security Tests**: Test authentication, permissions (`tests/security/`)
- **GUI Tests**: Test interface components (marked `gui`, e.g. `tests/unit/systems/university/shell/gui/`)

### Running Tests

```bash
# All tests
make test

# With coverage
make test-coverage

# University suite
make test-university

# Specific category
pytest tests/unit/systems/university/domains/<slice>/ -v --timeout=60
make test-security
```

## 🗄️ Database Development

### Schema Changes

1. **Create Migration**
   ```python
   # src/education_system/migrations/versions/<revision>_add_new_table.py
   from alembic import op

   revision = "<revision>"
   down_revision = "<current head>"  # The chain must keep exactly one head


   def upgrade() -> None:
       op.execute("""
           CREATE TABLE new_table (
               id INTEGER PRIMARY KEY,
               name TEXT NOT NULL
           )
       """)


   def downgrade() -> None:
       op.execute("DROP TABLE new_table")
   ```

2. **Test Migration**
   ```bash
   # Run against a copy of the database; backups belong in var/backups/
   python -m alembic -c src/education_system/alembic.ini upgrade head
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

## Additional Resources

- [Module Documentation](../modules/README.md) - All system modules
- [API Documentation](API.md) - REST API reference
- [Migration Guide](MIGRATION_GUIDE.md) - Module restructuring reference
- [Testing Guide](TESTING_GUIDE.md) - Complete testing guide
- [Troubleshooting](../TROUBLESHOOTING.md) - Common issues
