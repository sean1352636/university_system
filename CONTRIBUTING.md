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

3. **Create and activate a Python virtual environment** (Python 3.11+):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install dependencies**:
   ```bash
   make install-dev           # requirements-dev.lock: production plus linters, formatters, test tools
   pip install -e . --no-deps # make education_system importable
   ```

5. **Copy the environment template** and fill in local values:
   ```bash
   cp .env.example .env
   ```

6. **Initialise the databases** (SQLite files are created automatically on first run):
   ```bash
   python -m education_system --university --cli
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
chore: upgrade Flask to 3.x in pyproject.toml
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

Each system (nursery, primary, secondary, sixth form, FE college, apprenticeships, university) has its own module layout, so copy a neighbouring module. A complete module typically touches these integration points. See [PROJECT_STRUCTURE.md](docs/reference/PROJECT_STRUCTURE.md) for the layout of each system.

### 1. Service file

Create the business logic layer under the appropriate domain area:

```
src/education_system/systems/<system>/domain/<area>/<module_name>/<module_name>.py     # school systems
src/education_system/systems/university/domains/<slice>/domain/<module_name>/          # university
src/education_system/systems/<system>/services/<module_name>_service.py                # FE college, apprenticeships
```

The service must:
- Use `_conn()` to obtain a database connection (`BaseService` in `platform/kernel/base/service.py`), or otherwise close every connection it opens in a `finally` block.
- Raise domain-specific exceptions from `education_system.platform.kernel.exceptions` where appropriate.
- Use the path constants in `education_system.paths` rather than building database paths by hand.

### 2. GUI file

Create the tkinter GUI panel:

```
src/education_system/systems/<system>/interfaces/gui/<area>/<module_name>/<module_name>_views.py
src/education_system/systems/university/domains/<slice>/interfaces/gui/<module_name>/
```

- Inherit from `tk.Frame` (or `BaseModuleGUI` in `platform/kernel/base/gui.py`).
- Use `ttk.Notebook` for tabbed layouts where the module has multiple views.
- Register the GUI in the system's navigation: `NAV_CATEGORIES` in `gui_main.py` (primary, secondary), `interfaces/gui/gui_main.py` (sixth form) or `menu.py` (nursery); `NAVIGATION` in `gui_main.py` (FE college); `NAV_BY_ROLE` in `interfaces/gui/gui_main.py` (apprenticeships); `shell/gui/main/` (university).

### 3. CLI entry

Add a CLI sub-command in the system's CLI menu:

```
src/education_system/systems/{primary,secondary,nursery}/cli_main.py
src/education_system/systems/sixth_form/interfaces/cli/cli_main.py
src/education_system/systems/{fe_college,apprenticeships}/interfaces/cli/menus.py
src/education_system/systems/university/shell/cli/menu_router.py
```

### 4. API routes

Create a route file in the API package. Routes never go under `platform/`:

```
src/education_system/api/<system>/routes/<module_name>_routes.py
src/education_system/api/university/<area>/<module_name>_routes.py   # university
```

- Define a Flask `Blueprint` with a bare `/api/<resource>` prefix; mounting adds the version and system segments.
- Import and call the service layer for all operations.
- Use the shared JWT authentication decorators and validators (`education_system.platform.delivery.api.auth`).

### 5. Register the blueprint

Add your blueprint to `ALL_BLUEPRINTS` in `src/education_system/api/<system>/routes/__init__.py`, or `DOMAIN_BLUEPRINTS` in `src/education_system/api/university/<area>/__init__.py`. `src/education_system/platform/delivery/api/registry.py` mounts those lists under the system's prefix, such as `/api/v1/university/` or `/api/v1/sixthform/`.

### 6. Database schema

If the module needs new tables:

- University: add an Alembic migration to `src/education_system/migrations/versions/`. Its `down_revision` must point at the current head.
- FE college, apprenticeships: add them to `infrastructure/persistence/schema.py`.
- Other systems: follow the neighbouring modules, which create their own tables with `CREATE TABLE IF NOT EXISTS` in the system's shared database.

### 7. Tests

Create a test file under the scope, mirroring the owning package:

```
tests/unit/systems/<system>/<area>/test_<module_name>_service.py
```

- Use `pytest` with the shared `conftest.py` fixtures.
- Cover all CRUD operations plus edge cases.
- Aim for at least 80% coverage of the new service.

### Checklist for a new module

- [ ] Service file with full CRUD
- [ ] GUI panel wired into navigation
- [ ] CLI sub-command (if applicable)
- [ ] API routes under `src/education_system/api/<system>/`
- [ ] Blueprint added to the package's blueprint list
- [ ] Schema change (Alembic migration or `schema.py`)
- [ ] Tests with >= 80% coverage
- [ ] CHANGELOG.md updated

---

## Code Style

| Tool           | Purpose              | Configuration                     |
|----------------|----------------------|-----------------------------------|
| **PEP 8**      | Style guide          | Followed throughout               |
| **Ruff format** | Code formatter      | Line length: **100**              |
| **Ruff**       | Linter               | Config in `pyproject.toml`        |
| **mypy**       | Static type checking | Config in `pyproject.toml`        |

### Quick reference

- Maximum line length: **100 characters**.
- Use double quotes for strings (Ruff format default).
- Type-hint all public function signatures.
- Docstrings: use triple double-quotes; first line is a one-line summary.
- Imports: group into stdlib, third-party, local; one blank line between groups.

### Running checks locally

```bash
make format      # Run Ruff formatter
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
  pytest tests/unit/platform/identity/auth/test_auth_core.py -v
  ```
- **Check coverage**:
  ```bash
  pytest --cov=education_system --cov-report=term-missing
  ```

### Test conventions

- Place tests in the repository's `tests/` tree, by scope and then owner (e.g., `tests/unit/systems/primary/`, `tests/integration/platform/`). See [TESTING.md](docs/TESTING.md).
- Use the shared fixtures in `tests/conftest.py` and `tests/fixtures/`; never touch a live database.
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
   - Ruff (`ruff check`, `ruff format --check`) and mypy
   - Architecture and layout checks (`tools/university/check_architecture.py`, `tools/check_layout.py`)
   - pytest with coverage
   - Security scan (Bandit, pip-audit)

---

## How to Add a New System

Adding another education system requires changes across several shared components. Use the existing seven systems as reference implementations; FE College (`systems/fe_college/`) is the smallest complete example. Searching the repository for `fe_college` shows every place a system is named.

### 1. Create the system package

```
src/education_system/systems/<new_system>/
    __init__.py          # Re-exports SYSTEM_NAME from manifest.py
    manifest.py          # Key, display name, package_dir, interfaces (a SystemManifest)
    cli_main.py          # run() entry point
    gui_main.py          # run() entry point
    domain/              # Business rules
    infrastructure/      # Persistence and external adapters
    interfaces/
        cli/
        gui/
