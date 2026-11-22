# University System -- Adding a New Domain Module

This guide walks through every step required to add a new domain module to the University Management System.

---

## Module Structure

Every domain module lives in one of the 18 slices under `src/education_system/systems/university/domains/` (for example `domains/library/`), and follows this directory layout:

```
domains/<slice>/
    __init__.py
    domain/
        __init__.py
        my_module/
            __init__.py
            my_module_service.py
    interfaces/
        __init__.py
        gui/
            __init__.py
            my_module/
                __init__.py
                my_module_gui.py
        cli/
            __init__.py
            my_module/
                __init__.py
                my_module_cli.py
```

HTTP routes do not live in the slice. They go in `src/education_system/api/university/<area>/`.

Not every module needs every interface (gui, cli, API), but the **service in `domain/` is mandatory** -- it is the single source of business logic that the API, GUI, and CLI all depend on.

---

## Step 1: Create the Service

The service layer handles all business logic and database operations. Follow the standard pattern:

```python
"""My Module service."""

import logging
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text

logger = logging.getLogger(__name__)


class MyModuleService:
    """Service for managing my module resources."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return get_connection(self._db_path)

    def create_item(self, name: str, **kwargs) -> dict:
        """Create a new item."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO my_items (name) VALUES (?)",
                (name,),
            )
            conn.commit()
            item_id = cursor.lastrowid
            logger.info("Created item %d: %s", item_id, name)
            return self.get_item(item_id)
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_item(self, item_id: int) -> dict | None:
        """Get an item by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM my_items WHERE id = ?", (item_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_items(self, page: int = 1, per_page: int = 25) -> dict:
        """List items with pagination."""
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM my_items").fetchone()[0]
            offset = (page - 1) * per_page
            rows = conn.execute(
                "SELECT * FROM my_items ORDER BY id DESC LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
            return {
                "items": [dict(r) for r in rows],
                "total": total,
                "page": page,
                "per_page": per_page,
            }
        finally:
            conn.close()
```

---

## Step 2: Add the Database Table

Add your table with an Alembic migration in `src/education_system/migrations/versions/`. There is a single chain with exactly one head, so `down_revision` must point at the current head:

```python
"""Add my_module tables."""
from alembic import op

revision = "<new revision id>"
down_revision = "<current head>"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS my_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS my_items")
```

The launcher applies pending migrations at startup. Schema helpers shared by the code are in `src/education_system/systems/university/infrastructure/database/schemas/`.

---

## Step 3: Create the GUI (Optional)

GUI modules inherit from tkinter Frame, live in `domains/<slice>/interfaces/gui/`, and are registered in the main application:

```python
"""My Module GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.i18n import get_text


class MyModuleFrame(tk.Frame):
    """GUI frame for managing my module."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._build_ui()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="My Module",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Content area
        content = tk.Frame(self, bg="#ecf0f1")
        content.pack(fill="both", expand=True, padx=20, pady=10)

        # Add your widgets here

    def refresh(self):
        """Called when the frame is shown. Reload data here."""
        pass
```

---

## Step 4: Create the CLI (Optional)

CLI modules provide text-based menus and live in `domains/<slice>/interfaces/cli/`:

```python
"""My Module CLI commands."""

from education_system.systems.university.domains.<slice>.domain.my_module.my_module_service import MyModuleService


def my_module_menu(auth):
    """My Module management menu."""
    svc = MyModuleService()

    while True:
        print("\n=== My Module ===")
        print("[1] List items")
        print("[2] Create item")
        print("[0] Back")

        choice = input("Select: ").strip()
        if choice == "0":
            break
        elif choice == "1":
            result = svc.list_items()
            for item in result["items"]:
                print(f"  {item['id']}: {item['name']}")
        elif choice == "2":
            name = input("Name: ").strip()
            if name:
                svc.create_item(name)
                print("  Created.")
```

---

## Step 5: Add i18n Translations

Add translation keys to `var/data/university/locales/en/system/my_module.json` (and other languages):

```json
{
    "my_module": {
        "title": "My Module",
        "create_success": "Item created successfully",
        "delete_confirm": "Are you sure you want to delete this item?"
    }
}
```

---

## Step 6: Register the Module

1. **GUI**: Add the window to the main application in `src/education_system/systems/university/shell/gui/main/main_gui.py`
2. **CLI**: Add a menu entry in `src/education_system/systems/university/shell/cli/menus/main.py`
3. **API**: Create a blueprint in `src/education_system/api/university/<area>/` and add it to that package's `DOMAIN_BLUEPRINTS`; `src/education_system/platform/delivery/api/registry.py` mounts it under `/api/v1/university/`

The shell composes the domains, so these imports run from `shell/` to the slice. A domain must never import the shell.

---

## Checklist

- [ ] Service class with `_conn()` pattern and try/except/finally
- [ ] Database table(s) in an Alembic migration
- [ ] GUI frame with `refresh()` method (if GUI needed)
- [ ] CLI menu function (if CLI needed)
- [ ] API routes with JWT auth (if API needed)
- [ ] i18n translation keys
- [ ] Tests in `tests/unit/systems/university/domains/<slice>/`
- [ ] Registered in main application (GUI frame map, CLI menu, API server)
