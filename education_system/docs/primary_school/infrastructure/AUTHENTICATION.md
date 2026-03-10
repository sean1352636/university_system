# Primary School Authentication Guide

> Last Updated: March 2026

## Overview

The Primary School Management System uses the **shared authentication module** that is common to all four Education System subsystems. This architecture ensures consistent security policies, a single set of user credentials, and the ability for users to access multiple systems with one account.

---

## Shared Auth Architecture

Authentication is handled by a centralised module at:

```
education_system/shared/auth/
```

This module provides:

- User registration and credential management
- Password hashing and verification
- Session creation and validation
- Multi-Factor Authentication (MFA)
- Account lockout protection
- Role-based access control per system

The Primary School system does **not** implement its own authentication logic. Instead, it delegates to the shared module through a thin wrapper.

### Wrapper Layer

```
education_system/primary_school/infrastructure/auth/
```

The Primary School's `infrastructure/auth/` package re-exports functions from `shared/auth/`, providing a stable import path for the rest of the Primary School codebase. This indirection allows system-specific customisation (e.g., role defaults) without modifying the shared module.

```python
# primary_school/infrastructure/auth/__init__.py (simplified)
from shared.auth import authenticate, create_session, validate_session, ...
```

---

## Central Auth Database

All authentication data is stored in a single shared database:

```
education_system/shared/data/db_files/auth.db
```

### Auth Database Tables

| Table | Description |
|---|---|
| `users` | User accounts: username, email, password hash, `legacy_salt`, locked status, creation date. |
| `sessions` | Active sessions: token, user ID, expiry timestamp, IP address. |
| `mfa_secrets` | TOTP secrets for users who have enabled MFA. |
| `mfa_recovery_codes` | One-time recovery codes for MFA bypass. |
| `user_systems` | Maps each user to one or more systems (university, college, school, primary) with a per-system role. |

### user_systems Table

The `user_systems` table is the key to multi-system access. Each row links a user to a specific system with a specific role:

```
user_id | system   | role
--------|----------|--------
1       | primary  | admin
2       | primary  | teacher
2       | college  | staff
3       | primary  | parent
```

This means a single user account can have different roles in different systems, and the Primary School only sees users who have a `system = 'primary'` entry.

---

## Password Hashing

### Current Standard: bcrypt

All new passwords are hashed using **bcrypt** with an automatically generated salt. bcrypt is an adaptive hashing algorithm that is deliberately slow to resist brute-force attacks.

```python
import bcrypt

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
```

### Legacy Migration: PBKDF2-SHA256

Older accounts may have passwords hashed with PBKDF2-SHA256. These are identified by a non-null `legacy_salt` column in the `users` table.

**Automatic migration process:**

1. User attempts to log in.
2. System detects `legacy_salt` is set for this account.
3. Password is verified against the PBKDF2 hash using the stored salt.
4. If valid, the password is re-hashed with bcrypt.
5. The new bcrypt hash replaces the old hash, and `legacy_salt` is set to `NULL`.
6. All subsequent logins use bcrypt verification.

This migration is **transparent** to the user -- no action is required on their part.

---

## Session Management

Sessions are **database-backed** rather than stored in cookies or local memory, providing:

- Central session visibility (administrators can view active sessions).
- Reliable session expiry enforcement.
- Session revocation without requiring client cooperation.

### Session Lifecycle

1. **Creation**: On successful login, a cryptographically random token is generated and stored in the `sessions` table with the user ID and an expiry timestamp.
2. **Validation**: Each request includes the session token. The system checks the `sessions` table to verify the token exists and has not expired.
3. **Renewal**: Active sessions may have their expiry extended on each valid request.
4. **Expiry**: Sessions expire after **30 minutes** of inactivity (configurable via `SESSION_TIMEOUT`).
5. **Logout**: The session record is deleted from the database.

### Session Configuration

| Parameter | Default | Description |
|---|---|---|
| `SESSION_TIMEOUT` | 30 minutes | Time before an inactive session expires. |

---

## Account Lockout

To protect against brute-force password attacks, the system enforces account lockout:

| Parameter | Value |
|---|---|
| Maximum login attempts | **5** |
| Lockout duration | **15 minutes** |

After 5 consecutive failed login attempts, the account is locked for 15 minutes. The lockout counter resets after a successful login.

Administrators can manually unlock accounts through the admin panel.

---

## Roles

The Primary School system defines four roles, each with different levels of access:

| Role | Description | Typical Permissions |
|---|---|---|
| `admin` | School administrator | Full system access. User management, settings, finance, data export, audit logs. |
| `teacher` | Teaching staff | Pupil records, assessment, attendance, homework, behaviour, reports. Own class data. |
| `student` | Pupil (limited) | View own records, homework, timetable, reading log. Minimal write access. |
| `parent` | Parent/guardian | View linked pupil's records, attendance, reports, consent forms. Book parents' evening slots. |

Role-based access control (RBAC) is enforced at the service layer. Each service method checks the current user's role before permitting the operation.

---

## Default Accounts

The shared auth module provisions default accounts for each system. For Primary School:

| Username | Password | Role | Notes |
|---|---|---|---|
| `superadmin` | `Super@Admin123` | admin | Access to all 4 systems. |
| `primary_admin` | `Admin@Primary123` | admin | Primary school administrator. |
| `primary_teacher` | `Staff@Primary123` | teacher | Sample teacher account. |
| `primary_student` | `Student@Primary123` | student | Sample pupil account. |
| `primary_parent` | `Parent@Primary123` | parent | Sample parent account. |

**Important:** Change all default passwords before any production or real-school deployment. These credentials are documented publicly and must be treated as insecure.

---

## Universal Login Flow

The Education System platform provides a unified login experience via `run.py`:

```
run.py
  |
  v
UniversalLoginWindow (shared/gui/login_gui.py)
  |
  v
User enters credentials
  |
  v
shared/auth/ authenticates against auth.db
  |
  v
System selection (if user has access to multiple systems)
  |
  v
Primary School GUI launches with user_info=, role=, shared_auth=
```

### Step-by-step:

1. **`run.py`** is the single entry point for the entire Education System.
2. The **UniversalLoginWindow** is displayed, prompting for username and password.
3. Credentials are verified against `auth.db` using the shared auth module.
4. If the user has MFA enabled, a TOTP code (or recovery code) is requested.
5. If the user has access to **multiple systems** (e.g., primary and college), they select which system to enter.
6. The Primary School application is launched, receiving `user_info`, `role`, and a `shared_auth` reference so it does not need to re-authenticate.
7. The Primary School GUI skips its own login screen and proceeds directly to the dashboard.

### Direct Launch (Development)

For development or testing, individual systems can be launched directly. The Primary School launcher also accepts `user_info=`, `role=`, and `shared_auth=` keyword arguments to bypass login.