```

Tests go in `tests/unit/systems/<new_system>/`, not in the package.

### 2. Register the system

In `src/education_system/systems/registry.py`, add the key to `SYSTEM_KEYS`. Read the name from `registry.display_names()`; do not restate it elsewhere. If the system has a main menu, add it to `systems/menu_inventory.py`.

### 3. Add its paths

In `src/education_system/paths.py`, which is the only module that defines paths:
- Add prefixed constants: `<NEW_SYSTEM>_BACKUP_DIR`, `<NEW_SYSTEM>_DATA_DIR` (under `VAR_DIR / "data"`), `<NEW_SYSTEM>_DB` and `<NEW_SYSTEM>_PACKAGE_ROOT`.
- Add `ensure_<new_system>_directories()`, and call it from `ensure_all_directories()`.
- Add entries to `SYSTEM_DB_PATHS`, `SYSTEM_ORDER`, `SYSTEM_LABELS` and `SYSTEM_LEARNER_TABLE`, and export the new names in `__all__`.

### 4. Register with the launcher

- `src/education_system/launcher/main.py`: add the command-line flag and map it to the system key.
- `src/education_system/launcher/systems.py`: add `run_<new_system>_cli`, `run_<new_system>_gui` and `run_<new_system>_tests`, add them to `LAUNCHERS`, and add the key to `AUTH_GUI_SYSTEMS` and `AUTH_CLI_SYSTEMS`.
- `src/education_system/launcher/menus.py`: add the system to `cli_select_system()`.
- `src/education_system/platform/delivery/gui/login_gui.py`: add its button colour to `_SYSTEM_COLOURS`.

### 5. Add shared auth support

In `src/education_system/platform/identity/auth/`:
- `defaults.py`: add the key to `SYSTEMS`, and to `SYSTEM_ROLES` if it doesn't use the shared role vocabulary.
- `schema.py`: add the new system to `_DEFAULT_ACCOUNTS`, including the superadmin's list of systems, and record the accounts in `docs/reference/DEFAULT_ACCOUNTS.md`.

Systems use the platform auth directly, so no wrapper package is needed.

### 6. Create API routes

```
src/education_system/api/<new_system>/
    routes/
        __init__.py          # Exports ALL_BLUEPRINTS
        ...                  # One file per domain module
    schemas/
