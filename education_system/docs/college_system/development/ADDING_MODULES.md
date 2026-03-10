# College System -- Adding a New Domain Module

This guide walks through every step required to add a new domain module to the Sixth Form College Management System, using a hypothetical "awards" module as the running example.

---

## Module Structure

Every domain module lives under `education_system/college_system/modules/domain/` and follows this directory layout:

```
modules/domain/awards/
    __init__.py
    services/
        __init__.py
        awards_service.py
    gui/
        __init__.py
        awards_gui.py
    cli/
        __init__.py
        awards_cli.py
```

Not every module needs all three interfaces (services, gui, cli), but the services layer is mandatory -- it is the single source of business logic that the API, GUI, and CLI all depend on.


## Step 1: Define an Exception

Add a module-specific exception to `core/exceptions.py`. All domain exceptions inherit from `CollegeSystemError`:

```python
# In education_system/college_system/core/exceptions.py

class AwardsError(CollegeSystemError):
    """Awards related errors."""
```

This exception will be raised by the service layer and caught by the API error handlers.


## Step 2: Add Database Tables

Add the required table(s) to the schema initialisation in `infrastructure/database/schema.py`. Locate the `init_db()` function and add a `CREATE TABLE IF NOT EXISTS` statement:

```sql
CREATE TABLE IF NOT EXISTS awards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'academic',
    awarded_date TEXT DEFAULT (date('now')),
    awarded_by INTEGER,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (awarded_by) REFERENCES users(id)
);
```


## Step 3: Create the Service Class

Create the service file at `modules/domain/awards/services/awards_service.py`. Follow the established pattern:

```python
"""Awards management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import AwardsError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.validation.validators import validate_non_empty

import logging

logger = logging.getLogger(__name__)


class AwardsService:
    """Service for managing student awards."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_award(self, student_id: int, title: str,
                     description: str | None = None,
                     category: str = "academic",
                     awarded_by: int | None = None) -> dict:
        """Create a new award record."""
        title = validate_non_empty(title, "Title")

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO awards (student_id, title, description, category, awarded_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, title, description, category, awarded_by),
            )
            conn.commit()
            award_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            logger.info("Award created: id=%d for student=%d", award_id, student_id)
            return self.get_award(award_id)
        except Exception as e:
            conn.rollback()
            raise AwardsError(f"Failed to create award: {e}") from e
        finally:
            conn.close()

    def get_award(self, award_id: int) -> dict | None:
        """Get an award by primary key."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM awards WHERE id = ?", (award_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_awards(self, student_id: int | None = None,
                    category: str | None = None,
                    limit: int = 100, offset: int = 0) -> list[dict]:
        """List awards with optional filters."""
        sql = "SELECT * FROM awards WHERE 1=1"
        params = []

        if student_id:
            sql += " AND student_id = ?"
            params.append(student_id)
        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY awarded_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_award(self, award_id: int, **kwargs) -> dict:
        """Update an award record."""
        allowed = {"title", "description", "category", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

        if not updates:
            raise ValidationError("No valid fields to update.")

        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [award_id]

        conn = self._conn()
        try:
            conn.execute(f"UPDATE awards SET {set_clause} WHERE id = ?", params)
            conn.commit()
            result = self.get_award(award_id)
            if not result:
                raise AwardsError("Award not found.")
            return result
        finally:
            conn.close()

    def delete_award(self, award_id: int) -> bool:
        """Delete an award record."""
        conn = self._conn()
        try:
            cursor = conn.execute("DELETE FROM awards WHERE id = ?", (award_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise AwardsError("Award not found.")
            logger.info("Award deleted: id=%d", award_id)
            return True
        except AwardsError:
            raise
        except Exception as e:
            conn.rollback()
            raise AwardsError(f"Failed to delete award: {e}") from e
        finally:
            conn.close()

    def count_awards(self, student_id: int | None = None) -> int:
        """Count total awards."""
        conn = self._conn()
        try:
            if student_id:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM awards WHERE student_id = ?", (student_id,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as cnt FROM awards").fetchone()
            return row["cnt"]
        finally:
            conn.close()
```

