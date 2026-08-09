# Adding New Domain Modules

Last Updated: March 2026

This guide walks through creating a new domain module for the Primary School Management System. Each module follows the same structure: a service layer for business logic, a GUI frame for the tkinter interface, and a CLI menu for terminal access.

---

## Step 1: Choose the Domain Category

Modules are grouped into seven categories under `modules/domain/`:

| Category          | Path                      | Examples                                    |
|-------------------|---------------------------|---------------------------------------------|
| `academics`       | `modules/domain/academics/`       | pupils, subjects, assessment, attendance    |
| `pastoral_care`   | `modules/domain/pastoral_care/`   | behaviour, rewards, safeguarding, send      |
| `staff`           | `modules/domain/staff/`           | hr, cpd, cover, staff_directory             |
| `admin`           | `modules/domain/admin/`           | users, settings, admissions, finance        |
| `pupil_life`      | `modules/domain/pupil_life/`      | clubs, meals, transport, trips, library     |
| `communication`   | `modules/domain/communication/`   | email, notifications, calendar              |
| `facilities`      | `modules/domain/facilities/`      | room_booking, assets, visitors, incidents   |

Place your new module in the category that best fits its domain.

---

## Step 2: Create the Directory Structure

For a module called `enrichment` in the `pupil_life` category:

```
modules/domain/pupil_life/enrichment/
├── __init__.py
├── services/
│   ├── __init__.py
│   └── enrichment_service.py
└── gui/
    ├── __init__.py
    └── enrichment_gui.py
```

Create the directories:

```bash
mkdir -p education_system/primary_school/modules/domain/pupil_life/enrichment/{services,gui}
touch education_system/primary_school/modules/domain/pupil_life/enrichment/__init__.py
touch education_system/primary_school/modules/domain/pupil_life/enrichment/services/__init__.py
touch education_system/primary_school/modules/domain/pupil_life/enrichment/gui/__init__.py
```

---

## Step 3: Define the Database Schema

Add a `CREATE TABLE IF NOT EXISTS` statement to `infrastructure/database/schema.py` in the `TABLES` dictionary:

```python
# In infrastructure/database/schema.py, add to the TABLES dict:

"enrichment_activities": """
    CREATE TABLE IF NOT EXISTS enrichment_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        day_of_week TEXT,
        time_slot TEXT,
        max_capacity INTEGER DEFAULT 30,
        year_groups TEXT,
        staff_id TEXT,
        term TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )
""",

"enrichment_enrollments": """
    CREATE TABLE IF NOT EXISTS enrichment_enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id INTEGER NOT NULL REFERENCES enrichment_activities(id),
        pupil_id TEXT NOT NULL,
        enrolled_date TEXT DEFAULT (date('now')),
        status TEXT DEFAULT 'Active',
        notes TEXT,
        UNIQUE(activity_id, pupil_id)
    )
""",
```

The `initialise_database()` function in `schema.py` iterates over `TABLES` and creates them all. No additional registration is needed for schema creation.

---

## Step 4: Add a Domain Exception

Add an exception class to `core/exceptions.py` under the appropriate section:

```python
# In core/exceptions.py, add under the "Pupil life" section:

class EnrichmentError(SchoolSystemError):
    """Error related to enrichment activity operations."""
```

All module exceptions must inherit from `SchoolSystemError`.

---

## Step 5: Create the Service Layer

The service class contains all business logic and database operations. This is the most important file in the module.

### `services/enrichment_service.py`

