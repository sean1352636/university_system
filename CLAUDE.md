# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive, enterprise-grade **University Management System** built with Python. It integrates academic, financial, student affairs, health services, and administrative operations into a unified platform with CLI, GUI (Tkinter), and Web (Flask) interfaces.

**Version**: 5.0.0
**Python**: 3.8+
**Database**: SQLite (default), PostgreSQL/MySQL supported
**Architecture**: 4-layer domain-driven design

## Commands

### Running the Application

```bash
# Interactive menu (choose CLI/GUI/Tests)
python run.py

# Direct CLI mode
python run.py --cli

# Direct GUI mode
python run.py --gui

# Run all tests
python run.py --test
```

### Testing

```bash
# Run all tests
make test
python -m pytest university_system/tests/ -v

# Run specific test file
python -m pytest university_system/tests/test_authentication.py -v

# Run with coverage
make test-coverage
python -m pytest university_system/tests/ --cov=university_system --cov-report=html

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run security tests
make test-security

# Run tests in parallel
make test-fast
```

### Code Quality

```bash
# Lint code
make lint
ruff check university_system/

# Auto-fix linting issues
make lint-fix

# Format code (Black + isort)
make format

# Type checking
make type-check
mypy university_system/

# Security checks
make security-check

# Run all quality checks
make check
```

### Database Operations

```bash
# Create backup
make db-backup

# Restore from backup
make db-restore BACKUP_FILE=path/to/backup.db

# Reset database (WARNING: deletes all data)
make db-reset
```

### Email Scheduler

```bash
# Start email scheduler (background)
python -m university_system.utils.email_scheduler_control start

# Check scheduler status
python -m university_system.utils.email_scheduler_control status

# Stop scheduler
python -m university_system.utils.email_scheduler_control stop

# Run in foreground (testing/debugging)
python -m university_system.utils.email_scheduler_control run

# Or run directly
python -m university_system.infrastructure.email.email_scheduler
```

**Scheduled Tasks:**
- Satisfaction surveys: Daily at 09:00
- Book return reminders: Daily at 08:00
- Overdue book notices: Daily at 10:00
- SLA breach alerts: Every 30 minutes

See `docs/EMAIL_SCHEDULER.md` for detailed documentation.

### Development

```bash
# Install dependencies
make install

# Install dev dependencies
make install-dev

# Complete dev setup
make setup

# Clean build artifacts
make clean

# View logs
make logs

# Profile application
make profile
```

## Architecture

### 4-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│  Interface Layer (CLI, GUI, Web)                │
├─────────────────────────────────────────────────┤
│  Domain/Service Layer (Business Logic)          │
├─────────────────────────────────────────────────┤
│  Infrastructure Layer (Auth, DB, Email, AI)     │
├─────────────────────────────────────────────────┤
│  Data Layer (SQLite with Connection Pool)       │
└─────────────────────────────────────────────────┘
```

### Directory Structure

```
university_system/
├── infrastructure/           # Core infrastructure
│   ├── auth/                # Authentication & authorization
│   ├── database/            # Database layer with connection pooling
│   ├── email/               # Email service with async queue
│   ├── ai/                  # AI/chatbot integration
│   └── security/            # Security features (encryption, audit)
│
├── modules/
│   ├── domain/              # Domain layer (business logic)
│   │   ├── academics/       # Academic domain
│   │   │   └── gui/        # Academic GUIs (assignment_system, grade_tracking, etc.)
│   │   ├── commerce/        # Dining/commerce services
│   │   │   └── gui/        # Commerce GUIs (restaurant, shop management)
│   │   ├── finance/         # Financial services
│   │   │   ├── gui/        # Finance GUIs (finance management, reporting, financial aid)
│   │   │   │   ├── finance/          # 13 modular finance manager files
│   │   │   │   └── financial_aid/    # Financial aid & scholarships GUI
│   │   │   └── services/   # Finance service layer (financial_aid, budgeting, etc.)
│   │   ├── health/          # Health services
│   │   │   └── gui/        # Health GUIs (health portal, telemedicine)
│   │   ├── housing/         # Housing management
│   │   │   └── gui/        # Housing GUIs (accommodation management)
│   │   └── student_affairs/ # Student life (union, mentorship, etc.)
│   │       └── gui/        # Student affairs GUIs (union, alumni, helpdesk)
│   │
│   ├── web/                # Web interface (Flask) - NO GUIs HERE
│   ├── services/           # Application services
│   └── shared/             # Shared utilities
│       ├── constants/      # Centralized paths & constants
│       ├── gui/            # Shared GUI components (main_gui.py)
│       └── utils/          # Activity logging, config, validation
│
├── tests/                  # Comprehensive test suite
├── data/                   # Runtime data (DB, reports, uploads)
├── docs/                   # Documentation
└── utils/                  # Additional utilities
```

### Key Architectural Components

#### 1. Database Layer (`infrastructure/database/`)
- **Single unified database**: `data/db_files/student_records.db`
- **Thread-safe connection pooling**: 2-10 connections (configurable)
- **Write-Ahead Logging (WAL)** for better concurrency
- **Context managers** for transaction safety
- **Migration support** for schema versioning

```python
# Always use context managers for database operations
from university_system.infrastructure.database.db import get_connection, transaction

