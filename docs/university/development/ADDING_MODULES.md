# University System -- Adding a New Domain Module

This guide walks through every step required to add a new domain module to the University Management System.

---

## Module Structure

Every domain module lives under `education_system/university_system/modules/domain/` and follows this directory layout:

```
modules/domain/my_module/
    __init__.py
    services/
        __init__.py
        my_module_service.py
    gui/
        __init__.py
        my_module_gui.py
    cli/
        __init__.py
        my_module_cli.py
```

Not every module needs all three interfaces (services, gui, cli), but the **services layer is mandatory** -- it is the single source of business logic that the API, GUI, and CLI all depend on.

---

## Step 1: Create the Service

The service layer handles all business logic and database operations. Follow the standard pattern:

```python
"""My Module service."""

import logging
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.core.i18n import get_text

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

Add your table to the schema. The university system uses migration files in `infrastructure/database/migrations/`:

```python
"""Migration: add my_module tables."""

def upgrade(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS my_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
```

Or add the table directly to the appropriate schema file in `infrastructure/database/schemas/`.

---

## Step 3: Create the GUI (Optional)

GUI modules inherit from tkinter Frame and are registered in the main application:

```python
"""My Module GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.core.i18n import get_text


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

CLI modules provide text-based menus:

```python
"""My Module CLI commands."""

from education_system.university_system.modules.domain.my_module.services.my_module_service import MyModuleService


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

Add translation keys to `data/locales/en/system/my_module.json` (and other languages):

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

1. **GUI**: Add the frame class to the main application's frame map
2. **CLI**: Add a menu entry in `infrastructure/auth/cli/cli_menus.py`
3. **API**: Create a blueprint in `shared/api/university/routes/` and register it in the API server

---

## Checklist

- [ ] Service class with `_conn()` pattern and try/except/finally
- [ ] Database table(s) in schema or migration
- [ ] GUI frame with `refresh()` method (if GUI needed)
- [ ] CLI menu function (if CLI needed)
- [ ] API routes with JWT auth (if API needed)
- [ ] i18n translation keys
- [ ] Tests in `tests/`
- [ ] Registered in main application (GUI frame map, CLI menu, API server)
