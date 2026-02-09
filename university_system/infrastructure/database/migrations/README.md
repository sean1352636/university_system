# Database Migrations

This directory contains database migration scripts for updating the schema and data of existing University Management System installations.

## Running Migrations

To run a migration script, use the following command from the project root:

```bash
PYTHONPATH=/path/to/project python3 university_system/infrastructure/database/migrations/<migration_script>.py
```

Or if running from the project root:

```bash
PYTHONPATH=. python3 university_system/infrastructure/database/migrations/<migration_script>.py
```

## Available Migrations

### add_student_modules_columns.py

**Purpose**: Add missing columns to the `student_modules` table

**Adds the following columns:**
- `module_type` - Type of module (Standard, Elective, etc.)
- `module_name` - Name of the module
- `grade` - Student's grade in the module
- `completion_date` - Date when the module was completed
- `status` - Enrollment status (Enrolled, Completed, Withdrawn, etc.)

**When to run:**
- When you encounter "no such column: module_type" errors
- After updating from v4.x to v5.0
- When setting up an existing database with the new schema

**Usage:**
```bash
PYTHONPATH=. python3 university_system/infrastructure/database/migrations/add_student_modules_columns.py
```

The script will:
1. Check which columns already exist
2. Add only the missing columns
3. Populate `module_type` and `module_name` from the `modules` table
4. Display a summary of changes made

**Safety**: This migration is idempotent - it can be run multiple times safely. It will only add columns that don't already exist.

## Creating New Migrations

When creating a new migration:

1. Create a new Python file with a descriptive name (e.g., `add_feature_columns.py`)
2. Include a docstring explaining what the migration does
3. Make the migration idempotent (safe to run multiple times)
4. Test the migration on a backup database first
5. Update this README with details about the new migration

### Migration Template

```python
#!/usr/bin/env python3
"""
Migration: Brief description

Detailed explanation of what this migration does and why.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from university_system.modules.shared.constants import paths


def run_migration():
    """Run the migration"""
    try:
        conn = sqlite3.connect(paths.DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Migration logic here

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
```

## Best Practices

1. **Always backup** your database before running migrations
2. **Test migrations** on a copy of production data first
3. **Make migrations idempotent** - they should be safe to run multiple times
4. **Document changes** - Update this README and the CHANGELOG.md
5. **Handle errors gracefully** - Use try/except and rollback on failure
6. **Verify schema** - Check table structure before and after migration
7. **Populate data** - When adding columns, populate them from existing data if possible

## Troubleshooting

### Module Not Found Error

If you see `ModuleNotFoundError: No module named 'university_system'`, make sure to set PYTHONPATH:

```bash
PYTHONPATH=/path/to/project python3 migrations/script.py
```

### Permission Denied

If you encounter permission errors accessing the database:

```bash
chmod 644 university_system/data/db_files/student_records.db
```

### Database Locked

If the database is locked, make sure no other processes are using it:

```bash
# Check for processes using the database
lsof university_system/data/db_files/student_records.db

# Or force close all connections
pkill -f student_records.db
```

## Migration History

| Date | Migration | Description | Version |
|------|-----------|-------------|---------|
| 2025-11-05 | add_student_modules_columns.py | Add missing columns to student_modules | 5.0.1 |

---

For more information, see the main project documentation in `CLAUDE.md`.
