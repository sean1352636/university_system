# Module Restructuring Migration Guide

## Overview

Between versions 5.41 and 5.42, the University Management System underwent a major refactoring effort. **49 single-file modules** that had grown to between 1,000 and 4,500 lines were decomposed into package directories. Each original file was replaced by a directory containing smaller, focused modules.

**Why?** Large monolithic files were difficult to navigate, test, and maintain. Splitting them improves:

- **Readability** — each file has a single, clear responsibility
- **Code review** — changes touch smaller, focused files
- **Testing** — individual components can be tested in isolation
- **Collaboration** — fewer merge conflicts on large files

**Is anything broken?** No. Every new package includes an `__init__.py` that re-exports the same public API as the original file. Existing imports continue to work unchanged.

---

## Refactoring Patterns

Four patterns were used depending on the structure of the original module.

### Pattern 1: Functional Decomposition

Used when the original file contained **standalone functions** (no classes).

**Example:** `infrastructure/database/data_backup.py` (1,037 lines, 15 functions)

```
# Before
infrastructure/database/data_backup.py

# After
infrastructure/database/data_backup/
    __init__.py          # Re-exports all public functions
    _imports.py          # Shared imports and constants
    core.py              # Core backup/restore operations
    verification.py      # Integrity checks and verification
    scheduling.py        # Scheduled backup management
    reporting.py         # Backup status reports
```

Imports stay the same:
```python
# Both work identically
from university_system.infrastructure.database.data_backup import create_backup
```

### Pattern 2: Mixin-Based Class Splitting

Used when the original file contained a **single large class** with many methods. The class is split into mixin classes, each handling a group of related methods, then composed back together.

**Example:** `modules/domain/social_matching/services/social_matching_service.py` (1,012 lines, 1 class, 27 methods)

```
# Before
social_matching/services/social_matching_service.py  # SocialMatchingService class

# After
social_matching/services/
    constants.py                # Shared constants
    social_matching_service.py  # Main class composing all mixins
    interests.py                # InterestMixin — interest CRUD
    personality.py              # PersonalityMixin — personality profiles
    privacy.py                  # PrivacyMixin — privacy settings
    matching.py                 # MatchingMixin — compatibility scoring
    buddy_requests.py           # BuddyRequestMixin — buddy requests
    teams.py                    # TeamMixin — intramural teams
    clubs.py                    # ClubMixin — club recommendations
    activities.py               # ActivityMixin — social activities
    statistics.py               # StatisticsMixin — user analytics
```

The main class file composes all mixins:
```python
class SocialMatchingService(InterestMixin, PersonalityMixin, PrivacyMixin, ...):
    """Full service composed from focused mixins."""
    pass
```

### Pattern 3: Tab/Dialog-Based GUI Splitting

Used for **GUI modules** with multiple tabs, dialogs, or views. Each tab or dialog becomes its own file.

**Example:** `modules/domain/campus_navigation/gui/navigation_gui.py` (1,010 lines)

```
# Before
campus_navigation/gui/navigation_gui.py

# After
campus_navigation/gui/
    navigation_gui.py    # Core shell (NavigationGUI class)
    _imports.py          # Shared imports
    map_canvas.py        # Map drawing and interaction
    tabs/
        directory.py     # Building directory tab
        route.py         # Route planner tab
        nearest.py       # Find nearest tab
        favorites.py     # Favorites management tab
```

### Pattern 4: Shared Imports Extraction

A supporting pattern used alongside the others. Common imports, constants, and setup code are extracted into a `_imports.py` file that all sibling modules import from.

**Example:** `modules/domain/academics/gui/course_management_gui/core/_imports.py`

```python
# _imports.py — shared across all modules in this package
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from university_system.infrastructure.auth import UserAuth
# ... other shared imports and constants
```

---

## Complete File Mapping

All 49 refactored modules, grouped by domain area.

### Infrastructure

| Old File | New Package |
|---|---|
| `infrastructure/database/data_backup.py` | `infrastructure/database/data_backup/` |
| `infrastructure/email/admin.py` | `infrastructure/email/admin/` |
| `infrastructure/email/email_service.py` | `infrastructure/email/email_service/` |