Key patterns to follow:

- `__init__` accepts `db_path` and stores it as `self._db_path`.
- `_conn()` returns `connect(self._db_path)`.
- Every method opens a connection, uses `try/finally` to ensure `conn.close()`, and calls `conn.commit()` after writes.
- Rollback on failure, re-raise as the domain exception.
- Use logging for significant operations.


## Step 4: Add API Routes

Create the route file at `api/routes/awards_routes.py`:

```python
"""Awards API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.awards.services.awards_service import AwardsService

awards_bp = Blueprint("awards", __name__, url_prefix="/api/awards")

_db_path = None


def init_awards_routes(db_path=None):
    global _db_path
    _db_path = db_path


@awards_bp.route("", methods=["GET"])
@token_required
def list_awards():
    svc = AwardsService(_db_path)
    limit, offset = get_pagination_params()
    awards = svc.list_awards(
        student_id=request.args.get("student_id", type=int),
        category=request.args.get("category"),
        limit=limit, offset=offset,
    )
    total = svc.count_awards(student_id=request.args.get("student_id", type=int))
    return jsonify(paginated_response(awards, total))


@awards_bp.route("/<int:award_id>", methods=["GET"])
@token_required
def get_award(award_id):
    svc = AwardsService(_db_path)
    award = svc.get_award(award_id)
    if not award:
        return jsonify({"error": "Award not found."}), 404
    return jsonify({"data": award})


@awards_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_award():
    data = get_json_body()
    require_fields(data, "student_id", "title")
    svc = AwardsService(_db_path)
    award = svc.create_award(
        student_id=data["student_id"],
        title=data["title"],
        description=data.get("description"),
        category=data.get("category", "academic"),
        awarded_by=g.current_user["user_id"],
    )
    return jsonify({"message": "Award created.", "data": award}), 201


@awards_bp.route("/<int:award_id>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_award(award_id):
    data = get_json_body()
    svc = AwardsService(_db_path)
    award = svc.update_award(award_id, **data)
    return jsonify({"message": "Award updated.", "data": award})


@awards_bp.route("/<int:award_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_award(award_id):
    svc = AwardsService(_db_path)
    svc.delete_award(award_id)
    return jsonify({"message": "Award deleted."})
```

Key patterns:

- Create a `Blueprint` with a descriptive name and `/api/<resource>` prefix.
- Use a module-level `_db_path` global, set via `init_awards_routes(db_path)`.
- Apply `@token_required` to all routes.
- Apply `@role_required(...)` to mutation routes.
- Use `get_json_body()` and `require_fields()` for input validation.
- Use `get_pagination_params()` and `paginated_response()` for list endpoints.
- Return `201` for POST create, `200` for everything else.


## Step 5: Register Routes in the Routes Package

Edit `api/routes/__init__.py` to import and register the new blueprint:

```python
# Add the import
from education_system.college_system.api.routes.awards_routes import awards_bp, init_awards_routes

# Add to ALL_BLUEPRINTS list
ALL_BLUEPRINTS = [
    ...
    awards_bp,
]

# Add to ALL_INIT_FUNCS list
ALL_INIT_FUNCS = [
    ...
    init_awards_routes,
]
```

The app factory in `api_server.py` iterates over both lists, so no changes are needed there.


## Step 6: Add an Error Handler (Optional)

If you want the API to return a specific HTTP status for your exception, add a handler in `api/errors.py`:

```python
from education_system.college_system.core.exceptions import AwardsError

@app.errorhandler(AwardsError)
def handle_awards_error(e):
    return jsonify({"error": "Awards Error", "message": str(e)}), 400
```

This is optional because unhandled `CollegeSystemError` subclasses will already be caught by the generic `CollegeSystemError` handler (returning 500). Adding a specific handler changes the status code to 400.


