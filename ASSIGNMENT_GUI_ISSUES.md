# Assignment GUI - Remaining Issues

This document tracks all reported issues in the Assignment GUI that need to be fixed.

## Status Legend
- ✅ **FIXED** - Issue resolved and committed
- 🔧 **IN PROGRESS** - Currently being worked on
- ⏳ **PENDING** - Not yet started
- 📋 **DOCUMENTED** - Issue confirmed and documented

---

## ✅ FIXED ISSUES

### 1. File Path Errors (NoneType)
**Status**: FIXED ✅
**Commit**: 6afc18f
**Description**: Fixed "expected str, bytes or os.PathLike object, not NoneType" errors in:
- ✅ maintenance.py - archive_old_files()
- ✅ maintenance.py - cleanup_old_data()
- ✅ submission_manager.py - submit_assignment_gui()

**Solution**: Added proper fallback paths using `paths.UPLOAD_DIR` and `paths.DATA_DIR` when `assignment_system.submission_dir` is None.

---

## ⏳ PENDING ISSUES

### 2. Notifications - Missing created_at Column
**Status**: PENDING ⏳
**File**: `db_manager.py`, `notifications.py`
**Error**: "Skipped notifications cleanup: missing created_at column"

**Issue**:
- The notifications table is missing the `created_at` column
- This prevents proper cleanup of old notifications
- Notification queries may be using outdated schema

**Solution Required**:
- Add migration to add `created_at` column to notifications table
- Update all notification INSERT queries to include created_at
- Ensure default value is set for existing records

**Code Location**:
```python
# maintenance.py:446 - Cleanup tries to use created_at
cursor.execute('DELETE FROM notifications WHERE created_at < ? AND is_read = 1', (cutoff_date,))
```

---

### 3. Notifications - "no such column: id" Error
**Status**: PENDING ⏳
**File**: `notifications.py`
**Error**: "Failed to load notifications no such column id"

**Issue**:
- Notification queries are referencing 'id' column that may not exist
- Possible table schema mismatch

**Solution Required**:
- Check notifications table schema
- Update queries to use correct primary key column name
- Add migration if needed

**Code Location**:
```python
# notifications.py:268 - Query using id column
SELECT * FROM notifications WHERE id = ?
```

---

### 4. Submit Assignments - No Assignments Showing
**Status**: PENDING ⏳
**File**: `submission_manager.py`
**Error**: "No assignments coming up when you select the assignments box"

**Issue**:
- Assignment dropdown is empty when student tries to submit
- Possible causes:
  1. Student not enrolled in any modules
  2. No active assignments in student's modules
  3. Query filtering incorrectly
  4. Data not properly loaded

**Solution Required**:
- Add debug logging to `load_available_assignments()`
- Check if query returns results
- Add user feedback if no assignments available
- Verify student_modules table has data

**Code Location**:
```python
# submission_manager.py:154-161 - Query for student assignments
cursor.execute('''
SELECT a.id, a.title, a.module_code, a.due_date
FROM assignments a
JOIN student_modules sm ON a.module_code = sm.module_code
...
''', (student_id, student_id))
```

---

### 5. Analytics - Generate Health Report (Missing Feature)
**Status**: PENDING ⏳
**File**: `analytics.py`
**Error**: Feature does not exist

**Requirement**:
- Add "Generate Health Report" button to analytics dashboard
- Report should show:
  * System health metrics (database integrity, file storage status)
  * Assignment system statistics (total assignments, submissions, grades)
  * User activity metrics
  * Error/warning counts
- **Must email report to admin automatically**
- Fetch admin email from database (users table where role = 'admin')

**Solution Required**:
- Add `generate_health_report()` method to AnalyticsManager
- Query system metrics from database
- Format as readable report
- Use email service to send to admin
- Display confirmation to user

---

### 6. Analytics - Custom Reports Email Integration
**Status**: PENDING ⏳
**File**: `analytics.py`
**Current Behavior**: Reports only saved to file

**Requirement**:
- Show custom reports on screen (in a window/dialog)
- Add "Email to Admin" button
- Fetch correct admin email from database
- Send report via email service
- Similar to Module Scheduling GUI implementation

**Solution Required**:
- Modify `create_custom_report()` to show report in window
- Add email integration using `send_email()` from infrastructure
- Query admin email: `SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1`
- Add "View" and "Email" buttons to custom reports interface

**Code Location**:
```python
# analytics.py:577-619 - create_custom_report() function
# Currently only saves to file, needs to also display and email
```

---

### 7. Analytics - Submission Trends Shows Blank Screen
**Status**: PENDING ⏳
**File**: `analytics.py`
**Error**: "Submission trends shows blank screen with nothing on"

**Issue**:
- Chart rendering may be failing silently
- Or no data available for past 30 days
- Error handling may be hiding the issue

**Solution Required**:
- Add better error messages when no data available
- Show placeholder message: "No submission data available for the selected period"
- Add sample data generator for testing
- Check matplotlib/canvas embedding

**Code Location**:
```python
# analytics.py:233-295 - create_submission_trends() function
# Line 249: if submission_data: - may be False, causing blank screen
```

