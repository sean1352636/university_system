# Adding New Domain Modules

Last Updated: October 2026

This guide walks through creating a new domain module for the Primary School Management System. Each module follows the same structure: a data layer for business logic, a tkinter window for the GUI, a CLI handler for terminal access, and a blueprint for the REST API.

`src/education_system/systems/primary/domain/academics/enrichment/clubs/` is a complete working module; read it alongside this guide.

---

## Step 1: Choose the Domain Area

Modules are grouped into areas under `src/education_system/systems/primary/domain/`:

| Area            | Examples                                                  |
|-----------------|-----------------------------------------------------------|
| `academics`     | academic_year, attendance, classes, homework, timetable   |
| `admissions`    | admissions, enrolment                                     |
| `assessment`    | phonics, ks1_sats, ks2_sats, mtc, eyfs_profile, progress  |
| `finance`       | dinner_money, funding, pupil_premium, receipts, trips     |
| `governance`    | compliance, gdpr, mfa, policies, risk_management          |
| `learners`      | pupils (with onboarding, leavers, bulk_operations)        |
| `operations`    | assets, communications, document_hub, reporting, visitors |
| `pastoral`      | behaviour, house_points, send, transport, wellbeing       |
| `safeguarding`  | safeguarding, prevent_duty                                |
| `staff`         | appraisals, cover, cpd, departments, staff_hr             |

Place your new module in the area that best fits its domain.

---

## Step 2: Create the Directory Structure

Domain rules and screens live in separate trees. For an `activities` module in `academics/enrichment`, beside the existing `clubs`:

```
src/education_system/systems/primary/
├── domain/academics/enrichment/activities/
│   ├── __init__.py
│   └── activities.py              # Schema, dataclasses, validation, queries
└── interfaces/
    ├── cli/academics/enrichment/activities/
    │   ├── __init__.py
    │   └── activities_cli.py      # Terminal menus
    └── gui/academics/enrichment/activities/
        ├── __init__.py
        └── activities_views.py    # tkinter windows

src/education_system/api/primary/routes/
└── activities_routes.py           # Flask blueprint
```

Create the directories:

```bash
cd src/education_system/systems/primary
mkdir -p domain/academics/enrichment/activities
mkdir -p interfaces/cli/academics/enrichment/activities
mkdir -p interfaces/gui/academics/enrichment/activities
touch domain/academics/enrichment/activities/__init__.py
touch interfaces/cli/academics/enrichment/activities/__init__.py
touch interfaces/gui/academics/enrichment/activities/__init__.py
```

Domain modules must stay free of Tkinter, Flask and CLI code. Some `domain/` folders still hold `*_cli.py` and `*_views.py` files; those are `layout-shim` forwarders to `interfaces/`, so do not add new ones.

---

## Step 3: Define the Database Schema

Each module owns its tables. There is no central schema file and these tables are not managed by Alembic: a module declares a `_SCHEMA` string and creates it from its own `init_db()`, using `CREATE TABLE IF NOT EXISTS`.

All primary modules share one database, `var/data/primary/primary.db`, so a module normally borrows the pupils module's connection. That connection has `row_factory = sqlite3.Row` and foreign keys switched on.

```python
# In domain/academics/enrichment/activities/activities.py

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrichment_activities (
    activity_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    category       TEXT NOT NULL,
    max_capacity   INTEGER DEFAULT 30,
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS enrichment_enrollments (
    enrollment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id    INTEGER NOT NULL,
    pupil_id       TEXT NOT NULL,
    enrolled_date  TEXT DEFAULT (date('now')),
    status         TEXT NOT NULL DEFAULT 'active',
    UNIQUE(activity_id, pupil_id),
    FOREIGN KEY(activity_id) REFERENCES enrichment_activities(activity_id) ON DELETE CASCADE,
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
"""
```

To add a column to a table that already exists in live databases, add an `ALTER TABLE` step as `_migrate()` does in `domain/learners/pupils/pupils.py`.

---

## Step 4: Handle Validation Errors

There is no system-wide exception hierarchy. Primary modules raise `ValidationError`, which each module defines or imports. Modules that depend on pupils import the one in `domain/learners/pupils/pupils.py`, and the screens and routes catch it to show the message to the user.

Reusable validators are in `src/education_system/platform/kernel/validation/validators.py`.

---

## Step 5: Create the Data Layer

The data layer is a module of plain functions, not a service class. It contains all business logic and database operations, and it is the most important file in the module.

### `domain/academics/enrichment/activities/activities.py`