## Step 7: Add a Test Fixture

Add a fixture to `tests/conftest.py`:

```python
@pytest.fixture
def awards_service(db_path):
    """Create an AwardsService instance with the test database."""
    from education_system.college_system.modules.domain.awards.services.awards_service import AwardsService
    return AwardsService(db_path)
```


## Step 8: Write Tests

Create `tests/test_awards_service.py`:

```python
"""Tests for AwardsService."""

import pytest
from education_system.college_system.core.exceptions import AwardsError, ValidationError


class TestAwardsService:
    def test_create_award(self, awards_service, sample_student):
        award = awards_service.create_award(
            student_id=sample_student["id"],
            title="Outstanding Achievement",
            category="academic",
        )
        assert award["title"] == "Outstanding Achievement"
        assert award["student_id"] == sample_student["id"]
        assert award["category"] == "academic"

    def test_create_award_empty_title(self, awards_service, sample_student):
        with pytest.raises(ValidationError):
            awards_service.create_award(student_id=sample_student["id"], title="")

    def test_get_award_not_found(self, awards_service):
        assert awards_service.get_award(9999) is None

    def test_list_awards(self, awards_service, sample_student):
        awards_service.create_award(student_id=sample_student["id"], title="A")
        awards_service.create_award(student_id=sample_student["id"], title="B")
        results = awards_service.list_awards(student_id=sample_student["id"])
        assert len(results) == 2

    def test_update_award(self, awards_service, sample_student):
        created = awards_service.create_award(
            student_id=sample_student["id"], title="Original",
        )
        updated = awards_service.update_award(created["id"], title="Updated")
        assert updated["title"] == "Updated"

    def test_delete_award(self, awards_service, sample_student):
        created = awards_service.create_award(
            student_id=sample_student["id"], title="ToDelete",
        )
        result = awards_service.delete_award(created["id"])
        assert result is True
        assert awards_service.get_award(created["id"]) is None

    def test_count_awards(self, awards_service, sample_student):
        awards_service.create_award(student_id=sample_student["id"], title="A")
        awards_service.create_award(student_id=sample_student["id"], title="B")
        assert awards_service.count_awards(student_id=sample_student["id"]) == 2
```


## Step 9: Add GUI and CLI (Optional)

### GUI Panel

Create `modules/domain/awards/gui/awards_gui.py` with a `tk.Frame` subclass:

```python
import tkinter as tk
from tkinter import ttk


class AwardsPanel(tk.Frame):
    def __init__(self, parent, db_path=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._build_ui()

    def _build_ui(self):
        # Build your treeview, forms, buttons, etc.
        ...
```

### CLI Handler

Create `modules/domain/awards/cli/awards_cli.py` with menu functions:

```python
from education_system.college_system.modules.domain.awards.services.awards_service import AwardsService


def awards_menu(db_path):
    """Awards management CLI menu."""
    svc = AwardsService(db_path)
    while True:
        print("\n  Awards Management")
        print("  [1] List Awards")
        print("  [2] Create Award")
        print("  [0] Back")
        choice = input("  > ").strip()
        if choice == "0":
            break
        elif choice == "1":
            ...
        elif choice == "2":
            ...
```


## Checklist

When adding a new module, verify the following:

- [ ] Exception class added to `core/exceptions.py`
- [ ] Database table(s) added to `infrastructure/database/schema.py`
- [ ] `__init__.py` files created in `modules/domain/<name>/`, `services/`, `gui/`, `cli/`
- [ ] Service class created with the standard `_conn()` / `try/finally` pattern
- [ ] API route blueprint created with `init_*_routes()` function
- [ ] Blueprint and init function registered in `api/routes/__init__.py`
- [ ] Error handler added to `api/errors.py` (optional, for 400 status)
- [ ] Test fixture added to `tests/conftest.py`
- [ ] Test file created with CRUD tests and error-path tests
- [ ] Tests pass: `python -m pytest tests/test_awards_service.py -v`
