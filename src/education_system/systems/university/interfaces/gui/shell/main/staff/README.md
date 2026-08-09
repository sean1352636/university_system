# Staff CRUD Module

## Overview

This module provides comprehensive CRUD (Create, Read, Update, Delete) operations for staff user accounts in the University Management System.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Main GUI (main_gui.py)                     │
│  - Imports staff CRUD functions                         │
│  - Binds methods to UnifiedManagementGUI class          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│         Navigation (gui_setup.py)                       │
│  - Human Resources category                             │
│  - Role-based button visibility                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│       Staff CRUD GUI (staff_crud_gui.py)                │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  create_staff_dialog()                            │  │
│  │  - Form validation                                │  │
│  │  - Password hashing                               │  │
│  │  - Duplicate detection                            │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  view_staff()                                     │  │
│  │  - Tree view with all staff                       │  │
│  │  - Search functionality                           │  │
│  │  - Context menu actions                           │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  update_staff_dialog()                            │  │
│  │  - Edit personal info                             │  │
│  │  - Change role/status                             │  │
│  │  - Optional password reset                        │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  delete_staff_dialog() [Admin Only]               │  │
│  │  - Search and select                              │  │
│  │  - Confirmation warnings                          │  │
│  │  - Activity logging                               │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  search_staff_dialog()                            │  │
│  │  - Advanced search filters                        │  │
│  │  - Multiple search types                          │  │
│  │  - Results tree view                              │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│         Database Layer (db.py)                          │
│  - get_connection(): Read operations                    │
│  - transaction(): Write operations (ACID)               │
│  - Connection pooling                                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│    Users Table (student_records.db)                     │
│  - user_id (PK)                                         │
│  - username (UNIQUE)                                    │
│  - password_hash (PBKDF2)                               │
│  - email, first_name, last_name                         │
│  - role (staff/instructor/admin)                        │
│  - is_active, created_at, updated_at                    │
└─────────────────────────────────────────────────────────┘
```

## Module Files

- **staff_crud_gui.py** - Main implementation (~900 lines)
- **__init__.py** - Module exports
- **README.md** - This file

## Functions Exported

```python
from university_system.modules.shared.gui.main.staff import (
    create_staff_dialog,    # Create new staff member
    update_staff_dialog,    # Update existing staff
    view_staff,             # View all staff in tree
    delete_staff_dialog,    # Delete staff (admin)
    search_staff_dialog     # Advanced search
)
```

## Integration Pattern

The module follows the same pattern as the student CRUD system:

1. **Import**: Functions imported in `main_gui.py`
2. **Bind**: Methods bound to `UnifiedManagementGUI` class
3. **Navigate**: Accessible via navigation panel
4. **Permission**: Role-based access control
5. **Database**: Uses transaction context managers
6. **Logging**: All operations logged for audit

## Database Schema

Staff accounts use the existing `users` table:

```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    first_name TEXT,
    last_name TEXT,
    role TEXT DEFAULT 'student',
    student_id TEXT,
    is_active BOOLEAN DEFAULT 1,
    last_login TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students (student_id)
)
```

## Security Features

1. **Password Hashing**: PBKDF2 with 1,000,000 iterations
2. **Validation**: Email format, duplicate detection, required fields
3. **Access Control**: Role-based permissions (staff vs admin)
4. **Audit Trail**: Activity logging for all operations
5. **Transaction Safety**: ACID compliance with context managers

## Usage Example

```python
# Access through GUI
# 1. Log in as Staff or Admin
# 2. Navigate to: Human Resources ▶
# 3. Select: Create New Staff
# 4. Fill in the form and submit

# Programmatic usage (if needed)
from university_system.modules.shared.gui.main import UnifiedManagementGUI

# Create GUI instance
app = UnifiedManagementGUI(auth_manager)

# Create staff dialog
app.create_staff_dialog()

# View all staff
app.view_staff()

# Search staff
app.search_staff_dialog()
```

## Permissions Matrix

| Operation          | Student | Instructor | Staff | Admin |
|-------------------|---------|------------|-------|-------|
| View Staff        | ❌      | ❌         | ✅    | ✅    |
| Create Staff      | ❌      | ❌         | ✅    | ✅    |
| Search Staff      | ❌      | ❌         | ✅    | ✅    |
| Update Staff      | ❌      | ❌         | ✅    | ✅    |
| Delete Staff      | ❌      | ❌         | ❌    | ✅    |

## Error Handling

All functions include comprehensive error handling:

- Database connection errors
- Validation errors
- Duplicate detection
- Transaction rollback on failure
- User-friendly error messages
- Exception logging

## Testing

Test the module with:

```bash
# Run GUI
python run.py --gui

# Login as staff/admin
# Navigate to Human Resources
# Test each CRUD operation
```

## Future Enhancements

- [ ] Bulk staff import from CSV
- [ ] Export staff list
- [ ] Advanced filtering options
- [ ] Email verification
- [ ] Department assignment
- [ ] Custom permissions

## Support

For detailed documentation, see: `/university_system/STAFF_CRUD_GUIDE.md`

---

**Module Version**: 1.0.0
**Created**: 2026-01-27
**Status**: ✅ Production Ready