```python
"""Enrichment activity service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.infrastructure.validation.validators import (
    validate_non_empty,
)
from education_system.primary_school.core.exceptions import EnrichmentError

logger = logging.getLogger(__name__)


class EnrichmentService:
    """CRUD operations for enrichment activities."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        """Create a database connection using the configured path."""
        return connect(self._db_path)

    # ── Create ────────────────────────────────────────────────────────

    def create_activity(self, name, category, **kwargs):
        """Create a new enrichment activity.

        Args:
            name: Activity name (required).
            category: Activity category (required).
            **kwargs: Optional fields (description, day_of_week, etc.).

        Returns:
            The new row ID.

        Raises:
            EnrichmentError: If validation fails or DB operation errors.
        """
        name = validate_non_empty(name, "Activity name")
        category = validate_non_empty(category, "Category")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO enrichment_activities
                    (name, category, description, day_of_week, time_slot,
                     max_capacity, year_groups, staff_id, term)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    category,
                    kwargs.get("description"),
                    kwargs.get("day_of_week"),
                    kwargs.get("time_slot"),
                    kwargs.get("max_capacity", 30),
                    kwargs.get("year_groups"),
                    kwargs.get("staff_id"),
                    kwargs.get("term"),
                ),
            )
            conn.commit()
            logger.info("Created enrichment activity: %s", name)
            return cursor.lastrowid
        except Exception as e:
            logger.error("Failed to create enrichment activity: %s", e)
            raise EnrichmentError(f"Failed to create activity: {e}") from e
        finally:
            conn.close()

    # ── Read ──────────────────────────────────────────────────────────

    def list_activities(self, active_only=True):
        """Return all enrichment activities."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            if active_only:
                cursor.execute(
                    "SELECT * FROM enrichment_activities WHERE is_active = 1 "
                    "ORDER BY name"
                )
            else:
                cursor.execute(
                    "SELECT * FROM enrichment_activities ORDER BY name"
                )
            return cursor.fetchall()
        finally:
            conn.close()

    def get_activity(self, activity_id):
        """Return a single activity by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM enrichment_activities WHERE id = ?",
                (activity_id,),
            )
            return cursor.fetchone()
        finally:
            conn.close()

    # ── Update ────────────────────────────────────────────────────────

    def update_activity(self, activity_id, **kwargs):
        """Update an existing enrichment activity."""
        if not kwargs:
            return

        allowed = {
            "name", "category", "description", "day_of_week", "time_slot",
            "max_capacity", "year_groups", "staff_id", "term", "is_active",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [activity_id]

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE enrichment_activities SET {set_clause}, "
                f"updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated enrichment activity %s", activity_id)
        except Exception as e:
            logger.error("Failed to update enrichment activity: %s", e)
            raise EnrichmentError(f"Failed to update activity: {e}") from e
        finally:
            conn.close()

    # ── Delete ────────────────────────────────────────────────────────

    def delete_activity(self, activity_id):
        """Delete an enrichment activity and its enrollments."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM enrichment_enrollments WHERE activity_id = ?",
                (activity_id,),
            )
            cursor.execute(
                "DELETE FROM enrichment_activities WHERE id = ?",
                (activity_id,),
            )
            conn.commit()
            logger.info("Deleted enrichment activity %s", activity_id)
        except Exception as e:
            logger.error("Failed to delete enrichment activity: %s", e)
            raise EnrichmentError(f"Failed to delete activity: {e}") from e
        finally:
            conn.close()
```

### Key Service Patterns

- **`__init__`** accepts an optional `db_path` for testability.
- **`_conn()`** wraps `connect()` with the configured path.
- Every method opens its own connection and closes it in a `finally` block.
- Use `?` parameterized queries exclusively -- never string interpolation.
- Validate inputs at the top of each method before touching the database.
- Raise domain-specific exceptions (e.g., `EnrichmentError`), not generic ones.
- Log meaningful messages at `info` (success) and `error` (failure) levels.

---

## Step 6: Create the GUI Frame

The GUI frame is a `tk.Frame` subclass that gets loaded into the main window's content area when the user clicks the sidebar.

### `gui/enrichment_gui.py`