---

### 8. Messaging - Send Messages Not Using Email System
**Status**: PENDING ⏳
**File**: `messaging.py`
**Current Behavior**: Shows text box instead of actually sending email

**Requirement**:
- Link "Send Messages" button to actual email service
- Use `send_email()` from infrastructure.email.email_service
- Send real emails to recipients
- Store in messages table AND send via email service

**Solution Required**:
- Import email service: `from university_system.infrastructure.email.email_service import send_email`
- Call `send_email(recipient_email=..., subject=..., body=...)`
- Show confirmation after email sent
- Handle email delivery errors gracefully

---

### 9. Manage Groups - Missing Create Groups Button
**Status**: PENDING ⏳
**File**: `group_manager.py`
**Current Behavior**: Cannot create new groups from GUI

**Requirement**:
- Add "Create Group" button to group management interface
- Allow selection of module
- Allow selection of students enrolled in that module
- Set group name and size
- Assign students to group

**Solution Required**:
- Add `create_group_gui()` method to GroupManager
- Query students in selected module
- Multi-select listbox for student selection
- Validate group size
- Insert into groups table
- Link students via group_members table

---

### 10. Templates - Incorrect Import Paths
**Status**: PENDING ⏳
**File**: `template_manager.py`
**Error**: "Import path is incorrect to view these"

**Issue**:
- Template viewing/import functionality broken
- Import statements may be using old paths
- Templates may be stored in wrong directory

**Solution Required**:
- Verify template storage location uses `paths.DATA_DIR / 'templates' / 'assignments'`
- Update all import/export paths
- Fix any hardcoded paths
- Ensure templates directory exists on initialization

---

### 11. File Preview - Window Too Small
**Status**: PENDING ⏳
**File**: `file_preview.py`
**Current Behavior**: Preview window is too small to view content

**Requirement**:
- Make file preview window bigger
- Suggested size: 1200x800 or larger
- Make window resizable
- Proper scrollbars for large files

**Solution Required**:
- Update `show_file_preview()` window geometry
- Change from small size to: `preview_window.geometry("1200x800")`
- Add `preview_window.resizable(True, True)`
- Ensure content scrolls properly

---

### 12. Calendar Button - Opens New Window Instead of Full GUI
**Status**: PENDING ⏳
**File**: `file_preview.py`
**Current Behavior**: Creates a basic calendar window

**Requirement**:
- Open the full Academic Calendar GUI instead
- Use existing academic_calendar_gui.py
- Pass proper parent window
- Integrate seamlessly

**Solution Required**:
- Import: `from university_system.modules.domain.academics.gui.academic_calendar_gui import CalendarGUI`
- Create top-level window
- Initialize CalendarGUI with parent_window parameter
- Remove basic calendar implementation

**Code Location**:
```python
# file_preview.py - show_calendar() method
# Currently creates basic window, needs to launch full CalendarGUI
```

---

## 📋 TECHNICAL NOTES

### Database Schema Issues
Several issues relate to database schema mismatches:
- notifications table missing `created_at` column
- notifications table `id` column may not exist or be named differently
- Need comprehensive schema validation

### Email Integration Pattern
Multiple features need email integration. Standard pattern:
```python
# Get admin email from database
from university_system.infrastructure.database.db import get_connection

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1")
    admin_row = cursor.fetchone()
    admin_email = admin_row[0] if admin_row else "admin@university.edu"

# Send email
from university_system.infrastructure.email.email_service import send_email

send_email(
    recipient_email=admin_email,
    subject="Report Subject",
    body="Report content..."
)
```

### Path Handling Pattern
Use this pattern for all file operations:
```python
from university_system.modules.shared.constants import paths

# Check if attribute exists, use fallback if None
submission_dir = getattr(self.assignment_system, 'submission_dir', None)
if submission_dir is None:
    base_dir = paths.UPLOAD_DIR / 'submissions'
else:
    base_dir = Path(submission_dir)
```

---

## PRIORITY RANKING

### P0 - Critical (Breaks Core Functionality)
1. ✅ File Path Errors (FIXED)
2. Submit Assignments - No assignments showing
3. Notifications - "no such column: id" error

### P1 - High (Major Features Missing/Broken)
4. Generate Health Report (missing feature)
5. Custom Reports - Email integration
6. Send Messages - Not using email system
7. Manage Groups - Create groups button missing

### P2 - Medium (UX Issues)
8. Notifications - Missing created_at column
9. Submission Trends - Blank screen
10. Templates - Incorrect import paths

### P3 - Low (Minor Enhancements)
11. File Preview - Window too small
12. Calendar Button - Use full GUI

---

## TESTING CHECKLIST

After each fix, verify:
- [ ] No Python syntax errors (`python3 -m py_compile <file>`)
- [ ] Database queries execute successfully
- [ ] Email service integration works
- [ ] UI elements display correctly
- [ ] Error handling provides useful messages
- [ ] Changes documented in CHANGELOG.md

---

**Last Updated**: 2025-11-11
**Total Issues**: 12
**Fixed**: 1
**Remaining**: 11