# Read-only queries
with get_connection() as conn:
    result = conn.execute("SELECT * FROM students").fetchall()

# Transactions (auto-commit/rollback)
with transaction() as conn:
    conn.execute("INSERT INTO students ...")
```

#### 2. Authentication & Authorization (`infrastructure/auth/`)
- **PBKDF2 password hashing**: 1,000,000 iterations (OWASP recommended)
- **Multi-Factor Authentication**: TOTP, Email OTP, SMS OTP
- **Role-based permissions**: Admin, Instructor, Student, Staff
- **Global auth context**: Shared via `shared_context.py`
- **Session management**: Token-based with concurrency limits

```python
# Access global auth instance
from university_system.infrastructure.shared_context import get_auth

auth = get_auth()
if auth.is_logged_in():
    user = auth.get_current_user()

# Permission checking
from university_system.infrastructure.auth.authorization import require_permission

@require_permission('view_students')
def view_student_records():
    pass
```

#### 3. Email Infrastructure (`infrastructure/email/`)
- **Asynchronous email queue** with worker threads
- **Template rendering** with variable substitution
- **SMTP integration** with configurable providers
- **Scheduled emails** via `schedule` library
- **Database logging** of all sent emails

#### 4. Centralized Paths (`modules/shared/constants/paths.py`)
- **Single source of truth** for all file paths
- **Automatic directory creation** on import
- **Cross-platform compatibility**

```python
# Always use centralized paths
from university_system.modules.shared.constants import paths

db_path = paths.DEFAULT_DB_PATH
upload_dir = paths.UPLOAD_DIR
```

#### 5. Activity Logging (`modules/shared/utils/activity_logger.py`)
- **Comprehensive audit trail** for compliance
- **User attribution** for all actions
- **Timestamp tracking** for all events

```python
from university_system.modules.shared.utils.activity_logger import log_activity

log_activity('create', 'student', student_id='12345', details={'name': 'John Doe'})
log_activity('update', 'grade', grade_id='456', changes={'old': 'B', 'new': 'A'})
```

### Important Conventions

#### Import Structure
```python
# ✓ CORRECT: Use explicit imports
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.constants import paths

# ✗ INCORRECT: Avoid wildcard imports
from university_system.infrastructure.database.db import *
```

#### Database Access Pattern
```python
# ✓ CORRECT: Always use context managers
with transaction() as conn:
    conn.execute("INSERT INTO students VALUES (?, ?)", (id, name))

