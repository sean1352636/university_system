# College System -- Adding a New Domain Module

This guide walks through every step required to add a new domain module to the Sixth Form College Management System, using a hypothetical "awards" module as the running example.

---

## Module Structure

The sixth form system lives under `src/education_system/systems/sixth_form/`, with HTTP routes kept apart in `src/education_system/api/sixth_form/`. A module's rules and its screens sit in parallel trees:

```
systems/sixth_form/
    domain/pastoral/awards/
        __init__.py
        awards.py                # Data layer: schema, dataclasses, validation, queries
    interfaces/
        cli/pastoral/awards/
            __init__.py
            awards_cli.py        # run() and dispatch(label)
        gui/pastoral/awards/
            __init__.py
            awards_views.py      # open_awards_window(parent)
```

Choose the area that fits: `domain/` holds `academics`, `admissions`, `assessment`, `governance`, `learners`, `operations`, `pastoral`, `progression`, `safeguarding` and `staff`. Finance, communications and operations work that has moved to vertical slices goes in `domains/{finance,communications,operations}/domain/<module>/`, with its screens in that slice's `interfaces/{cli,gui}/`.

Not every module needs all three interfaces (domain, gui, cli), but the domain layer is mandatory -- it is the single source of business logic that the API, GUI, and CLI all depend on. Domain code may not import `tkinter`, Flask or the `sqlite3` driver; `tools/check_layout.py` enforces this.


## Step 1: Add a Database Path

Every sixth form module shares one database, `var/data/sixth_form/sixthform.db`. Add a named constant for the module to `src/education_system/paths.py`, and list it in `__all__` in the same file:

```python
SIXTH_FORM_AWARDS_DB: Path = SIXTH_FORM_STUDENTS_DB
```


## Step 2: Create the Data Layer

There is no central schema file, service class or shared exception hierarchy. Each module owns its `_SCHEMA`, creates it lazily in `init_db()`, returns dataclasses from module-level functions, and defines its own `ValidationError`.

Create `domain/pastoral/awards/awards.py`:

```python
"""Student awards data layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.learners.students import (
    students as _students,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_AWARDS_DB

CATEGORIES: tuple[str, ...] = ("Academic", "Enrichment", "Attendance", "Other")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS awards (
    award_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT,
    category     TEXT NOT NULL DEFAULT 'Academic',
    awarded_on   TEXT DEFAULT (date('now')),
    awarded_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_awards_student ON awards(student_id);
"""


class ValidationError(ValueError):
    """Bad input to an awards operation."""


@dataclass
class Award:
    award_id: int
    student_id: str
    title: str
    description: str | None
    category: str
    awarded_on: str | None
    awarded_by: str | None
    created_at: str | None = None


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _students.init_db()                # The table this one references
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _row(r: _sql.Row) -> Award:
    return Award(**{k: r[k] for k in r.keys()})


def create_award(payload: dict[str, Any]) -> Award:
    init_db()
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    category = payload.get("category") or "Academic"
    if category not in CATEGORIES:
        raise ValidationError(f"Unknown category: {category}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO awards (student_id, title, description, category, awarded_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (payload.get("student_id"), title, payload.get("description"),
                 category, payload.get("awarded_by")),
            )
            award_id = cur.lastrowid
    except _sql.IntegrityError as e:
        raise ValidationError(f"Could not save award: {e}") from e
    logger.info("Award %s created", award_id)
    return get_award(award_id)


def get_award(award_id: int) -> Award | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM awards WHERE award_id = ?", (award_id,)).fetchone()
    return _row(r) if r else None


def list_awards(*, student_id: str | None = None) -> list[Award]:
    init_db()
    sql = "SELECT * FROM awards"
    params: tuple = ()
    if student_id:
        sql += " WHERE student_id = ?"
        params = (student_id,)
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql + " ORDER BY awarded_on DESC", params)]


def delete_award(award_id: int) -> bool:
    init_db()
    with _connect() as conn:
        return conn.execute("DELETE FROM awards WHERE award_id = ?", (award_id,)).rowcount > 0
```

Key patterns to follow:

- `DB_PATH` is a module attribute, so tests can redirect it with `monkeypatch`.
- `init_db()` is idempotent and is called at the top of every public function. It first initialises any module whose tables it references, because foreign keys are enforced.
- `with _connect() as conn:` commits on success and rolls back on an exception.
- Always use `?` placeholders.
- Use logging for significant operations.

`src/education_system/systems/sixth_form/domain/academics/enrichment/enrichment.py` is a complete real example.


## Step 3: Add API Routes

Route modules live at `src/education_system/api/sixth_form/routes/`, and related resources share a module. To add a whole new module, create `api/sixth_form/routes/awards_routes.py`:

```python
"""REST API for sixth form awards."""

from __future__ import annotations

import dataclasses
import functools
import os

from flask import Blueprint, g, jsonify, request

from education_system.api.sixth_form import access_gate

awards_bp = Blueprint("sf_awards", __name__, url_prefix="/api/awards")


def _token_required(view):
    view = access_gate.gate(view)
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _data():
    from education_system.systems.sixth_form.domain.pastoral.awards import awards
    return awards


@awards_bp.route("", methods=["GET"])
@_token_required
def list_awards_route():
    rows = _data().list_awards(student_id=request.args.get("student_id"))
    return jsonify({"awards": [dataclasses.asdict(r) for r in rows], "count": len(rows)})


@awards_bp.route("", methods=["POST"])
@_token_required
def create_award_route():
    data = _data()
    try:
        award = data.create_award(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(dataclasses.asdict(award)), 201


@awards_bp.route("/<int:award_id>", methods=["DELETE"])
@_token_required
def delete_award_route(award_id: int):
    if not _data().delete_award(award_id):
        return jsonify({"error": f"No award with id {award_id}"}), 404
    return jsonify({"deleted": award_id})
```