### Academics — Services

| Old File | New Package |
|---|---|
| `modules/domain/academics/services/course_management.py` | `modules/domain/academics/services/course_management/` |
| `modules/domain/academics/services/module_scheduling.py` | `modules/domain/academics/services/module_scheduling/` |
| `modules/domain/academics/services/parent_portal.py` | `modules/domain/academics/services/parent_portal/` |
| `modules/domain/academics/grading/grade_calculation.py` | `modules/domain/academics/grading/grade_calculation/` |
| `modules/domain/academics/grading/learning_outcomes.py` | `modules/domain/academics/grading/learning_outcomes/` |

### Academics — GUI

| Old File | New Package |
|---|---|
| `modules/domain/academics/gui/exam_scheduler.py` | `modules/domain/academics/gui/exam_scheduler/` |
| `modules/domain/academics/gui/grade_tracking_management_gui.py` | `modules/domain/academics/gui/grade_tracking_management_gui/` |
| `modules/domain/academics/gui/grade_tracking/analytics_manager.py` | `modules/domain/academics/gui/grade_tracking/analytics_manager/` |
| `modules/domain/academics/gui/assignment_system/assignment_manager.py` | `modules/domain/academics/gui/assignment_system/assignment_manager/` |
| `modules/domain/academics/gui/assignment_system/group_manager.py` | `modules/domain/academics/gui/assignment_system/group_manager/` |
| `modules/domain/academics/gui/library/fines.py` | `modules/domain/academics/gui/library/fines/` |

### Finance

| Old File | New Package |
|---|---|
| `modules/domain/finance/gui/finance/budget_manager.py` | `modules/domain/finance/gui/finance/budget_manager/` |
| `modules/domain/finance/gui/finance/expense_manager.py` | `modules/domain/finance/gui/finance/expense_manager/` |
| `modules/domain/finance/gui/finance/settings.py` | `modules/domain/finance/gui/finance/settings/` |
| `modules/domain/finance/gui/finance/transaction_manager.py` | `modules/domain/finance/gui/finance/transaction_manager/` |
| `modules/domain/finance/gui/finance_reporting/archive_backup.py` | `modules/domain/finance/gui/finance_reporting/archive_backup/` |
| `modules/domain/finance/gui/financial_aid/admin_portal.py` | `modules/domain/finance/gui/financial_aid/admin_portal/` |
| `modules/domain/finance/gui/financial_aid/student_portal.py` | `modules/domain/finance/gui/financial_aid/student_portal/` |
| `modules/domain/finance/reporting/financial_reports.py` | `modules/domain/finance/reporting/financial_reports/` |
| `modules/domain/finance/reporting/revenue_analytics.py` | `modules/domain/finance/reporting/revenue_analytics/` |

### Health

| Old File | New Package |
|---|---|
| `modules/domain/health/records/medical_records.py` | `modules/domain/health/records/medical_records/` → split into `admin/`, `analytics/`, `clinical/`, `db/`, `records/`, `referrals/`, `screening/`, `student/`, `vaccinations/`, `wellness/` |

### Housing

| Old File | New Package |
|---|---|
| `modules/domain/housing/services/accommodation.py` | `modules/domain/housing/services/accommodation/` |
| `modules/domain/housing/services/housing_accommodation.py` | `modules/domain/housing/services/housing_accommodation/` |

### Mobility

| Old File | New Package |
|---|---|
| `modules/domain/mobility/gui/trip_management_gui.py` | `modules/domain/mobility/gui/trip_management_gui/` |
| `modules/domain/mobility/services/parking_management.py` | `modules/domain/mobility/services/parking_management/` |
| `modules/domain/mobility/services/trip_management.py` | `modules/domain/mobility/services/trip_management/` |

### Student Affairs