```python
"""Enrichment activity GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pupil_life.enrichment.services.enrichment_service import (
    EnrichmentService,
)


class _ActivityDialog(tk.Toplevel):
    """Add / Edit activity dialog."""

    def __init__(self, parent, db_path, activity=None):
        super().__init__(parent)
        self.result = None
        self._activity = activity
        self.title("Edit Activity" if activity else "Add Activity")
        self.geometry("420x350")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        fields = [
            ("name", "Name *"),
            ("category", "Category *"),
            ("description", "Description"),
            ("day_of_week", "Day of Week"),
            ("time_slot", "Time Slot"),
            ("max_capacity", "Max Capacity"),
            ("year_groups", "Year Groups"),
            ("term", "Term"),
        ]
        for key, label in fields:
            row = tk.Frame(frm)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
            entry = tk.Entry(row, width=30)
            entry.pack(side="left", fill="x", expand=True)
            self._entries[key] = entry

        # Pre-fill for edit
        if activity:
            for key, widget in self._entries.items():
                val = activity.get(key)
                if val is not None:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(
            side="left", padx=5
        )
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(
            side="right", padx=5
        )

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _save(self):
        data = {k: w.get().strip() for k, w in self._entries.items()}
        if not data.get("name"):
            messagebox.showwarning("Validation", "Name is required.", parent=self)
            return
        if not data.get("category"):
            messagebox.showwarning("Validation", "Category is required.", parent=self)
            return
        self.result = data
        self.destroy()


class EnrichmentFrame(tk.Frame):
    """Main enrichment activity management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = EnrichmentService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Enrichment Activities",
            fg="white",
            bg=self.HEADER_BG,
            font=("Helvetica", 14, "bold"),
        ).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="Add Activity", command=self._on_add).pack(
            side="left", padx=3
        )
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(
            side="left", padx=3
        )
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(
            side="left", padx=3
        )

        # Treeview
        columns = ("id", "name", "category", "day_of_week", "time_slot", "max_capacity")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse"
        )
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120)
        self._tree.column("id", width=50)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._load_data()

    def _load_data(self):
        """Refresh the Treeview with current data."""
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            for row in self._service.list_activities():
                self._tree.insert(
                    "",
                    "end",
                    iid=row["id"],
                    values=(
                        row["id"],
                        row["name"],
                        row["category"],
                        row["day_of_week"] or "",
                        row["time_slot"] or "",
                        row["max_capacity"],
                    ),
                )
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_add(self):
        dlg = _ActivityDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_activity(**dlg.result)
                self._load_data()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)

    def _on_edit(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an activity first.", parent=self)
            return
        activity = dict(self._service.get_activity(int(sel[0])))
        dlg = _ActivityDialog(self, self._db_path, activity=activity)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_activity(int(sel[0]), **dlg.result)
                self._load_data()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an activity first.", parent=self)
            return
        if messagebox.askyesno("Confirm", "Delete this activity?", parent=self):
            try:
                self._service.delete_activity(int(sel[0]))
                self._load_data()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)
```

### Key GUI Patterns

- **`__init__` signature**: `(self, parent, db_path, auth=None)` -- all frames receive these three arguments.
- Instantiate the service in `__init__` and delegate all logic to it.
- Use `_ActivityDialog(tk.Toplevel)` for add/edit forms with `grab_set()` for modality.
- `Treeview` with a vertical scrollbar for list views.
- `_load_data()` clears and repopulates the Treeview.
- Wrap service calls in `try/except` and show `messagebox.showerror()` on failure.

---

## Step 7: Create the CLI Menu

Add a file at `cli/menus/enrichment_cli.py`:

```python
"""Enrichment CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def enrichment_menu(auth):
    """Enrichment activities management menu."""
    from education_system.primary_school.cli.cli_main import (
        print_header,
        print_menu,
        get_choice,
    )
    from education_system.primary_school.modules.domain.pupil_life.enrichment.services.enrichment_service import (
        EnrichmentService,
    )

    svc = EnrichmentService(get_db_path())

    while True:
        print_header("Enrichment Activities")
        print_menu([
            ("1", "List activities"),
            ("2", "View details"),
            ("3", "Add activity"),
            ("4", "Update activity"),
            ("5", "Delete activity"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_activities()
            if not items:
                print("\n  No activities found.")
            else:
                for item in items:
                    print(f"  {dict(item)}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_activity(int(pk))
                if item:
                    for k, v in dict(item).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            name = input("  Name: ").strip()
            category = input("  Category: ").strip()
            description = input("  Description: ").strip()
            try:
                svc.create_activity(name, category, description=description)
                print("\n  Activity created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            name = input("  Name: ").strip()
            category = input("  Category: ").strip()
            try:
                svc.update_activity(int(pk), name=name, category=category)
                print("\n  Activity updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_activity(int(pk))
                print("\n  Activity deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
```

### Key CLI Patterns

- Function name follows `<module>_menu(auth)` convention.
- Import service and CLI helpers lazily inside the function to avoid circular imports.
- Use `get_db_path()` to obtain the active database path.
- Wrap all service calls in `try/except` and print errors to the console.
- Always provide a "Back" option (`"0"`) to return to the parent menu.

---

## Step 8: Register the Module

### 8a. Add to the GUI Sidebar

In `main_gui.py`, add the module to the sidebar navigation. Locate the section where sidebar buttons are created and add an entry:

```python
# In main_gui.py, in the sidebar button definitions:
("Enrichment", "pupil_life", self._show_enrichment),
```