# ✗ INCORRECT: Don't manage connections manually
conn = get_connection()
conn.execute("INSERT...")
conn.commit()  # Missing error handling
```

#### Permission Checking
```python
# ✓ CORRECT: Use decorators or inline checks
@require_permission('edit_grades')
def edit_student_grade(student_id, grade):
    pass

# Alternative: Inline check
auth = get_auth()
if not auth.has_permission('edit_grades'):
    raise PermissionError("Access denied")
```

#### Activity Logging (Required for Compliance)
```python
# ✓ CORRECT: Log all data modifications
log_activity('delete', 'course', course_id=course_id)

# ✓ CORRECT: Log user actions
log_activity('view', 'student_records', user_id=current_user.id)
```

### Recent Refactoring (October 2025)

The codebase underwent major modularization:
- **Student Union**: Split from 16,535 lines → 18 specialized files
- **Assignment System**: Refactored from 14,393 lines → 19 manager-based files
- **Grade Tracking**: Reorganized from 13,114 lines → 24 modular files
- **Finance Module**: Split from 11,641 lines → 13 manager files

**Result**: 91% reduction in max file size, average ~750 lines per file

**Manager Pattern** is used throughout:
```python
# Example: Assignment system uses managers
assignment_system/
├── assignment_manager.py     # Assignment CRUD
├── grading_manager.py        # Grading operations
├── group_manager.py          # Group management
└── analytics_manager.py      # Analytics & reporting
```

## Configuration

### Environment Variables
Create a `.env` file (copy from `.env.example` if available):
```bash
# Core Settings
DEFAULT_ADMIN_PASSWORD=admin123
DEFAULT_STAFF_PASSWORD=staff123
DEFAULT_STUDENT_PASSWORD=student123

# Database (optional - defaults to SQLite)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=university_system

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_password

# Application Settings
APP_ENV=development
DEBUG=True
LOG_LEVEL=INFO
```

### Database Location
- Default: `data/db_files/student_records.db`
- Configured via `paths.DEFAULT_DB_PATH`

### Logging Configuration
- Logs location: `logs/` directory
- Rotating file handlers with size limits
- Configured in `utils/logging/log_config.py`

## Security

### Password Security
- **PBKDF2-SHA256 hashing** with unique salts (1M iterations)
- Never store plaintext passwords
- Automatic salt generation per user

### SQL Injection Prevention
- **Always use parameterized queries**
```python
# ✓ CORRECT
conn.execute("SELECT * FROM students WHERE id = ?", (student_id,))

# ✗ INCORRECT - SQL injection risk
conn.execute(f"SELECT * FROM students WHERE id = {student_id}")
```

### Transaction Safety
- Use `transaction()` context manager for ACID compliance
- Automatic rollback on exceptions
- No manual commit/rollback needed

### Access Control
- Role-based permissions enforced at service layer
- Use `@require_permission()` decorator
- Check permissions before sensitive operations

### Audit Logging
- **Required for all data modifications**
- Use `log_activity()` for compliance
- Tracks user, action, timestamp, and details

## Testing Guidelines

### Test Structure
```
tests/
├── test_authentication.py       # Auth system tests
├── test_database_integrity.py   # DB constraint tests
├── test_student_enrollment.py   # Enrollment workflow tests
├── test_performance.py          # Query performance tests
└── run_all_tests.py            # Test runner
```

### Test Coverage Targets
- Core functionality: 90%+
- Infrastructure: 85%+
- Domain services: 80%+
- Interfaces: 70%+

### Running Specific Tests
```bash
# Single test file
python -m pytest university_system/tests/test_authentication.py -v

# Single test class
python -m pytest university_system/tests/test_authentication.py::TestAuthentication -v

