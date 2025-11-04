# User Accounts Fix - October 2025

## Problem

When logging in with the `admin` account, users were seeing "logged in as student" instead of "logged in as admin". This was caused by incorrect mappings between the `user_accounts` and `users` tables in the database.

### Root Cause

In the original `_create_default_accounts_if_needed()` method in `user_authentication.py`, the code checked for existing users using:

```python
cursor.execute(
    'SELECT id FROM users WHERE username = ? OR email = ?',
    (account['username'], account['email']),
)
```

The `OR` condition with email was problematic because:
1. If any user had a matching email (like `admin@example.com`), the code would reuse that user's ID
2. This could cause system accounts (admin, staff) to point to wrong users with wrong roles
3. When the database was initialized, students got user IDs 1, 2, 3, etc., and later when admin accounts were created, they ended up pointing to those student records

## Solutions Applied

### 1. Fixed Account Creation Logic

**File:** `university_system/infrastructure/auth/user_authentication.py`
**Method:** `_create_default_accounts_if_needed()`

**Changes:**
- Changed user lookup to check **only by username**, not email
- Added role verification: if user exists but has wrong role, update it
- Added proper error handling and logging

**Before:**
```python
cursor.execute(
    'SELECT id FROM users WHERE username = ? OR email = ?',
    (account['username'], account['email']),
)
```

**After:**
```python
# Check if user already exists by username ONLY (not email)
# This prevents accidentally reusing a different user's ID if emails happen to match
cursor.execute(
    'SELECT id, role FROM users WHERE username = ?',
    (account['username'],),
)
user_row = cursor.fetchone()

if user_row:
    # User exists - verify it has the correct role
    user_id, existing_role = user_row
    if existing_role != account['role']:
        logging.warning(
            f"User '{account['username']}' exists with role '{existing_role}' "
            f"but expected '{account['role']}'. Updating role."
        )
        cursor.execute(
            'UPDATE users SET role = ?, updated_at = ? WHERE id = ?',
            (account['role'], timestamp, user_id)
        )
```

### 2. Created Fix Utility

**File:** `university_system/utils/fix_user_accounts.py`

A comprehensive utility script that:
- Analyzes the database for account mapping issues
- Fixes system accounts (admin, staff, student) to have correct roles
- Cleans up duplicate account mappings
- Removes orphaned accounts
- Verifies database integrity

**Usage:**

```bash
# Analyze only (no changes)
python university_system/utils/fix_user_accounts.py --analyze-only

# Fix with confirmation prompt
python university_system/utils/fix_user_accounts.py

# Fix automatically without prompt
python university_system/utils/fix_user_accounts.py --yes
```

## Impact

### What Was Fixed
✅ Admin account now correctly shows "role: admin"
✅ Staff account now correctly shows "role: staff"
✅ Student account now correctly shows "role: student"
✅ Future database initializations will create accounts correctly
✅ Duplicate account mappings have been cleaned up

### What Changed
- **user_authentication.py**: Updated `_create_default_accounts_if_needed()` method
- **New utility**: `university_system/utils/fix_user_accounts.py`
- **Database**: Fixed existing incorrect mappings

## Testing

### Before Fix
```
Username: admin
Password: admin123
Welcome, admin! You are logged in as student.  ❌
Logged in as: admin (Role: student)            ❌
```

### After Fix
```
Username: admin
Password: admin123
Welcome, admin! You are logged in as admin.    ✅
Logged in as: admin (Role: admin)              ✅
```

## Database Verification

Check system account mappings:
```bash
sqlite3 university_system/data/db_files/student_records.db \
  "SELECT ua.username, ua.user_id, u.username as user_username, u.role
   FROM user_accounts ua
   JOIN users u ON ua.user_id = u.id
   WHERE ua.username IN ('admin', 'staff', 'student');"
```

Expected output:
```
admin|192|admin|admin
staff|193|staff|staff
student|194|student|student
```

## Prevention

This fix ensures that:
1. **New databases** will be initialized correctly from the start
2. **Existing databases** can be fixed using the utility script
3. **Future changes** won't accidentally introduce this issue again

### Best Practices

When creating user accounts:
1. ✅ Always check for existing users by **username only**
2. ✅ Verify the role matches expectations
3. ✅ Create both `users` and `user_accounts` records in the same transaction
4. ✅ Use `cursor.lastrowid` to get the correct `user_id`
5. ❌ Don't use `OR` conditions with email when looking up users for account creation

## Rollback

If you need to rollback these changes:
1. The old behavior can be restored by reverting the changes to `user_authentication.py`
2. However, this is NOT recommended as it would reintroduce the bug
3. Instead, use the fix utility to correct any issues

## Future Improvements

Potential enhancements:
- [ ] Add database migration system to track schema changes
- [ ] Add automated tests for account creation logic
- [ ] Add constraint checks to prevent duplicate mappings at database level
- [ ] Create a dashboard to monitor account health

## Questions?

If you encounter issues:
1. Run the fix utility in analyze mode: `python university_system/utils/fix_user_accounts.py --analyze-only`
2. Check the logs in `university_system/logs/`
3. Verify database integrity with the SQL queries above

---

**Fixed by:** Claude Code
**Date:** October 31, 2025
**Ticket:** Admin login showing wrong role
**Status:** ✅ Resolved
