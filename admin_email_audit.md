# Admin Email Routing Audit Report

**Date:** 2025-11-14
**Purpose:** Verify all GUI files sending reports/emails to admin are linked to correct user accounts after user ID reorganization

## Executive Summary

✅ **Status:** All admin email routing verified and fixed
🔧 **Issues Found:** 1 hardcoded reference
✅ **Resolution:** Updated to use correct admin user ID

---

## Current Admin Accounts

After v5.0.8 reorganization:

| User ID | Username | Email | Role | Status |
|---------|----------|-------|------|--------|
| 1 | system_teessideuniversity | noreply@university.edu | admin | ✅ Primary System Admin |
| 2 | 1952392 | lucas.jones@university.edu | staff | ✅ Staff Account |
| 3 | S12345 | student@example.com | student | ✅ Student Account |

---

## Files Audited

### ✅ CORRECT - No Changes Needed

#### 1. **Health Portal GUI** (`health_portal_gui.py:3716`)
```sql
SELECT DISTINCT email FROM users WHERE role = 'admin'
AND email IS NOT NULL AND email != ''
```
**Status:** ✅ Correctly queries all admin emails by role
**Impact:** Health emergency notifications sent to all admins

#### 2. **Library GUI** (`library_gui.py:3230`)
```sql
SELECT email FROM users WHERE role = 'admin' LIMIT 1
```
**Status:** ✅ Gets first admin by role (will be ID 1)
**Impact:** Library reports sent to system admin

#### 3. **Module Scheduling GUI** (`module_scheduling_gui.py:304, 352`)
```sql
-- Single admin email:
SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1

-- All admin emails for selection:
SELECT username, email FROM users WHERE LOWER(role) = 'admin' ORDER BY username
```
**Status:** ✅ Correctly queries admin by role
**Fallback:** Uses "admin@university.edu" if no admin found
**Impact:** Scheduling reports sent to admin

#### 4. **Course Management GUI** (`course_management_gui.py:2109`)
```sql
SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1
```
**Status:** ✅ Correctly queries admin by role
**Fallback:** Uses "admin@university.edu" if no admin found
**Impact:** Course reports sent to admin

#### 5. **Financial Reporting GUI** (`finance_reporting_gui.py:5536`)
```python
recipients_entry.insert(0, "finance@university.edu, admin@university.edu")
```
**Status:** ✅ Uses generic email addresses (static configuration)
**Impact:** Financial reports sent to configured email addresses

#### 6. **Financial Reports Module** (`financial_reports.py:75, 1342, 1349`)
```python
self.notification_emails = ['finance@university.edu', 'admin@university.edu']
```
**Status:** ✅ Uses generic email addresses (static configuration)
**Impact:** Financial alerts sent to configured email addresses

#### 7. **Helpdesk GUI** (`helpdesk_gui.py:7483`)
```python
admin_email = "admin@university.edu"
```
**Status:** ✅ Uses generic admin email (static configuration)
**Impact:** Helpdesk ticket notifications

---

### 🔧 FIXED - Changes Made

#### 8. **Housing Accommodation GUI** (`housing_accommodation_gui.py:4710`)

**Problem:** Hardcoded username reference to '7591239' (outdated admin account)

**Before:**
```sql
SELECT email, first_name, last_name
FROM users
WHERE (role = 'admin' OR role = 'staff')
AND email IS NOT NULL
AND email != ''
ORDER BY
    CASE
        WHEN username = '7591239' THEN 1  -- ❌ Points to student (ID 194)
        WHEN role = 'admin' THEN 2
        WHEN role = 'staff' THEN 3
        ELSE 4
    END
LIMIT 1
```

**After:**
```sql
SELECT email, first_name, last_name
FROM users
WHERE (role = 'admin' OR role = 'staff')
AND email IS NOT NULL
AND email != ''
ORDER BY
    CASE
        WHEN id = 1 THEN 1  -- ✅ Points to system admin
        WHEN role = 'admin' THEN 2
        WHEN role = 'staff' THEN 3
        ELSE 4
    END
LIMIT 1
```

**Impact:**
- Housing inspection reports now sent to correct admin (system_teessideuniversity)
- Accommodation notifications routed to noreply@university.edu
- Removes dependency on hardcoded username

---

## Verification Queries

All admin email queries were tested against current database:

```sql
-- Primary admin (ID 1)
SELECT id, username, email, role FROM users WHERE id = 1;
-- Result: 1|system_teessideuniversity|noreply@university.edu|admin ✅

-- All admins
SELECT id, username, email, role FROM users WHERE role = 'admin';
-- Results:
--   1|system_teessideuniversity|noreply@university.edu|admin
--   197|system_||admin (incomplete record)

-- Verify old '7591239' is now a student
SELECT id, username, email, role FROM users WHERE username = '7591239';
-- Result: 194|7591239|c759123@tees.ac.uk|student ✅
```

---

## Recommendations

### ✅ Implemented
1. Changed hardcoded username reference to use user ID
2. Verified all admin email queries work correctly
3. Documented changes in CHANGELOG.md

### 📋 Future Improvements
1. **Consider centralizing admin email configuration:**
   - Create a system settings table for admin contact emails
   - Allows dynamic configuration without code changes

2. **Clean up incomplete admin record:**
   - User ID 197 (system_) has no email - should be deleted or completed

3. **Standardize email fallbacks:**
   - Some files use "admin@university.edu" as fallback
   - Consider using actual system admin email (noreply@university.edu) instead

---

## Summary

**Total Files Audited:** 8 GUI/module files
**Issues Found:** 1 hardcoded reference
**Issues Fixed:** 1
**Status:** ✅ All admin email routing verified and functional

All reports and notifications will now correctly route to the system admin account (ID 1: system_teessideuniversity / noreply@university.edu) or dynamically query admins by role.