```python
"""Enrichment activities data layer."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

# _SCHEMA from Step 3 goes here.


@dataclass
class Activity:
    activity_id: int
    name: str
    category: str
    max_capacity: int | None
    is_active: bool


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Activity:
    return Activity(
        activity_id=r["activity_id"],
        name=r["name"],
        category=r["category"],
        max_capacity=r["max_capacity"],
        is_active=bool(r["is_active"]),
    )


def create(data: dict[str, Any]) -> Activity:
    init_db()
    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()
    if not name:
        raise ValidationError("Activity name is required")
    if not category:
        raise ValidationError("Category is required")
    try:
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO enrichment_activities (name, category, max_capacity) "
                "VALUES (?, ?, ?)",
                (name, category, data.get("max_capacity", 30)),
            )
            activity_id = cur.lastrowid
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValidationError(f"Activity {name!r} already exists") from exc
    logger.info("Created enrichment activity #%d %s", activity_id, name)
    rec = get(activity_id)
    assert rec is not None
    return rec


def get(activity_id: int) -> Activity | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM enrichment_activities WHERE activity_id = ?",
            (activity_id,),
        ).fetchone()
    return _row(r) if r else None


def list_all(*, active_only: bool = False) -> list[Activity]:
    init_db()
    sql = "SELECT * FROM enrichment_activities"
    if active_only:
        sql += " WHERE is_active = 1"
    with _connect() as conn:
        rows = conn.execute(sql + " ORDER BY name").fetchall()
    return [_row(r) for r in rows]
```

### Key Data Layer Patterns

- **`init_db()`** runs at the top of every public function and is guarded by `_DB_READY`, so it does its work once.
- **`_connect()`** returns a connection to the shared database. Paths come from `education_system.paths`; never hardcode them.
- Use `?` parameterized queries exclusively -- never string interpolation.
- Validate inputs at the top of each function before touching the database.
- Raise `ValidationError` with a message fit to show the user.
- Return dataclasses, so `dataclasses.asdict()` can serialise them for the API.
- Log meaningful messages at `info` (success) and `exception` (failure) levels.

---

## Step 6: Create the GUI Window

A view is a function that takes the main window as `host` and opens a `tk.Toplevel` over `host.root`.

### `interfaces/gui/academics/enrichment/activities/activities_views.py`

```python
"""Tk views for enrichment activities."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.primary.domain.academics.enrichment.activities import (
    activities as data,
)


def open_activities(host) -> None:
    win = tk.Toplevel(host.root)
    win.title("Enrichment Activities")
    win.transient(host.root)
    win.geometry("800x500")

    cols = ("id", "name", "category", "capacity")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
    for col in cols:
        tree.heading(col, text=col.title())
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    for rec in data.list_all(active_only=True):
        tree.insert("", "end", values=(
            rec.activity_id, rec.name, rec.category, rec.max_capacity,
        ))
```

### Key GUI Patterns

- All SQL and rules stay in the data layer; views only call it.
- Wrap entry points in a decorator like `_safe_view` in `clubs_views.py`, which reports `ValidationError` and logs anything unexpected.
- Open forms in their own dialog, as `_open_form_dialog()` in `clubs_views.py` does.

---

## Step 7: Create the CLI Handler

A CLI module exposes `dispatch(label)`, which runs the handler for a menu label and returns `True`, or returns `False` if the label is not its own.

### `interfaces/cli/academics/enrichment/activities/activities_cli.py`

```python
"""CLI handlers for enrichment activities."""

from __future__ import annotations

from education_system.systems.primary.domain.academics.enrichment.activities import (
    activities as data,
)


def _list() -> None:
    rows = data.list_all(active_only=True)
    if not rows:
        print("  No activities.")
        return
    for rec in rows:
        print(f"  {rec.activity_id:>4}  {rec.name}  ({rec.category})")


_DISPATCH = {
    "Enrichment Activities": _list,
}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    handler()
    return True
```

### Key CLI Patterns

- Read input through a small `_prompt()` helper that treats `EOFError` and `KeyboardInterrupt` as empty input.
- Wrap handlers in a decorator like `_safe` in `clubs_cli.py`, so `ValidationError` prints a message instead of ending the menu.

---

## Step 8: Create the API Blueprint

Routes are not in the system package. Each module gets a blueprint in `src/education_system/api/primary/routes/`.

### `src/education_system/api/primary/routes/activities_routes.py`

