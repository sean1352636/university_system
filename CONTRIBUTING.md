# Contributing to Education System

Thank you for your interest in contributing to the Education System project. This guide covers everything you need to know to get started, follow our conventions, and submit high-quality pull requests.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Branch Naming Conventions](#branch-naming-conventions)
3. [Commit Message Format](#commit-message-format)
4. [How to Add a New Domain Module](#how-to-add-a-new-domain-module)
5. [Code Style](#code-style)
6. [Testing Requirements](#testing-requirements)
7. [PR Process](#pr-process)
8. [How to Add a New System](#how-to-add-a-new-system)

---

## Getting Started

1. **Fork the repository** on GitHub.

2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/<your-username>/university_system.git
   cd university_system
   ```

3. **Create and activate a Python virtual environment** (Python 3.10+):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt   # linters, formatters, test tools
   ```

5. **Copy the environment template** and fill in local values:
   ```bash
   cp .env.example .env
   ```

6. **Initialise the databases** (SQLite files are created automatically on first run):
   ```bash
   python run.py --mode cli
   ```

7. **Verify everything works**:
   ```bash
   make test
   ```

---

## Branch Naming Conventions

Use a prefix that describes the kind of change, followed by a `/` and a short kebab-case description:

| Prefix     | Use case                                      | Example                              |
|------------|-----------------------------------------------|--------------------------------------|
| `feature/` | New functionality or module                   | `feature/student-export`             |
| `bugfix/`  | Fixing a bug in existing code                 | `bugfix/login-session-timeout`       |
| `hotfix/`  | Urgent production fix                         | `hotfix/auth-token-expiry`           |
| `docs/`    | Documentation-only changes                    | `docs/update-api-guide`              |

Always branch from `main`:
```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

---

## Commit Message Format

Every commit message must follow the **type: description** format. Use the imperative mood ("add", not "added" or "adds").

### Types

| Type       | When to use                                            |
|------------|--------------------------------------------------------|
| `feat`     | A new feature or module                                |
| `fix`      | A bug fix                                              |
| `refactor` | Code restructuring with no behaviour change            |
| `test`     | Adding or updating tests only                          |
| `docs`     | Documentation changes only                             |
| `style`    | Formatting, whitespace, linting (no logic change)      |
| `chore`    | Build scripts, CI config, dependency updates           |
| `perf`     | Performance improvements                               |

### Examples

```
feat: add student export to CSV
fix: resolve login bug when MFA is disabled
refactor: extract shared pagination logic into utility
test: add coverage for enrollment edge cases
docs: update API authentication section in README
chore: upgrade Flask to 3.x in requirements
```

For multi-line messages, leave a blank line after the summary and add detail in the body:

```
feat: add bulk student import

Supports CSV and XLSX uploads. Validates required fields
(name, date of birth, year group) before inserting rows.
Adds progress feedback via the activity feed.
```

---

## How to Add a New Domain Module

Each system (college, secondary, primary, university) follows a consistent module structure. A complete module typically touches these integration points:

### 1. Service file

Create the business logic layer under the appropriate domain category:

```
education_system/<system>/modules/domain/<category>/<module_name>/services/<module_name>_service.py
```

The service must:
- Use `_conn()` to obtain a database connection via `connect(db_path)`.
- Wrap all DB operations in `try/except/finally` with `conn.close()` in the `finally` block.
- Raise domain-specific exceptions from `core/exceptions.py` where appropriate.

### 2. GUI file

Create the tkinter GUI panel:

```
education_system/<system>/modules/domain/<category>/<module_name>/gui/<module_name>_gui.py
```

- Inherit from `tk.Frame`.
- Use `ttk.Notebook` for tabbed layouts where the module has multiple views.
- Register the GUI in the system's sidebar navigation (typically in `modules/shared/gui/main_gui.py` or equivalent).

### 3. CLI entry

Add a CLI sub-command in the system's CLI main file:

```
education_system/<system>/modules/shared/cli/cli_main.py   # college
education_system/<system>/cli/cli_main.py                   # secondary, primary
```

### 4. API routes

Create a route file under the shared API layer:

```
education_system/shared/api/<system>/routes/<module_name>_routes.py
```

- Define a Flask `Blueprint`.
- Import and call the service layer for all operations.
- Use the shared JWT authentication decorators and validators.

### 5. Register in unified_server.py

Open `education_system/shared/api/unified_server.py` and add your blueprint to the system's blueprint list so it is mounted under `/api/v1/<system>/`.

### 6. Database schema

If the module needs new tables, add them to:

```
education_system/<system>/infrastructure/database/schema.py
```

### 7. Tests

Create a test file:

```
education_system/<system>/tests/<category>/test_<module_name>_service.py
```

- Use `pytest` with the shared `conftest.py` fixtures.
- Cover all CRUD operations plus edge cases.
- Aim for at least 80% coverage of the new service.

### Checklist for a new module

- [ ] Service file with full CRUD
- [ ] GUI panel wired into sidebar
- [ ] CLI sub-command (if applicable)
- [ ] API routes under `shared/api/<system>/routes/`
- [ ] Blueprint registered in `unified_server.py`
- [ ] Schema migration in `schema.py`
- [ ] Tests with >= 80% coverage
- [ ] CHANGELOG.md updated

---

## Code Style

| Tool           | Purpose              | Configuration                     |
|----------------|----------------------|-----------------------------------|
| **PEP 8**      | Style guide          | Followed throughout               |
| **Black**      | Code formatter       | Line length: **100**              |
| **Ruff**       | Linter               | Config in `pyproject.toml`        |
| **mypy**       | Static type checking | Config in `pyproject.toml`        |

### Quick reference

- Maximum line length: **100 characters**.
- Use double quotes for strings (Black default).
- Type-hint all public function signatures.
- Docstrings: use triple double-quotes; first line is a one-line summary.
- Imports: group into stdlib, third-party, local; one blank line between groups.

### Running checks locally

```bash
make format      # Run Black formatter
make lint        # Run Ruff linter
make type-check  # Run mypy
```

All three must pass before you open a PR.

---

## Testing Requirements

- **Framework**: `pytest`
- **Minimum coverage**: **80%** for any new or modified module.
- **Run the full suite**:
  ```bash
  make test
  ```
- **Run a single test file**:
  ```bash
  pytest education_system/college_system/tests/academics/test_student_service.py -v
  ```
- **Check coverage**:
  ```bash
  pytest --cov=education_system --cov-report=term-missing
  ```

### Test conventions

- Place tests in the `tests/` directory of the relevant system, organised by category (e.g., `tests/academics/`, `tests/pastoral/`).
- Use the shared fixtures in `conftest.py` (in-memory SQLite database, authenticated test client, etc.).
- Name test files `test_<module_name>_service.py`.
- Name test functions `test_<action>_<scenario>` (e.g., `test_create_student_success`, `test_enroll_duplicate_raises`).
- Mock external dependencies; never hit real SMTP servers or external APIs in tests.

---

## PR Process

1. **Ensure all quality checks pass locally**:
   ```bash
   make format
   make lint
   make type-check
   make test
   ```

2. **Update `CHANGELOG.md`** with a brief description of your changes under the `[Unreleased]` section. Group entries by type (Added, Changed, Fixed, Removed).

3. **Push your branch** and open a pull request against `main`:
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Fill in the PR template**:
   - Summarise what changed and why (1-3 bullet points).
   - Include a test plan describing how reviewers can verify the changes.

5. **Request a code review** from at least one maintainer.

6. **Address review feedback** with new commits (do not force-push over review comments).

7. CI must be green before merge. The pipeline runs:
   - `make lint` (Ruff)
   - `make format --check` (Black)
   - `make type-check` (mypy)
   - `make test` (pytest with coverage)
   - Security scan (Bandit)

---

## How to Add a New System

Adding a fifth (or beyond) education system requires changes across several shared components. Use the existing four systems (university, college, secondary, primary) as reference implementations.

### 1. Create the system directory

```
education_system/<new_system>/
    __init__.py
    __main__.py
    core/
        defaults.py          # DB path, system constants
        exceptions.py        # System-specific exceptions
    infrastructure/
        database/
            schema.py        # SQLite table definitions
            db.py            # Connection helper
        auth/                # Thin wrapper re-exporting from shared auth
    modules/
        domain/              # Domain modules (follow existing category layout)
        shared/
            gui/             # main_gui.py, dashboard_gui.py
            cli/             # cli_main.py
    tests/
        conftest.py
    data/
        db_files/            # SQLite databases created at runtime
```

### 2. Register in `run.py`

Update `run.py` (project root) to:
- Import the new system's launcher.
- Add it to the system selection logic so the universal login can route authenticated users to it.

### 3. Add shared auth support

In `education_system/shared/auth/schema.py`:
- Add the new system identifier to the `user_systems` seeding logic.
- Create default accounts (admin, staff, student, parent) for the new system following the password pattern `<Role>@<System>123`.

### 4. Create API routes

Add a new directory under the shared API layer:

```
education_system/shared/api/<new_system>/
    __init__.py              # Exports blueprints list + init_funcs list
    routes/
        auth_routes.py
        system_routes.py
        ...                  # One file per domain module
```

### 5. Register in `unified_server.py`

In `education_system/shared/api/unified_server.py`:
- Import the new system's blueprints and init functions from `shared/api/<new_system>/`.
- Call `_register_system_blueprints(app, blueprints, init_funcs, db_path, "<new_system>", "New System Label")`.

This mounts all routes under `/api/v1/<new_system>/`.

### 6. Update CI and documentation

- Add the new system to any CI matrix builds in `.github/workflows/`.
- Update `README.md` to document the new system.
- Add entries to `CHANGELOG.md`.

### Checklist for a new system

- [ ] System directory with core, infrastructure, modules, tests
- [ ] `__main__.py` entry point
- [ ] Database schema with `initialise_database()`
- [ ] Shared auth wrappers in `infrastructure/auth/`
- [ ] Default user accounts seeded via shared auth
- [ ] Registered in `run.py` system selection
- [ ] API routes under `shared/api/<new_system>/`
- [ ] Blueprints registered in `unified_server.py`
- [ ] Tests with `conftest.py` and initial coverage
- [ ] CI pipeline updated
- [ ] README and CHANGELOG updated