```

`tools/gen_menu_routes.py` generates main-menu routes under `routes/menu/` from the system's menu.

### 7. Add the mount

In `src/education_system/platform/kernel/core/system_keys.py`, add the key to `CANONICAL_SYSTEMS`, and add an alias if the URL prefix differs from the key. API role checks rely on this: a prefix that doesn't resolve to a listed key falls back to the user's best role in any system.

In `src/education_system/platform/delivery/api/registry.py`, add a `Mount` to `SYSTEMS` naming the key, prefix, route module and label. If the URL segment differs from the system key, add it to `MOUNT_SYSTEM_KEYS`.

This mounts all routes under `/api/v1/<mount key>/`. The platform must not import from `education_system.api` or `education_system.systems` other than through this table.

### 8. Join the cross-system layer

- Subclass `PhaseAdapter` (`platform/cross_system/adapters/base.py`) in the system, with a `register()` function, and add its module path to `_PHASE_ADAPTERS` in `launcher/systems.py`. Systems never import each other.
- Declare `learner_login_roles` and `learner_ids_for_login` on the adapter so learner logins link automatically.
- Add `<new_system>_pk` and `<new_system>_student_id` slots to `student_journey` in `platform/identity/auth/schema.py`, and to `SYSTEM_SLOTS` in `platform/cross_system/identity_service.py`.
- Add the system to `PHASE_ORDER` or `PARALLEL_SYSTEMS` in `platform/cross_system/progression.py`.

### 9. Update CI and documentation

- Run `python tools/check_layout.py` (see `make layout-check`) and update its baseline if needed.
- Update `README.md` and `docs/reference/PROJECT_STRUCTURE.md` to document the new system, and add `docs/<new_system>/`.
- Add entries to `CHANGELOG.md`.

### Checklist for a new system

- [ ] System package with `manifest.py`, `domain/`, `infrastructure/`, `interfaces/`
- [ ] Added to `systems/registry.py`
- [ ] Prefixed constants and `SYSTEM_*` entries in `paths.py`
- [ ] Database schema with an idempotent init
- [ ] Default user accounts seeded via shared auth
- [ ] Registered in `launcher/main.py`, `launcher/systems.py` and `launcher/menus.py`
- [ ] API routes under `src/education_system/api/<new_system>/`
- [ ] `Mount` added to `platform/delivery/api/registry.py`
- [ ] Key added to `CANONICAL_SYSTEMS` in `platform/kernel/core/system_keys.py`
- [ ] `PhaseAdapter`, `student_journey` slots and progression entry
- [ ] Tests under `tests/unit/systems/<new_system>/`
- [ ] README, PROJECT_STRUCTURE and CHANGELOG updated