Then add the handler method:

```python
def _show_enrichment(self):
    from education_system.primary_school.modules.domain.pupil_life.enrichment.gui.enrichment_gui import (
        EnrichmentFrame,
    )
    self._show_frame(EnrichmentFrame)
```

### 8b. Add to the CLI Menu

In `cli/cli_main.py`, add the module to the appropriate submenu. Locate the pupil life menu items and add:

```python
("enrichment", "Enrichment Activities", lambda: enrichment_menu(auth)),
```

With the import at the top of the menu function:

```python
from education_system.primary_school.cli.menus.enrichment_cli import enrichment_menu
```

### 8c. Export from `__init__.py`

In `modules/domain/pupil_life/enrichment/__init__.py`:

```python
"""Enrichment activities module."""
```

In `modules/domain/pupil_life/enrichment/services/__init__.py`:

```python
from .enrichment_service import EnrichmentService

__all__ = ["EnrichmentService"]
```

In `modules/domain/pupil_life/enrichment/gui/__init__.py`:

```python
from .enrichment_gui import EnrichmentFrame

__all__ = ["EnrichmentFrame"]
```

---

## Step 9: Write Tests

Create a test file at `tests/test_enrichment_service.py`:

```python
"""Tests for the EnrichmentService."""

import os
import sqlite3
import tempfile
import pytest

from education_system.primary_school.modules.domain.pupil_life.enrichment.services.enrichment_service import (
    EnrichmentService,
)
from education_system.primary_school.core.exceptions import EnrichmentError


@pytest.fixture
def db_path():
    """Create a temporary database with the enrichment schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE enrichment_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            day_of_week TEXT,
            time_slot TEXT,
            max_capacity INTEGER DEFAULT 30,
            year_groups TEXT,
            staff_id TEXT,
            term TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE enrichment_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL REFERENCES enrichment_activities(id),
            pupil_id TEXT NOT NULL,
            enrolled_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'Active',
            notes TEXT,
            UNIQUE(activity_id, pupil_id)
        )
    """)
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


@pytest.fixture
def service(db_path):
    """Return an EnrichmentService wired to the temp DB."""
    return EnrichmentService(db_path)


class TestEnrichmentService:

    def test_create_activity(self, service):
        row_id = service.create_activity("Chess Club", "Academic")
        assert row_id == 1

    def test_list_activities(self, service):
        service.create_activity("Chess Club", "Academic")
        service.create_activity("Football", "Sport")
        activities = service.list_activities()
        assert len(activities) == 2

    def test_get_activity(self, service):
        row_id = service.create_activity("Chess Club", "Academic", description="Weekly chess")
        activity = service.get_activity(row_id)
        assert activity["name"] == "Chess Club"
        assert activity["description"] == "Weekly chess"

    def test_update_activity(self, service):
        row_id = service.create_activity("Chess Club", "Academic")
        service.update_activity(row_id, name="Chess Society")
        activity = service.get_activity(row_id)
        assert activity["name"] == "Chess Society"

    def test_delete_activity(self, service):
        row_id = service.create_activity("Chess Club", "Academic")
        service.delete_activity(row_id)
        assert service.get_activity(row_id) is None

    def test_create_activity_empty_name_raises(self, service):
        with pytest.raises(Exception):
            service.create_activity("", "Academic")
```

See the [Testing Guide](TESTING_GUIDE.md) for full testing patterns and conventions.

---

## Checklist

Before submitting a new module, verify:

- [ ] Directory structure follows `module_name/{__init__.py, services/, gui/}` pattern
- [ ] Schema added to `infrastructure/database/schema.py` using `CREATE TABLE IF NOT EXISTS`
- [ ] Exception class added to `core/exceptions.py` inheriting from `SchoolSystemError`
- [ ] Service class uses `_conn()` / `try/finally` pattern with parameterized queries
- [ ] GUI frame inherits `tk.Frame` with `(parent, db_path, auth=None)` signature
- [ ] CLI menu follows `<module>_menu(auth)` convention
- [ ] Module registered in sidebar (`main_gui.py`) and CLI menus (`cli_main.py`)
- [ ] `__init__.py` files export key classes
- [ ] Tests written with temporary database fixture
- [ ] Code formatted with Black and linted with Ruff
- [ ] Docstrings on module, class, and public methods