```python
"""REST API for Primary Enrichment Activities."""

from __future__ import annotations

import dataclasses
import functools
import os

from flask import Blueprint, g, jsonify, request

activities_bp = Blueprint("pri_activities", __name__, url_prefix="/api/activities")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _data():
    from education_system.systems.primary.domain.academics.enrichment.activities import (
        activities as data,
    )
    return data


@activities_bp.route("", methods=["GET"])
@_token_required
def list_activities():
    data = _data()
    rows = data.list_all(active_only=request.args.get("active_only") == "1")
    return jsonify({"items": [dataclasses.asdict(r) for r in rows], "count": len(rows)})


@activities_bp.route("", methods=["POST"])
@_token_required
def create_activity():
    data = _data()
    try:
        rec = data.create(request.get_json(silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(dataclasses.asdict(rec)), 201
```

The unified server rewrites the prefix, so this blueprint is served at `/api/v1/primary/activities`.

---

## Step 9: Register the Module

### 9a. Add to the GUI Sidebar

In `src/education_system/systems/primary/gui_main.py`, add a `(label, method name)` entry to the right group in `NAV_CATEGORIES`:

```python
("Academic Management", [
    ...
    ("Clubs & Activities", "open_clubs"),
    ("Enrichment Activities", "open_activities"),
]),
```

Then add the method to `PrimarySchoolMainGUI`, importing lazily to keep startup fast:

```python
def open_activities(self) -> None:
    from education_system.systems.primary.interfaces.gui.academics.enrichment.activities import (
        activities_views,
    )
    activities_views.open_activities(self)
```

### 9b. Add to the CLI Menu

In `src/education_system/systems/primary/cli_main.py`, add the label to the same group in `CATEGORIES`:

```python
("Academic Management", [
    ...
    "Clubs & Activities",
    "Enrichment Activities",
]),
```

Then, in `_submenu()`, import the handler and add it to the dispatch chain:

```python
from education_system.systems.primary.interfaces.cli.academics.enrichment.activities import activities_cli
...
or clubs_cli.dispatch(label)
or activities_cli.dispatch(label)
```

### 9c. Register the Blueprint

In `src/education_system/api/primary/routes/__init__.py`, import the blueprint and add it to `__all__` and to `ALL_BLUEPRINTS`:

```python
from education_system.api.primary.routes.activities_routes import (
    activities_bp,
)
```

The mount table in `src/education_system/platform/delivery/api/registry.py` already serves everything in `ALL_BLUEPRINTS`, so it needs no change.

---

## Step 10: Write Tests

Create `tests/unit/systems/primary/test_activities.py`. Redirect the database to a temporary file so a test can never touch `var/data/primary/primary.db`:

```python
"""Tests for the enrichment activities data layer."""

import pytest

from education_system.systems.primary.domain.academics.enrichment.activities import (
    activities as data,
)
from education_system.systems.primary.domain.learners.pupils import pupils
from education_system.systems.primary.domain.learners.pupils.pupils import ValidationError


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(pupils, "DB_PATH", tmp_path / "primary.db")
    monkeypatch.setattr(pupils, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(pupils, "_DB_READY", False)
    monkeypatch.setattr(data, "_DB_READY", False)


def test_create_activity():
    rec = data.create({"name": "Chess", "category": "Games"})
    assert rec.activity_id > 0
    assert data.get(rec.activity_id).name == "Chess"


def test_create_requires_name():
    with pytest.raises(ValidationError):
        data.create({"name": "", "category": "Games"})


def test_duplicate_name_rejected():
    data.create({"name": "Chess", "category": "Games"})
    with pytest.raises(ValidationError):
        data.create({"name": "Chess", "category": "Games"})
```

See the [Testing Guide](TESTING_GUIDE.md) for full testing patterns and conventions.

---

## Checklist

Before submitting a new module, verify:

- [ ] Domain code is under `domain/<area>/`, with screens under `interfaces/{cli,gui}/<area>/`
- [ ] The module declares `_SCHEMA` using `CREATE TABLE IF NOT EXISTS`, and creates it from `init_db()`
- [ ] Invalid input raises `ValidationError`
- [ ] All queries are parameterized
- [ ] The domain module imports no Tkinter, Flask or CLI code
- [ ] View exposes `open_<module>(host)`; CLI exposes `dispatch(label)`
- [ ] Module registered in `NAV_CATEGORIES` (`gui_main.py`) and `CATEGORIES` (`cli_main.py`)
- [ ] Blueprint added to `ALL_BLUEPRINTS` in `api/primary/routes/__init__.py`
- [ ] Tests written with a temporary database fixture
- [ ] Code formatted and linted with Ruff (`make format`, `make lint`)
- [ ] Docstrings on module and public functions
