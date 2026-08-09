# Adding New Modules to the Secondary School System

> Last Updated: March 2026

This guide walks through every step required to add a new domain module. We will use a fictional **"Rewards"** module as the running example, placed under `pastoral_care/`.

## Table of Contents

- [1. Directory Structure](#1-directory-structure)
- [2. Database Schema](#2-database-schema)
- [3. Exception Class](#3-exception-class)
- [4. Service Layer](#4-service-layer)
- [5. GUI Panel](#5-gui-panel)
- [6. CLI Menu](#6-cli-menu)
- [7. Registration](#7-registration)
- [8. Writing Tests](#8-writing-tests)
- [Checklist](#checklist)

---

## 1. Directory Structure

Create the following directory tree under the appropriate domain category in `modules/domain/`:

```
modules/domain/pastoral_care/rewards/
├── __init__.py
├── services/
│   ├── __init__.py
│   └── rewards_service.py
├── gui/
│   ├── __init__.py
│   └── rewards_gui.py
└── cli/
    └── __init__.py
```

```bash
# Create the directories
mkdir -p education_system/secondary_school/modules/domain/pastoral_care/rewards/{services,gui,cli}

# Create __init__.py files
touch education_system/secondary_school/modules/domain/pastoral_care/rewards/__init__.py
touch education_system/secondary_school/modules/domain/pastoral_care/rewards/services/__init__.py
touch education_system/secondary_school/modules/domain/pastoral_care/rewards/gui/__init__.py
touch education_system/secondary_school/modules/domain/pastoral_care/rewards/cli/__init__.py
```

---

## 2. Database Schema

Add your table definition to `infrastructure/database/schema.py` in the `TABLES` dictionary. Always use `CREATE TABLE IF NOT EXISTS` for idempotent initialization.

```python
# In infrastructure/database/schema.py, add to the TABLES dict:

"rewards": """
    CREATE TABLE IF NOT EXISTS rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        awarded_by INTEGER,
        reward_type TEXT NOT NULL DEFAULT 'merit',
        category TEXT NOT NULL,
        points INTEGER NOT NULL DEFAULT 1,
        description TEXT,
        date_awarded TEXT NOT NULL DEFAULT (datetime('now')),
        academic_year TEXT,
        term TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (student_id) REFERENCES students(id),
        FOREIGN KEY (awarded_by) REFERENCES users(id)
    )
""",
```

### Schema Guidelines

- Use `INTEGER PRIMARY KEY AUTOINCREMENT` for the primary key.
- Include `created_at` (and `updated_at` if records are mutable) with `DEFAULT (datetime('now'))`.
- Always declare `FOREIGN KEY` constraints -- they are enforced via `PRAGMA foreign_keys = ON`.
- Use `TEXT` for dates (ISO 8601 format: `YYYY-MM-DD` or `datetime('now')`).
- Add `DEFAULT` values where sensible to keep service code concise.
- Table names are `snake_case` and plural.

---

## 3. Exception Class

Add a dedicated exception to `core/exceptions.py`:

```python
class RewardsError(SchoolSystemError):
    """Rewards and merits errors."""
```

Place it in alphabetical order among the existing exception classes. Every module should have its own exception type so callers can catch domain-specific errors without catching unrelated failures.

---

## 4. Service Layer

The service layer is the core of every module. It encapsulates all business logic and database access.

### Full Example: `rewards_service.py`

```python
"""Rewards management service."""

from datetime import datetime
import logging

from education_system.secondary_school.core.exceptions import RewardsError, ValidationError
from education_system.secondary_school.infrastructure.database.db import connect
from education_system.secondary_school.infrastructure.database.constants import REWARD_TYPES
from education_system.secondary_school.infrastructure.validation.validators import validate_non_empty

logger = logging.getLogger(__name__)


class RewardsService:
    """Service for managing student rewards and merits."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        """Get a database connection."""
        return connect(self._db_path)

    # -- Create -------------------------------------------------------

    def award_reward(
        self,
        student_id: int,
        category: str,
        reward_type: str = "merit",
        points: int = 1,
        description: str | None = None,
        awarded_by: int | None = None,
        academic_year: str | None = None,
        term: str | None = None,
    ) -> dict:
        """Award a reward to a student."""
        category = validate_non_empty(category, "Category")

        if reward_type not in REWARD_TYPES:
            raise ValidationError(
                f"Invalid reward type '{reward_type}'. "
                f"Must be one of: {', '.join(REWARD_TYPES)}"
            )

        if points < 1:
            raise ValidationError("Points must be at least 1")

        conn = self._conn()
        try:
            # Verify the student exists
            student = conn.execute(
                "SELECT id FROM students WHERE id = ?", (student_id,)
            ).fetchone()
            if not student:
                raise RewardsError(f"Student with id {student_id} not found")

            conn.execute(
                """INSERT INTO rewards
                   (student_id, awarded_by, reward_type, category,
                    points, description, academic_year, term)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, awarded_by, reward_type, category,
                 points, description, academic_year, term),
            )
            conn.commit()
            reward_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            row = conn.execute(
                "SELECT * FROM rewards WHERE id = ?", (reward_id,)
            ).fetchone()
            logger.info("Reward %s awarded to student %s", reward_id, student_id)
            return dict(row)
        except RewardsError:
            raise
        except Exception as e:
            logger.error("Failed to award reward: %s", e)
            raise RewardsError(f"Failed to award reward: {e}") from e
        finally:
            conn.close()

    # -- Read ---------------------------------------------------------

    def get_reward(self, reward_id: int) -> dict | None:
        """Get a single reward by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM rewards WHERE id = ?", (reward_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_rewards(
        self,
        student_id: int | None = None,
        reward_type: str | None = None,
        term: str | None = None,
    ) -> list[dict]:
        """List rewards with optional filters."""
        clauses = []
        params = []
        if student_id is not None:
            clauses.append("student_id = ?")
            params.append(student_id)
        if reward_type:
            clauses.append("reward_type = ?")
            params.append(reward_type)
        if term:
            clauses.append("term = ?")
            params.append(term)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM rewards {where} ORDER BY date_awarded DESC",
                params,
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_points(self, student_id: int) -> int:
        """Get total reward points for a student."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(points), 0) AS total FROM rewards WHERE student_id = ?",
                (student_id,),
            ).fetchone()
            return row["total"]
        finally:
            conn.close()

    # -- Delete -------------------------------------------------------

    def delete_reward(self, reward_id: int) -> bool:
        """Delete a reward record."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "DELETE FROM rewards WHERE id = ?", (reward_id,)
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise RewardsError(f"Reward {reward_id} not found")
            logger.info("Reward %s deleted", reward_id)
            return True
        finally:
            conn.close()
```

### Service Layer Rules

| Rule | Detail |
|------|--------|
| **Constructor** | Accept optional `db_path: str \| None = None` for test injection |
| **`_conn()` method** | Always return `connect(self._db_path)` |
| **Connection cleanup** | Use `try/finally` with `conn.close()` in every public method |
| **Parameterized queries** | Always `?` placeholders -- never f-strings or `.format()` for SQL values |
| **Validate early** | Check inputs before touching the database |
| **Return dicts** | Convert `sqlite3.Row` to `dict()` before returning |
| **Commit explicitly** | Call `conn.commit()` after INSERT/UPDATE/DELETE |
| **Logging** | Use `logger.info()` for successful mutations, `logger.error()` for failures |
| **Domain exceptions** | Raise your module's specific error type (e.g. `RewardsError`) |

---

## 5. GUI Panel

GUI panels inherit from `tk.Frame` and are embedded in the main application's content area.

### Pattern: `rewards_gui.py`

```python
"""Rewards management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.pastoral_care.rewards.services.rewards_service import (
    RewardsService,
)
from education_system.secondary_school.core.exceptions import RewardsError, ValidationError


class RewardsPanel(tk.Frame):
    """Panel for viewing and awarding student rewards."""

    def __init__(self, parent, db_path=None, user=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._service = RewardsService(db_path)
        self._user = user
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        # -- Toolbar --
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=5)

        ttk.Button(toolbar, text="Award Reward", command=self._on_add).pack(side="left")
        ttk.Button(toolbar, text="Refresh", command=self._refresh).pack(side="left", padx=5)

        # -- Search --
        self._search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self._search_var, width=25).pack(side="right")
        ttk.Label(toolbar, text="Search:").pack(side="right", padx=(0, 5))

        # -- Treeview --
        columns = ("id", "student_id", "type", "category", "points", "date")
        self._tree = ttk.Treeview(self, columns=columns, show="headings", height=20)
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=100)
        self._tree.pack(fill="both", expand=True, padx=10, pady=5)

        # -- Scrollbar --
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _refresh(self):
        """Reload data from the service into the treeview."""
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            rewards = self._service.list_rewards()
            for r in rewards:
                self._tree.insert("", "end", values=(
                    r["id"], r["student_id"], r["reward_type"],
                    r["category"], r["points"], r["date_awarded"],
                ))
        except RewardsError as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        """Open dialog to award a new reward."""
        dialog = _RewardDialog(self, title="Award Reward")
        self.wait_window(dialog)
        if dialog.result:
            try:
                self._service.award_reward(**dialog.result)
                self._refresh()
            except (RewardsError, ValidationError) as e:
                messagebox.showerror("Error", str(e))


class _RewardDialog(tk.Toplevel):
    """Modal dialog for awarding a reward."""

    def __init__(self, parent, title="Reward", **kwargs):
        super().__init__(parent, **kwargs)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)

        fields = [
            ("Student ID (row id)", "student_id"),
            ("Category", "category"),
            ("Points", "points"),
            ("Description", "description"),
        ]
        self._vars = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(container, text=label, anchor="w").grid(row=i, column=0, sticky="w", **pad)
            var = tk.StringVar()
            ttk.Entry(container, textvariable=var, width=30).grid(row=i, column=1, sticky="ew", **pad)
            self._vars[key] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {
            "student_id": int(self._vars["student_id"].get()),
            "category": self._vars["category"].get(),
            "points": int(self._vars["points"].get() or "1"),
            "description": self._vars["description"].get() or None,
        }
        self.destroy()
```

### GUI Rules

| Rule | Detail |
|------|--------|
| Inherit from `tk.Frame` | Panels are embedded in the main window |
| Accept `db_path`, `user` | Passed by the main app for service instantiation |
| Call services only | Never access the DB directly from GUI code |
| Modal dialogs | Use `tk.Toplevel` + `grab_set()` |
| Error display | Use `messagebox.showerror()` for caught exceptions |
| Treeview for lists | Use `ttk.Treeview` with `show="headings"` |
| Refresh pattern | Clear + reload from service after mutations |

---

## 6. CLI Menu

CLI modules provide a text-based menu for the same functionality. The pattern uses numbered menus with role-based access.

```python
# In cli/__init__.py or a dedicated cli file:

"""Rewards CLI menu."""

from education_system.secondary_school.modules.domain.pastoral_care.rewards.services.rewards_service import (
    RewardsService,
)
from education_system.secondary_school.core.exceptions import RewardsError, ValidationError


def rewards_menu(db_path=None, user=None):
    """Rewards management sub-menu."""
    service = RewardsService(db_path)

    while True:
        print("\n--- Rewards Management ---")
        print("  [1] Award Reward")
        print("  [2] List Rewards")
        print("  [3] Student Points Total")
        print("  [0] Back")
        choice = input("Select option: ").strip()

        if choice == "1":
            try:
                sid = int(input("Student ID (row id): ").strip())
                category = input("Category: ").strip()
                points = int(input("Points [1]: ").strip() or "1")
                desc = input("Description (optional): ").strip() or None
                reward = service.award_reward(
                    student_id=sid, category=category,
                    points=points, description=desc,
                )
                print(f"  Reward #{reward['id']} awarded ({points} points)")
            except (RewardsError, ValidationError, ValueError) as e:
                print(f"  Error: {e}")
        elif choice == "2":
            rewards = service.list_rewards()
            for r in rewards:
                print(f"  #{r['id']}  Student {r['student_id']}  "
                      f"{r['reward_type']}  {r['category']}  {r['points']}pts")
        elif choice == "3":
            try:
                sid = int(input("Student ID (row id): ").strip())
                total = service.get_student_points(sid)
                print(f"  Total points: {total}")
            except ValueError as e:
                print(f"  Error: {e}")
        elif choice == "0":
            break
```

---

## 7. Registration

After creating the module, register it in the relevant places so it appears in the application.

### 7a. Module `__init__.py`

In the module's `__init__.py`, export the main classes:

```python
# modules/domain/pastoral_care/rewards/__init__.py
from education_system.secondary_school.modules.domain.pastoral_care.rewards.services.rewards_service import (
    RewardsService,
)
```

### 7b. Sidebar (GUI)

In `main_gui.py`, add the module to the sidebar configuration so it appears in the navigation. Follow the existing pattern of module registration -- add an entry in the sidebar items list for the appropriate category with the panel class and label.

### 7c. CLI Main Menu

In `cli/cli_main.py`, import your menu function and add it to the appropriate sub-menu section:

```python
from education_system.secondary_school.modules.domain.pastoral_care.rewards.cli import rewards_menu

# Then in the pastoral_care sub-menu options list, add:
("rewards", "Rewards Management", lambda: rewards_menu(db_path, user)),
```

### 7d. API Routes (optional)

If the module needs REST endpoints, create a Flask Blueprint in `api/routes/` and register it in `api/api_server.py`.

---

## 8. Writing Tests

Create a test file in `tests/`:

```python
# tests/test_rewards_service.py

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
    """Award a sample reward for testing."""
    return rewards_service.award_reward(
        student_id=sample_student["id"],
        category="achievement",
        reward_type="merit",
        points=5,
        description="Excellent homework",
    )


class TestRewardsService:
    def test_award_reward(self, rewards_service, sample_student):
        reward = rewards_service.award_reward(
            student_id=sample_student["id"],
            category="effort",
            points=3,
        )
        assert reward["student_id"] == sample_student["id"]
        assert reward["category"] == "effort"
        assert reward["points"] == 3
        assert reward["reward_type"] == "merit"

    def test_award_reward_invalid_type(self, rewards_service, sample_student):
        with pytest.raises(ValidationError, match="Invalid reward type"):
            rewards_service.award_reward(
                student_id=sample_student["id"],
                category="effort",
                reward_type="invalid_type",
            )

    def test_award_reward_nonexistent_student(self, rewards_service):
        with pytest.raises(RewardsError, match="not found"):
            rewards_service.award_reward(student_id=9999, category="effort")

    def test_get_reward(self, rewards_service, sample_reward):
        found = rewards_service.get_reward(sample_reward["id"])
        assert found is not None
        assert found["category"] == "achievement"

    def test_list_rewards(self, rewards_service, sample_student):
        rewards_service.award_reward(student_id=sample_student["id"], category="effort")
        rewards_service.award_reward(student_id=sample_student["id"], category="homework")
        all_rewards = rewards_service.list_rewards(student_id=sample_student["id"])
        assert len(all_rewards) == 2

    def test_get_student_points(self, rewards_service, sample_student):
        rewards_service.award_reward(student_id=sample_student["id"], category="effort", points=3)
        rewards_service.award_reward(student_id=sample_student["id"], category="homework", points=5)
        total = rewards_service.get_student_points(sample_student["id"])
        assert total == 8

    def test_delete_reward(self, rewards_service, sample_reward):
        assert rewards_service.delete_reward(sample_reward["id"]) is True
        assert rewards_service.get_reward(sample_reward["id"]) is None

    def test_delete_nonexistent_reward(self, rewards_service):
        with pytest.raises(RewardsError, match="not found"):
            rewards_service.delete_reward(9999)
```

Tests use the shared `db_path` and `sample_student` fixtures from `tests/conftest.py`, which create a fresh temporary database for each test. See [TESTING_GUIDE.md](TESTING_GUIDE.md) for full details.

---

## Checklist

Use this checklist when adding a new module:

- [ ] Created directory structure: `modules/domain/<category>/<module>/` with `services/`, `gui/`, `cli/` subdirectories
- [ ] Added `__init__.py` to every new directory
- [ ] Added `CREATE TABLE IF NOT EXISTS` to `infrastructure/database/schema.py`
- [ ] Added exception class to `core/exceptions.py`
- [ ] Created service class with `__init__(db_path)`, `_conn()`, `try/finally` connection cleanup
- [ ] All SQL uses parameterized queries (`?` placeholders)
- [ ] Created GUI panel inheriting from `tk.Frame`
- [ ] Created CLI menu function (if needed)
- [ ] Registered module in sidebar (`main_gui.py`)
- [ ] Registered module in CLI menu (`cli/cli_main.py`)
- [ ] Created API routes (if needed)
- [ ] Written tests in `tests/test_<module>_service.py`
- [ ] Tests pass: `pytest education_system/secondary_school/tests/test_<module>_service.py -v`
- [ ] Code formatted: `black education_system/secondary_school/modules/domain/<category>/<module>/`
- [ ] Code linted: `ruff check education_system/secondary_school/modules/domain/<category>/<module>/`