| Old File | New Package |
|---|---|
| `modules/domain/student_affairs/services/alumni_management.py` | `modules/domain/student_affairs/services/alumni_management/` |
| `modules/domain/student_affairs/services/helpdesk.py` | `modules/domain/student_affairs/services/helpdesk/` |
| `modules/domain/student_affairs/student_union/clubs/club_management.py` | `modules/domain/student_affairs/student_union/clubs/club_management/` |

### Commerce

| Old File | New Package |
|---|---|
| `modules/domain/commerce/services/shop_management.py` | `modules/domain/commerce/services/shop_management/` |

### Shared Modules

| Old File | New Package |
|---|---|
| `modules/shared/gui/simple_activity_logger_gui.py` | `modules/shared/gui/simple_activity_logger_gui/` |
| `modules/shared/gui/student_analytics_gui.py` | `modules/shared/gui/student_analytics_gui/` |
| `modules/shared/services/analytics/advanced_search.py` | `modules/shared/services/analytics/advanced_search/` |
| `modules/shared/services/analytics/enhanced_reporting.py` | `modules/shared/services/analytics/enhanced_reporting/` |
| `modules/shared/services/analytics/student_analytics.py` | `modules/shared/services/analytics/student_analytics/` |
| `modules/shared/services/integrations/integration_marketplace_core.py` | `modules/shared/services/integrations/integration_marketplace_core/` |
| `modules/shared/utils/batch_operations.py` | `modules/shared/utils/batch_operations/` |
| `modules/shared/utils/document_manager.py` | `modules/shared/utils/document_manager/` |
| `modules/shared/utils/simple_activity_logger.py` | `modules/shared/utils/simple_activity_logger/` |

### Services (CLI/GUI)

| Old File | New Package |
|---|---|
| `modules/services/cli/betting_shop_cli.py` | `modules/services/cli/betting_shop_cli/` |
| `modules/services/cli/charity_shop_cli.py` | `modules/services/cli/charity_shop_cli/` |
| `modules/services/cli/cinema_cli.py` | `modules/services/cli/cinema_cli/` |
| `modules/services/gui/charity_shop_gui.py` | `modules/services/gui/charity_shop_gui/` |
| `modules/services/gui/integration_marketplace_gui.py` | `modules/services/gui/integration_marketplace_gui/` |

### Utils

| Old File | New Package |
|---|---|
| `utils/ai/university_chatbot.py` | `utils/ai/university_chatbot/` |
| `utils/logging/log_management.py` | `utils/logging/log_management/` |

---

## Import Migration

All new packages include `__init__.py` files that re-export the same public API. **Existing imports work without changes.** However, for new code you may prefer importing from the specific submodule for clarity.

### Example: Data Backup

```python
# Original import (still works)
from university_system.infrastructure.database.data_backup import create_backup, restore_backup

# New direct import (optional, for clarity)
from university_system.infrastructure.database.data_backup.core import create_backup, restore_backup
```

### Example: Social Matching Service

```python
# Original import (still works)
from university_system.modules.domain.social_matching.services.social_matching_service import SocialMatchingService

# New direct import (optional, for clarity)
from university_system.modules.domain.social_matching.services.matching import MatchingMixin
```

### Example: Course Management

```python
# Original import (still works)
from university_system.modules.domain.academics.services.course_management import CourseManagementService

# The __init__.py re-exports everything from the subpackage
```

---

## Backward Compatibility

- Every new package has an `__init__.py` that re-exports all public names from the original module
- **No breaking changes** — all existing import paths continue to resolve
- Test files that imported from the old paths will continue to work via the re-exports
- The only visible change is that `inspect.getfile()` and similar introspection will report the submodule file rather than the original monolith

---

## FAQ

**Q: Do I need to update my imports?**
A: No. Existing imports work unchanged thanks to `__init__.py` re-exports.

**Q: Which pattern should I use for new modules?**
A: If your file exceeds ~800 lines, consider splitting it. Use functional decomposition for utility modules, mixin-based splitting for large classes, and tab/dialog-based splitting for GUI modules.

**Q: How do I find where code moved to?**
A: Check the mapping table above, or look at the `__init__.py` in the new package — it lists all re-exported names and their source modules.
