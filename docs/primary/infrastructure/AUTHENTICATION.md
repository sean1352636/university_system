# Primary School Authentication Guide

> Last Updated: October 2026

## Overview

The Primary School Management System uses the **shared authentication module** that is common to all seven Education System systems. This architecture ensures consistent security policies, a single set of user credentials, and the ability for users to access multiple systems with one account.

---

## Shared Auth Architecture

Authentication is handled by a centralised module at:

```
src/education_system/platform/identity/auth/
```

This module provides:

- User registration and credential management
- Password hashing and verification
- Session creation and validation
- Multi-Factor Authentication (MFA)
- Account lockout protection
- Role-based access control per system

The Primary School system does **not** implement its own authentication logic. There is no wrapper package: the launcher signs the user in and passes the system a `shared_auth` object, an instance of `UserAuth`.

```python
from education_system.platform.identity.auth import UserAuth, SessionManager, MFAService
```

---

## Central Auth Database

All authentication data is stored in a single shared database:

```
var/data/platform/db_files/auth.db
```

### Auth Database Tables

| Table | Description |
|---|---|
| `users` | User accounts: username, email, password hash, `legacy_salt`, `failed_login_attempts`, `locked_until`, creation date. |
| `sessions` | Sessions: token, user ID, expiry timestamp, active flag. |
| `mfa_secrets` | TOTP secrets for users who have enabled MFA. |
| `mfa_recovery_codes` | One-time recovery codes for MFA bypass. |
| `user_systems` | Maps each user to one or more systems (nursery, primary, secondary, sixth_form, fe_college, apprenticeships, university) with a per-system role. |

### user_systems Table

The `user_systems` table is the key to multi-system access. Each row links a user to a specific system with a specific role:

```
user_id | system_key | role
--------|------------|--------
1       | primary    | admin
2       | primary    | teacher
2       | sixth_form | staff
3       | primary    | parent
```

This means a single user account can have different roles in different systems, and the Primary School only sees users who have a `system_key = 'primary'` entry.

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
3. **Expiry**: Sessions expire **30 minutes** after creation (configurable via `EDU_SESSION_TIMEOUT`).
4. **Logout**: The session record is marked inactive, and expired or inactive records are cleared later.

### Session Configuration

| Parameter | Default | Description |
|---|---|---|
| `EDU_SESSION_TIMEOUT` | 30 minutes | Time before a session expires. |

---

## Account Lockout

To protect against brute-force password attacks, the system enforces account lockout:

| Parameter | Value |
|---|---|
| Maximum login attempts | **3** |
| Lockout duration | **15 minutes** |

After 3 consecutive failed login attempts, the account is locked for 15 minutes. The lockout counter resets after a successful login.

Administrators can manually unlock accounts through the admin panel.

---

## Roles

The Primary School system uses these roles from the shared role vocabulary, each with different levels of access:

| Role | Description | Typical Permissions |
|---|---|---|
| `admin` | School administrator | Full system access. User management, settings, finance, data export, audit logs. |
| `teacher` | Teaching staff | Pupil records, assessment, attendance, homework, behaviour, reports. Own class data. |
| `student` | Pupil (limited) | View own records, homework, timetable, reading log. Minimal write access. |
| `parent` | Parent/guardian | View linked pupil's records, attendance, reports, consent forms. Book parents' evening slots. |

Role filtering is enforced in the primary GUI and CLI by one rule, `systems/primary/domain/access.py`, checked both when a menu is drawn and when a screen opens. Domain modules still do not check roles. On the API, routes require a token (`token_required`), and the generated menu routes also require staff (`staff_required`). See [SECURITY.md](../security/SECURITY.md#role-based-access-control-rbac) for what each role sees.

---

## Default Accounts

The shared auth module provisions default accounts for each system when `EDU_DEV_SEED=true`; without that flag none are created. For Primary School:

| Username | Password | Role | Notes |
|---|---|---|---|
| `superadmin` | `SuperAdmin@123` | admin | Access to all 7 systems. |
| `admin3` | `admin1234` | admin | Primary school administrator. |
| `staff3` | `staff1234` | teacher | Sample teacher account. |
| `student3` | `student1234` | student | Sample pupil account. |
| `parent3` | `parent1234` | parent | Sample parent account. |

**Important:** Change all default passwords before any production or real-school deployment. These credentials are documented publicly and must be treated as insecure.

---

## Universal Login Flow

The Education System platform provides a unified login experience via `python -m education_system`:

```
python -m education_system
  |
  v
UniversalLoginWindow (src/education_system/platform/delivery/gui/login_gui.py)
  |
  v
User enters credentials
  |
  v
src/education_system/platform/identity/auth/ authenticates against auth.db
  |
  v
System selection (if user has access to multiple systems)
  |
  v
Primary School GUI launches with user_info=, role=, shared_auth=
```

### Step-by-step:

1. **`python -m education_system`** is the single entry point for the entire Education System.
2. The **UniversalLoginWindow** is displayed, prompting for username and password.
3. Credentials are verified against `auth.db` using the shared auth module.
4. If the user has MFA enabled, a TOTP code (or recovery code) is requested.
5. If the user has access to **multiple systems** (e.g., primary and sixth form), they select which system to enter.
6. The Primary School application is launched, receiving `user_info`, `role`, and a `shared_auth` reference so it does not need to re-authenticate.
7. The Primary School GUI has no login screen of its own and proceeds directly to the dashboard.

### Direct Launch (Development)

For development or testing, the launcher can go straight to this system with `python -m education_system --primary --gui`. You still sign in: `gui_main.run()` and `cli_main.run()` refuse to start without a signed-in `shared_auth`.
