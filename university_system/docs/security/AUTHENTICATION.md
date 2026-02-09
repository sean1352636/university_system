# Authentication Flow Documentation

## Overview

The University Management System implements a secure, centralized authentication system with role-based access control (RBAC). This document describes the authentication and authorization flows, security measures, and implementation details.

## Table of Contents

- [Architecture](#architecture)
- [Authentication Flow](#authentication-flow)
- [Password Security](#password-security)
- [Session Management](#session-management)
- [Authorization](#authorization)
- [Role-Based Access Control](#role-based-access-control)
- [Implementation Examples](#implementation-examples)
- [Security Features](#security-features)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │   CLI    │    │   GUI    │    │    Web Interface     │  │
│  └────┬─────┘    └─────┬────┘    └──────────┬───────────┘  │
└───────┼────────────────┼────────────────────┼───────────────┘
        │                │                    │
        └────────────────┼────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────────┐
│                        v                                     │
│              Authentication Layer                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │     infrastructure/auth/auth_system.py               │  │
│  │  - User authentication                               │  │
│  │  - Password hashing/verification                     │  │
│  │  - Session management                                │  │
│  │  - Permission checking                               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────────┐
│                        v                                     │
│                   Database Layer                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │  users   │    │sessions  │    │   audit_log          │  │
│  └──────────┘    └──────────┘    └──────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Files

- `infrastructure/auth/auth_system.py`: Core authentication module
- `infrastructure/auth/permissions.py`: Permission management
- `infrastructure/auth/roles.py`: Role definitions
- `infrastructure/database/db.py`: Database operations

## Authentication Flow

### 1. Login Process

```
┌─────────┐           ┌──────────────┐           ┌──────────┐
│  User   │           │   Auth       │           │ Database │
│         │           │  System      │           │          │
└────┬────┘           └──────┬───────┘           └─────┬────┘
     │                       │                         │
     │  1. Submit            │                         │
     │  credentials          │                         │
     ├──────────────────────>│                         │
     │                       │                         │
     │                       │  2. Query user by       │
     │                       │     username            │
     │                       ├────────────────────────>│
     │                       │                         │
     │                       │  3. Return user record  │
     │                       │     (hash, salt, role)  │
     │                       │<────────────────────────┤
     │                       │                         │
     │                       │  4. Hash submitted      │
     │                       │     password with salt  │
     │                       │                         │
     │                       │  5. Compare hashes      │
     │                       │                         │
     │                       ├─┐                       │
     │                       │ │ If match:             │
     │                       │ │                       │
     │                       │ │ 6. Create session     │
     │                       │ │    token              │
     │                       │<┘                       │
     │                       │                         │
     │                       │  7. Store session       │
     │                       ├────────────────────────>│
     │                       │                         │
     │                       │  8. Log successful      │
     │                       │     login to audit_log  │
     │                       ├────────────────────────>│
     │                       │                         │
     │  9. Return session    │                         │
     │     token + user info │                         │
     │<──────────────────────┤                         │
     │                       │                         │
     ├─┐                     │                         │
     │ │ 10. Store token     │                         │
     │ │     for subsequent  │                         │
     │ │     requests        │                         │
     │<┘                     │                         │
     │                       │                         │
```

### 2. Failed Login Attempt

```
If password doesn't match:
  1. Increment failed_login_attempts
  2. Log failed attempt to audit_log
  3. If attempts >= threshold (e.g., 5):
     - Set account_locked_until (e.g., 30 minutes)
     - Send notification email
  4. Return generic error message (prevent username enumeration)
```

### 3. Logout Process

```
┌─────────┐           ┌──────────────┐           ┌──────────┐
│  User   │           │   Auth       │           │ Database │
└────┬────┘           └──────┬───────┘           └─────┬────┘
     │                       │                         │
     │  1. Logout request    │                         │
     │     with session token│                         │
     ├──────────────────────>│                         │
     │                       │                         │
     │                       │  2. Delete session      │
     │                       ├────────────────────────>│
     │                       │                         │
     │                       │  3. Log logout event    │
     │                       ├────────────────────────>│
     │                       │                         │
     │  4. Confirmation      │                         │
     │<──────────────────────┤                         │
     │                       │                         │
```

## Password Security

### Hashing Algorithm

The system uses PBKDF2-HMAC-SHA256 for password hashing:

```python
import hashlib
import os
from typing import Tuple

def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    Args:
        password: The password to hash
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (hashed_password, salt) both as hex strings

    Security parameters:
        - Algorithm: PBKDF2-HMAC-SHA256
        - Iterations: 100,000
        - Salt length: 32 bytes
        - Hash length: 128 bytes
    """
    if salt is None:
        salt = os.urandom(32)  # 32 bytes = 256 bits
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)

    # Hash the password with 100,000 iterations
    key = hashlib.pbkdf2_hmac(
        'sha256',           # Hash algorithm
        password.encode('utf-8'),  # Convert password to bytes
        salt,               # Salt
        100000,             # Number of iterations
        dklen=128           # Desired key length
    )

    return key.hex(), salt.hex()
```

### Password Verification

```python
def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """
    Verify a password against stored hash and salt.

    Args:
        password: Password to verify
        stored_hash: Stored password hash (hex string)
        stored_salt: Stored salt (hex string)

    Returns:
        True if password matches, False otherwise
    """
    # Hash the submitted password with the stored salt
    computed_hash, _ = hash_password(password, stored_salt)

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed_hash, stored_hash)
```

### Password Requirements

Default password requirements (configurable):

```python
PASSWORD_REQUIREMENTS = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_digit': True,
    'require_special': True,
    'special_chars': '!@#$%^&*()_+-=[]{}|;:,.<>?'
}

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password meets requirements.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < PASSWORD_REQUIREMENTS['min_length']:
        return False, f"Password must be at least {PASSWORD_REQUIREMENTS['min_length']} characters"

    if PASSWORD_REQUIREMENTS['require_uppercase'] and not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if PASSWORD_REQUIREMENTS['require_lowercase'] and not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if PASSWORD_REQUIREMENTS['require_digit'] and not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    if PASSWORD_REQUIREMENTS['require_special']:
        if not any(c in PASSWORD_REQUIREMENTS['special_chars'] for c in password):
            return False, "Password must contain at least one special character"

    return True, ""
```

## Session Management

### Session Creation

```python
import secrets
from datetime import datetime, timedelta

def create_session(user_id: int, ip_address: str = None, user_agent: str = None) -> str:
    """
    Create a new session for a user.

    Args:
        user_id: User ID
        ip_address: Client IP address (optional)
        user_agent: Client user agent (optional)

    Returns:
        Session token (secure random string)
    """
    # Generate secure random token
    session_token = secrets.token_urlsafe(32)

    # Calculate expiration time (default: 1 hour)
    expires_at = datetime.now() + timedelta(seconds=SESSION_TIMEOUT)

    # Store session in database
    with get_db_transaction() as (conn, cursor):
        cursor.execute("""
            INSERT INTO sessions (user_id, session_token, ip_address, user_agent, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, session_token, ip_address, user_agent, expires_at))

    return session_token
```

### Session Validation

```python
def validate_session(session_token: str) -> Optional[Dict]:
    """
    Validate a session token and return user info.

    Args:
        session_token: Session token to validate

    Returns:
        User info dict if valid, None if invalid/expired
    """
    db = DatabaseManager()
    conn = db.get_connection()
    cursor = conn.cursor()

    # Query session and user info
    cursor.execute("""
        SELECT s.user_id, s.expires_at, s.last_activity,
               u.username, u.role, u.active, u.account_locked_until
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.session_token = ?
    """, (session_token,))

    result = cursor.fetchone()
    db.close()

    if not result:
        return None

    user_id, expires_at, last_activity, username, role, active, locked_until = result

    # Check if session expired
    if datetime.fromisoformat(expires_at) < datetime.now():
        invalidate_session(session_token)
        return None

    # Check if account is active
    if not active:
        return None

    # Check if account is locked
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now():
        return None

    # Update last activity
    update_session_activity(session_token)

    return {
        'user_id': user_id,
        'username': username,
        'role': role
    }
```

### Session Timeout

```python
# Session configuration
SESSION_TIMEOUT = 3600  # 1 hour in seconds
SESSION_REFRESH_INTERVAL = 900  # 15 minutes

def update_session_activity(session_token: str):
    """Update last activity timestamp for a session."""
    with get_db_transaction() as (conn, cursor):
        cursor.execute("""
            UPDATE sessions
            SET last_activity = CURRENT_TIMESTAMP
            WHERE session_token = ?
        """, (session_token,))
```

### Session Cleanup

```python
def cleanup_expired_sessions():
    """
    Remove expired sessions from database.
    Should be run periodically (e.g., via cron job).
    """
    with get_db_transaction() as (conn, cursor):
        cursor.execute("""
            DELETE FROM sessions
            WHERE expires_at < CURRENT_TIMESTAMP
        """)
        deleted_count = cursor.rowcount

    return deleted_count
```

## Authorization

### Permission System

Permissions are defined as strings in the format `resource.action`:

```python
# Example permissions
PERMISSIONS = {
    # Course permissions
    'courses.view',
    'courses.create',
    'courses.edit',
    'courses.delete',

    # Student permissions
    'students.view',
    'students.edit',
    'students.grades.view',
    'students.grades.edit',

    # Admin permissions
    'users.manage',
    'system.configure',

    # Financial permissions
    'finance.view',
    'finance.process_payments',
}
```

### Role Definitions

```python
# infrastructure/auth/roles.py
ROLES = {
    'admin': {
        'description': 'System administrator',
        'permissions': '*',  # All permissions
    },
    'faculty': {
        'description': 'Faculty member',
        'permissions': [
            'courses.view',
            'courses.create',
            'courses.edit',
            'students.view',
            'students.grades.view',
            'students.grades.edit',
            'assignments.create',
            'assignments.grade',
        ]
    },
    'student': {
        'description': 'Student',
        'permissions': [
            'courses.view',
            'courses.enroll',
            'assignments.view',
            'assignments.submit',
            'grades.view_own',
        ]
    },
    'staff': {
        'description': 'Staff member',
        'permissions': [
            'students.view',
            'finance.view',
            'finance.process_payments',
        ]
    }
}
```

### Permission Checking

```python
def has_permission(user_id: int, permission: str) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        user_id: User ID
        permission: Permission string (e.g., 'courses.create')

    Returns:
        True if user has permission, False otherwise
    """
    # Get user role
    db = DatabaseManager()
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    db.close()

    if not result:
        return False

    role = result[0]

    # Admin has all permissions
    if role == 'admin':
        return True

    # Check role permissions
    role_permissions = ROLES.get(role, {}).get('permissions', [])

    # Wildcard permission
    if role_permissions == '*':
        return True

    # Exact match or wildcard match
    return (
        permission in role_permissions or
        permission.split('.')[0] + '.*' in role_permissions
    )
```

### Permission Decorator

```python
from functools import wraps
from infrastructure.auth.permissions import has_permission
from infrastructure.exceptions import AuthorizationException

def require_permission(permission: str):
    """
    Decorator to require a specific permission.

    Usage:
        @require_permission('courses.create')
        def create_course(user_id, course_data):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract user_id from arguments
            user_id = kwargs.get('user_id') or args[0]

            if not has_permission(user_id, permission):
                raise AuthorizationException(
                    f"User {user_id} does not have permission: {permission}"
                )

            return func(*args, **kwargs)
        return wrapper
    return decorator
```

## Role-Based Access Control

### User Roles

| Role     | Access Level | Description                              |
|----------|-------------|------------------------------------------|
| Admin    | Full        | Complete system access                   |
| Faculty  | High        | Course and student management            |
| Student  | Limited     | Personal records and course enrollment   |
| Staff    | Medium      | Module-specific operations               |

### Role Assignment

```python
def assign_role(user_id: int, role: str, assigned_by: int):
    """
    Assign a role to a user.

    Args:
        user_id: User to assign role to
        role: Role name
        assigned_by: User ID performing the assignment

    Raises:
        ValueError: If role is invalid
        AuthorizationException: If assigner lacks permission
    """
    # Validate role
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role}")

    # Check permission
    if not has_permission(assigned_by, 'users.manage'):
        raise AuthorizationException("Insufficient permissions to assign roles")

    # Update user role
    with get_db_transaction() as (conn, cursor):
        cursor.execute("""
            UPDATE users
            SET role = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (role, user_id))

        # Log the role change
        cursor.execute("""
            INSERT INTO audit_log (user_id, event_type, event_description, metadata)
            VALUES (?, 'role.assigned', 'Role assigned to user', ?)
        """, (
            assigned_by,
            json.dumps({
                'target_user_id': user_id,
                'new_role': role
            })
        ))
```

## Implementation Examples

### CLI Authentication

```python
# modules/interfaces/cli/main.py
from infrastructure.auth.auth_system import authenticate, create_session

def login_cli():
    """CLI login flow."""
    username = input("Username: ")
    password = getpass.getpass("Password: ")

    try:
        user_info = authenticate(username, password)

        if user_info:
            session_token = create_session(user_info['id'])
            print(f"Login successful! Welcome, {user_info['username']}")
            return user_info, session_token
        else:
            print("Invalid credentials")
            return None, None

    except Exception as e:
        print(f"Login error: {e}")
        return None, None
```

### GUI Authentication

```python
# modules/interfaces/gui/login_gui.py
import tkinter as tk
from tkinter import messagebox
from infrastructure.auth.auth_system import authenticate, create_session

class LoginWindow:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("University System - Login")

        # Username field
        tk.Label(self.window, text="Username:").grid(row=0, column=0)
        self.username_entry = tk.Entry(self.window)
        self.username_entry.grid(row=0, column=1)

        # Password field
        tk.Label(self.window, text="Password:").grid(row=1, column=0)
        self.password_entry = tk.Entry(self.window, show="*")
        self.password_entry.grid(row=1, column=1)

        # Login button
        tk.Button(self.window, text="Login", command=self.login).grid(row=2, column=1)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        try:
            user_info = authenticate(username, password)

            if user_info:
                session_token = create_session(user_info['id'])
                messagebox.showinfo("Success", f"Welcome, {user_info['username']}!")
                self.window.destroy()
                # Open main application window
            else:
                messagebox.showerror("Error", "Invalid credentials")

        except Exception as e:
            messagebox.showerror("Error", f"Login failed: {e}")
```

### Web API Authentication

```python
# modules/web/app.py
from flask import Flask, request, jsonify, session
from infrastructure.auth.auth_system import authenticate, create_session, validate_session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """API endpoint for user login."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400

    try:
        user_info = authenticate(
            username,
            password,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )

        if user_info:
            session_token = create_session(
                user_info['id'],
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )

            return jsonify({
                'success': True,
                'token': session_token,
                'user': {
                    'id': user_info['id'],
                    'username': user_info['username'],
                    'role': user_info['role']
                }
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401

    except Exception as e:
        return jsonify({'error': 'Authentication failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """API endpoint for user logout."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if token:
        invalidate_session(token)

    return jsonify({'success': True})

# Authentication middleware
@app.before_request
def authenticate_request():
    """Validate session for protected endpoints."""
    # Skip auth for public endpoints
    if request.path.startswith('/api/auth/login'):
        return

    # Extract token
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        return jsonify({'error': 'Missing authentication token'}), 401

    # Validate session
    user_info = validate_session(token)

    if not user_info:
        return jsonify({'error': 'Invalid or expired session'}), 401

    # Attach user info to request
    request.user = user_info
```

## Security Features

### Account Lockout

Protect against brute force attacks:

```python
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 1800  # 30 minutes in seconds

def check_account_lockout(username: str) -> Optional[datetime]:
    """
    Check if account is locked.

    Returns:
        Lock expiration time if locked, None if not locked
    """
    db = DatabaseManager()
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT account_locked_until
        FROM users
        WHERE username = ?
    """, (username,))

    result = cursor.fetchone()
    db.close()

    if not result or not result[0]:
        return None

    locked_until = datetime.fromisoformat(result[0])

    # Check if lock expired
    if locked_until < datetime.now():
        # Clear the lock
        unlock_account(username)
        return None

    return locked_until

def handle_failed_login(username: str):
    """Handle a failed login attempt."""
    with get_db_transaction() as (conn, cursor):
        # Increment failed attempts
        cursor.execute("""
            UPDATE users
            SET failed_login_attempts = failed_login_attempts + 1
            WHERE username = ?
        """, (username,))

        # Check if we should lock the account
        cursor.execute("""
            SELECT failed_login_attempts
            FROM users
            WHERE username = ?
        """, (username,))

        attempts = cursor.fetchone()[0]

        if attempts >= MAX_FAILED_ATTEMPTS:
            # Lock the account
            locked_until = datetime.now() + timedelta(seconds=LOCKOUT_DURATION)
            cursor.execute("""
                UPDATE users
                SET account_locked_until = ?
                WHERE username = ?
            """, (locked_until, username))

            # Log the lockout
            cursor.execute("""
                INSERT INTO audit_log (event_type, event_description, metadata)
                VALUES ('account.locked', 'Account locked due to failed login attempts', ?)
            """, (json.dumps({'username': username, 'attempts': attempts}),))
```

### Audit Logging

Log all authentication events:

```python
def log_auth_event(event_type: str, user_id: int = None, username: str = None,
                   success: bool = True, ip_address: str = None, metadata: dict = None):
    """
    Log an authentication event.

    Args:
        event_type: Type of event (e.g., 'login', 'logout', 'password_change')
        user_id: User ID (if authenticated)
        username: Username (for failed attempts)
        success: Whether the operation succeeded
        ip_address: Client IP address
        metadata: Additional event data
    """
    with get_db_transaction() as (conn, cursor):
        cursor.execute("""
            INSERT INTO audit_log (
                user_id, event_type, event_description,
                success, ip_address, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            f'auth.{event_type}',
            f'Authentication event: {event_type}',
            success,
            ip_address,
            json.dumps(metadata or {})
        ))
```

## API Reference

### Core Functions

#### `authenticate(username, password, ip_address=None, user_agent=None)`

Authenticate a user with username and password.

**Parameters:**
- `username` (str): Username
- `password` (str): Password (plaintext, will be hashed)
- `ip_address` (str, optional): Client IP address
- `user_agent` (str, optional): Client user agent

**Returns:**
- `dict`: User info if successful, None if failed

**Raises:**
- `AuthenticationException`: If account is locked

#### `create_session(user_id, ip_address=None, user_agent=None)`

Create a new session for a user.

**Parameters:**
- `user_id` (int): User ID
- `ip_address` (str, optional): Client IP address
- `user_agent` (str, optional): Client user agent

**Returns:**
- `str`: Session token

#### `validate_session(session_token)`

Validate a session token.

**Parameters:**
- `session_token` (str): Session token to validate

**Returns:**
- `dict`: User info if valid, None if invalid

#### `invalidate_session(session_token)`

Invalidate a session.

**Parameters:**
- `session_token` (str): Session token to invalidate

#### `has_permission(user_id, permission)`

Check if a user has a specific permission.

**Parameters:**
- `user_id` (int): User ID
- `permission` (str): Permission string

**Returns:**
- `bool`: True if user has permission

## Troubleshooting

### Common Issues

**Account Locked**
```
Error: "Account is locked until YYYY-MM-DD HH:MM:SS"

Solution:
1. Wait for lockout period to expire, or
2. Admin can manually unlock:
   UPDATE users SET account_locked_until = NULL, failed_login_attempts = 0
   WHERE username = 'username';
```

**Session Expired**
```
Error: "Session expired or invalid"

Solution:
1. User must log in again
2. Increase SESSION_TIMEOUT if sessions expire too quickly
3. Check for clock synchronization issues
```

**Permission Denied**
```
Error: "User does not have permission: courses.create"

Solution:
1. Check user role
2. Verify role has required permission in ROLES definition
3. Assign appropriate role if needed
```

### Debug Mode

Enable authentication debugging:

```python
# In config or environment
AUTH_DEBUG = True

# This will log detailed auth information
if AUTH_DEBUG:
    logger.debug(f"Authenticating user: {username}")
    logger.debug(f"User role: {role}")
    logger.debug(f"Required permission: {permission}")
    logger.debug(f"Has permission: {has_permission(user_id, permission)}")
```

## Best Practices

1. **Never Log Passwords**: Never log plaintext passwords or hashes
2. **Use HTTPS**: Always use HTTPS in production for web interfaces
3. **Secure Session Tokens**: Treat session tokens like passwords
4. **Regular Session Cleanup**: Clean up expired sessions regularly
5. **Monitor Failed Logins**: Alert on suspicious login patterns
6. **Strong Passwords**: Enforce password complexity requirements
7. **Multi-Factor Authentication**: Consider implementing 2FA for sensitive accounts
8. **Regular Audits**: Review audit logs regularly

## References

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [NIST Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)
- [PBKDF2 Specification](https://tools.ietf.org/html/rfc2898)

---

For questions or issues, contact the development team or see [SECURITY.md](SECURITY.md).