# Single test method
python -m pytest university_system/tests/test_authentication.py::TestAuthentication::test_login -v
```

## Common Patterns

### Adding a New Feature

1. **Domain Layer**: Implement business logic in appropriate domain
2. **Service Layer**: Create service functions if needed
3. **Interface Layer**: Add UI (CLI/GUI/Web)
4. **Database**: Add tables/migrations if needed
5. **Tests**: Write unit and integration tests
6. **Activity Logging**: Add audit trail logging
7. **Documentation**: Update relevant docs

### Working with Transactions
```python
try:
    with transaction() as conn:
        # Multiple operations in single transaction
        conn.execute("INSERT INTO students ...")
        conn.execute("INSERT INTO enrollments ...")
        # Auto-commits if no exception
except Exception as e:
    # Auto-rollback already happened
    log_error(e, context)
    raise
```

### Error Handling
```python
from university_system.infrastructure.exceptions import (
    DatabaseError,
    AuthenticationError,
    ValidationError
)

try:
    # Operation
    pass
except DatabaseError as e:
    logger.error(f"Database error: {e}")
    # Handle gracefully
except AuthenticationError as e:
    logger.warning(f"Auth failed: {e}")
    # Redirect to login
```

## Entry Points

- **Main**: `run.py` - Interactive menu
- **CLI**: `university_system/modules/shared/cli/cli_main.py` - Command-line interface
- **GUI**: `university_system/modules/shared/gui/main_gui.py` - Tkinter GUI
- **Web**: `university_system/modules/web/app.py` - Flask web server
- **Tests**: `university_system/tests/run_all_tests.py` - Test suite

## Key Files Reference

| Purpose | File Path |
|---------|-----------|
| Centralized paths | `modules/shared/constants/paths.py` |
| Database connection | `infrastructure/database/db.py` |
| Authentication | `infrastructure/auth/user_authentication.py` |
| Authorization | `infrastructure/auth/authorization.py` |
| Activity logging | `modules/shared/utils/activity_logger.py` |
| Configuration | `modules/shared/utils/config.py` |
| Email service | `infrastructure/email/email_service.py` |
| Global context | `infrastructure/shared_context.py` |

## Code Style

- **Formatter**: Black (line length: 100)
- **Linter**: Ruff
- **Type checker**: mypy
- **Style guide**: PEP 8
- **Docstrings**: NumPy/Google style
- **Import order**: isort

Format code before committing:
```bash
make format
make lint
```

## Troubleshooting

### Database Lock Errors
- Ensure only one instance is running
- Use WAL mode (enabled by default)
- Always use context managers
- Check connection pool limits

### Import Errors After Refactoring
```python
# Old (deprecated but works via __init__.py re-exports)
from university_system.modules.interfaces.gui.grade_tracking_gui import GradeTrackingApp

# New (recommended)
from university_system.modules.interfaces.gui.grade_tracking import GradeTrackingApp
```

### Permission Errors
```bash
# Fix data directory permissions
chmod -R 755 data/ logs/ backups/
```

### Module Not Found
```bash
# Always run from project root
cd /path/to/project
python run.py

# Use module syntax
python -m university_system.modules.shared.cli.cli_main
```

## Design Principles

1. **Domain-Driven Design**: Clear separation between domains
2. **Manager Pattern**: Large modules use manager classes
3. **Single Responsibility**: Each file has one clear purpose
4. **Explicit Imports**: No wildcard imports
5. **Context Managers**: Always use for resources (DB, files)
6. **Activity Logging**: Log all data modifications
7. **Permission Checks**: Enforce RBAC at service layer
8. **Transaction Safety**: Use `transaction()` for modifications
9. **Centralized Configuration**: Use `paths` module
10. **Backward Compatibility**: Old imports still work via `__init__.py`

## Additional Resources

- **Full Documentation**: `docs/README.md`
- **API Documentation**: `docs/development/API.md`
- **Security Guide**: `SECURITY.md`
- **Architecture Deep Dive**: `university_system/ARCHITECTURE.md` (if exists)
- **Module Documentation**: `docs/modules/`