Key patterns:

- The Blueprint keeps the `/api/<resource>` prefix. The unified server rewrites it on mounting, so these routes are served at `/api/v1/sixthform/awards`.
- Wrap every view in the module's `_token_required`, which runs the JWT check and then `access_gate.gate`.
- Import the domain module inside the view, so importing the routes stays cheap.
- Map `ValidationError` to 400 in the view, and a missing record to 404.
- Return `201` for POST create, `200` for everything else.


## Step 4: Register the Blueprint and Its Access Rule

Edit `src/education_system/api/sixth_form/routes/__init__.py` to import `awards_bp`, then add it to `__all__` and to `ALL_BLUEPRINTS`. The server mounts that tuple, so no other server change is needed.

Then give the routes a rule in `RULES` in `src/education_system/api/sixth_form/access_gate.py`, keyed by the route module's short name. **A route without a rule is refused.**

```python
"awards_routes": (
    Rule(r"", A.PASTORAL, A.PASTORAL),
),
```


## Step 5: Add a Test Fixture

Add a fixture beside your tests, either in a `conftest.py` or in the test file. It points the module at a temporary database:

```python
@pytest.fixture
def awards_data(tmp_path, monkeypatch):
    """The awards data layer, on a temporary database."""
    from education_system.systems.sixth_form.domain.learners.students import students
    from education_system.systems.sixth_form.domain.pastoral.awards import awards

    db = str(tmp_path / "sixthform.db")
    for module in (students, awards):
        monkeypatch.setattr(module, "DB_PATH", db)
        monkeypatch.setattr(module, "_DB_READY", False)
    awards.init_db()
    return awards
```

Redirect every module whose tables `init_db()` creates, or the test will write to the live database.


## Step 6: Write Tests

Create `tests/unit/systems/sixth_form/domain/pastoral/awards/test_awards.py`:

```python
"""Tests for the awards data layer."""

import pytest


def test_create_award_requires_title(awards_data):
    with pytest.raises(awards_data.ValidationError):
        awards_data.create_award({"student_id": "C1000001", "title": ""})


def test_unknown_category_refused(awards_data):
    with pytest.raises(awards_data.ValidationError):
        awards_data.create_award(
            {"student_id": "C1000001", "title": "A", "category": "Nope"})


def test_get_award_not_found(awards_data):
    assert awards_data.get_award(9999) is None


def test_delete_missing_award(awards_data):
    assert awards_data.delete_award(9999) is False
```


## Step 7: Add GUI and CLI (Optional)

### GUI Window

Create `interfaces/gui/pastoral/awards/awards_views.py`. A sixth form window is a `Toplevel` holding a `SidebarBook`. Import dialogs from `parented_dialogs`, never directly from `tkinter`:

```python
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.pastoral.awards import awards as data
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook


def open_awards_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title("Awards")

    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    # Build your treeview, forms, buttons, etc.
```

Then wire it into `interfaces/gui/gui_main.py`: add `("Awards", "open_awards")` to the right group in `NAV_CATEGORIES`, and add the method to `SixthFormMainGUI`:

```python
def open_awards(self) -> None:
    from education_system.systems.sixth_form.interfaces.gui.pastoral.awards import awards_views
    awards_views.open_awards_window(self)
```

### CLI Handler

Create `interfaces/cli/pastoral/awards/awards_cli.py` with a `run()` menu and a `dispatch(label)`:

```python
from education_system.systems.sixth_form.domain.pastoral.awards import awards as data


def run() -> None:
    """Awards management CLI menu."""
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


def dispatch(label: str) -> bool:
    if label != "Awards":
        return False
    run()
    return True
```

Then wire it into `interfaces/cli/cli_main.py`: add `"Awards"` to the right category's list of labels, and add this entry to `_DISPATCHERS`:

```python
("education_system.systems.sixth_form.interfaces.cli.pastoral.awards", "awards_cli"),
```

### Menu Access

Add the label to `MENU_CAPABILITIES` in `domain/governance/user_management/access.py`. A label missing from that map is admin-only:

```python
"Awards": PASTORAL,
```


## Checklist

When adding a new module, verify the following:

- [ ] `SIXTH_FORM_<NAME>_DB` added to `src/education_system/paths.py` and its `__all__`
- [ ] `__init__.py` files created in `domain/<area>/<name>/` and `interfaces/{cli,gui}/<area>/<name>/`
- [ ] Data layer created with `_SCHEMA`, `init_db()`, `_connect()` and `ValidationError`
- [ ] API route blueprint created in `api/sixth_form/routes/`
- [ ] Blueprint added to `ALL_BLUEPRINTS` in `api/sixth_form/routes/__init__.py`
- [ ] Rule added to `RULES` in `api/sixth_form/access_gate.py`
- [ ] Menu label added to `MENU_CAPABILITIES` in `domain/governance/user_management/access.py`
- [ ] GUI wired into `gui_main.py` and CLI wired into `cli_main.py`
- [ ] Test fixture redirects `DB_PATH` for every module involved
- [ ] Test file created with CRUD tests and error-path tests
- [ ] Tests pass: `python -m pytest tests/unit/systems/sixth_form/domain/pastoral/awards/ -v`
