# Multi-Factor Authentication (MFA) Guide

This guide covers the setup, usage, and management of Multi-Factor Authentication in the Sixth Form College Management System. All details are based on the actual implementation in `infrastructure/auth/mfa_service.py` and `api/auth.py`.

---

## Table of Contents

1. [What is MFA and Why It Matters](#what-is-mfa-and-why-it-matters)
2. [Supported Methods](#supported-methods)
3. [Setting Up MFA](#setting-up-mfa)
4. [Backup Recovery Codes](#backup-recovery-codes)
5. [Login Flow with MFA](#login-flow-with-mfa)
6. [Admin Management of MFA](#admin-management-of-mfa)
7. [Troubleshooting](#troubleshooting)
8. [API Endpoints for MFA Operations](#api-endpoints-for-mfa-operations)

---

## What is MFA and Why It Matters

Multi-Factor Authentication adds a second layer of verification beyond the username and password. Even if a password is compromised through phishing, credential stuffing, or a data breach, an attacker cannot access the account without the second factor.

For a college management system, MFA is particularly important because the system handles:

- **Student personal data** -- names, contact information, medical records, safeguarding notes.
- **Academic records** -- grades, attendance, assessment results, progress reports.
- **Financial information** -- bursary details, fee records, payment data.
- **Staff HR data** -- employment records, payroll information, CPD records.
- **Safeguarding records** -- sensitive child protection information that must be protected by law.

MFA should be enabled for all admin and staff accounts at minimum. It is strongly recommended for any account with access to sensitive data.

---

## Supported Methods

### TOTP (Time-Based One-Time Password)

The system uses TOTP as its MFA method, implemented via the `pyotp` library. TOTP generates a 6-digit code that changes every 30 seconds, based on a shared secret and the current time.

Compatible authenticator applications include:

- Google Authenticator (Android, iOS)
- Microsoft Authenticator (Android, iOS)
- Authy (Android, iOS, Desktop)
- 1Password, Bitwarden, and other password managers with TOTP support
- Any application that supports the TOTP standard (RFC 6238)

---

## Setting Up MFA

### Step 1: Generate MFA Secret

MFA setup is initiated through the `MFAService.setup_totp()` method. This performs the following actions:

1. Removes any existing MFA configuration for the user (allowing a fresh setup).
2. Generates a new random Base32-encoded TOTP secret using `pyotp.random_base32()`.
3. Creates a provisioning URI with the issuer name "College Management System".
4. Generates 10 single-use backup recovery codes.
5. Stores the TOTP secret in the `mfa_secrets` database table with `is_enabled = 1`.
6. Stores SHA-256 hashes of the recovery codes in the `mfa_recovery_codes` table.

The method returns:

```python
{
    "secret": "BASE32ENCODEDSECRET",
    "provisioning_uri": "otpauth://totp/College%20Management%20System:username?secret=...&issuer=...",
    "recovery_codes": ["ABCD-1234", "EFGH-5678", ...]
}
```

### Step 2: Add to Authenticator App

Use one of these methods to add the account to your authenticator app:

**QR Code method (recommended):**
- The `provisioning_uri` can be rendered as a QR code.
- Open your authenticator app and select "Add account" or "Scan QR code".
- Scan the QR code with your phone camera.

**Manual entry method:**
- Open your authenticator app and select "Add account" or "Enter manually".
- Enter the account name (your username).
- Enter the Base32 secret key returned in the `secret` field.
- Ensure the type is set to "Time-based" (not counter-based).

### Step 3: Verify Setup

After adding the account to your authenticator app, verify the setup by entering the current 6-digit code displayed in the app. The system verifies the code using `MFAService.verify_totp()` with a 1-step time window tolerance (allowing codes from the previous, current, and next 30-second windows).

---

## Backup Recovery Codes

### What Are Recovery Codes

Recovery codes are single-use backup codes that allow you to log in when you do not have access to your authenticator app. They are generated during MFA setup.

### Code Format

Each recovery code follows the format `XXXX-XXXX`, where each character is a random uppercase letter (`A-Z`) or digit (`0-9`). Codes are generated using Python's `secrets` module for cryptographic randomness.

### Number of Codes

The system generates **10 recovery codes** at setup time (defined by `MFAService.RECOVERY_CODE_COUNT`).

### How Codes Are Stored

- Recovery codes are **never stored in plaintext** in the database.
- Each code is hashed using SHA-256 before storage in the `mfa_recovery_codes` table.
- The plaintext codes are shown to the user **only once** during setup. They cannot be retrieved later.

### Using a Recovery Code

1. At the MFA verification prompt, enter a recovery code instead of a TOTP code.
2. The system normalizes the code (strips whitespace, converts to uppercase) and computes its SHA-256 hash.
3. If the hash matches an unused code in the database (`is_used = 0`), the code is accepted.
4. The code is then marked as used (`is_used = 1`) and cannot be used again.
5. Login proceeds as normal.

### Checking Remaining Codes

The `MFAService.get_remaining_recovery_codes(user_id)` method returns the count of unused recovery codes for a user. Monitor this count and regenerate codes before they run out.

### Regenerating Recovery Codes

To regenerate recovery codes, run `MFAService.setup_totp()` again. This will:

- Delete all existing MFA data (TOTP secret and recovery codes).
- Generate a new TOTP secret and a fresh set of 10 recovery codes.
- Require the user to reconfigure their authenticator app with the new secret.

### Storing Recovery Codes Safely

- Print or write down the codes and store them in a secure physical location.
- Alternatively, store them in an encrypted password manager.
- Do not store recovery codes alongside your password.
- Do not share recovery codes with anyone.

---

## Login Flow with MFA

When MFA is enabled for a user, the login process has two phases:

### Phase 1: Password Verification

1. User submits username and password.
2. The system validates the password as usual (checking lockout, verifying bcrypt hash).
3. If the password is correct, the system checks `MFAService.is_mfa_enabled(user_id)`.
4. If MFA is enabled, the system returns:

```python
{
    "mfa_required": True,
    "user_id": 42,
    "username": "jdoe"
}
```

No session token is created at this stage. The user is not yet authenticated.

### Phase 2: MFA Verification

5. The user is prompted for their MFA code.
6. The user enters either:
   - A 6-digit TOTP code from their authenticator app, or
   - A recovery code in `XXXX-XXXX` format.
7. The system calls `UserAuth.verify_mfa(user_id, code)`, which:
   - First attempts TOTP verification (`verify_totp`).
   - If TOTP fails, attempts recovery code verification (`verify_recovery_code`).
   - If both fail, raises `AuthError("Invalid MFA code.")`.
8. On success, a session token is created and the user is fully authenticated.

### API Login Flow

For API-based login, the flow uses JWT tokens:

1. POST to the login endpoint with username and password.
2. If MFA is required, the API returns an MFA token (a short-lived JWT with `purpose: "mfa_verify"` that expires in 5 minutes).
3. POST to the MFA verification endpoint with the MFA token in the `Authorization: Bearer` header and the TOTP/recovery code in the request body.
4. On success, the API returns a full JWT session token (valid for 24 hours by default).

The MFA token is validated by the `@mfa_token_required` decorator, which checks:
- The token is valid and not expired.
- The `purpose` field equals `"mfa_verify"` (preventing regular session tokens from being used for MFA verification).

---

## Admin Management of MFA

### Checking MFA Status

Administrators can check whether MFA is enabled for a user:

```python
mfa_service = MFAService(db_path)
is_enabled = mfa_service.is_mfa_enabled(user_id)
```

This queries the `mfa_secrets` table for the user and checks the `is_enabled` flag.

### Enabling MFA for a User

MFA is enabled during setup. Call `setup_totp()` with the user's ID and username:

```python
result = mfa_service.setup_totp(user_id=42, username="jdoe")
# Provide result["secret"], result["provisioning_uri"], and
# result["recovery_codes"] to the user securely.
```

The TOTP secret is stored with `is_enabled = 1` immediately.

### Disabling MFA for a User

Administrators can disable MFA using `disable_mfa()`:

```python
mfa_service.disable_mfa(user_id=42)
```

This method:
- Deletes the user's TOTP secret from the `mfa_secrets` table.
- Deletes all recovery codes from the `mfa_recovery_codes` table.
- Raises `MFAError` if MFA was not set up for the user.

After disabling, the user will log in with only username and password.

### Resetting MFA

To reset MFA (e.g., when a user gets a new phone), call `setup_totp()` again. This deletes the old configuration and creates a new one. The user must reconfigure their authenticator app.

### Monitoring Recovery Code Usage

Track remaining recovery codes to identify users who may need assistance:

```python
remaining = mfa_service.get_remaining_recovery_codes(user_id=42)
if remaining <= 2:
    # Alert the user to regenerate codes
    ...
```

---

## Troubleshooting

### Lost or Replaced Device

**Problem:** The user no longer has access to their authenticator app.

**Solution:**
1. Use a backup recovery code to log in.
2. Once logged in, disable MFA and set it up again with the new device.
3. If no recovery codes are available, an administrator must disable MFA for the user:
   ```python
   mfa_service.disable_mfa(user_id)
   ```
4. The user can then log in with just their password and re-enable MFA.

### Invalid TOTP Code

**Problem:** The 6-digit code from the authenticator app is rejected.

**Possible causes and solutions:**

- **Clock drift:** TOTP is time-based. If the device clock is more than 30 seconds off, codes will be invalid. The system allows a 1-step window tolerance (plus or minus 30 seconds), but larger discrepancies will fail.
  - Ensure the device clock is synchronized (enable automatic time on your phone).
  - On Android: Settings > System > Date & Time > Set time automatically.
  - On iOS: Settings > General > Date & Time > Set Automatically.

- **Wrong account:** If multiple TOTP accounts are configured, ensure you are reading the code for "College Management System".

- **Expired code:** TOTP codes change every 30 seconds. If the code is about to expire (timer nearly at zero), wait for the next code.

- **Mistyped code:** Ensure all 6 digits are entered correctly with no spaces.

### Recovery Code Not Working

**Problem:** A recovery code is rejected.

**Possible causes and solutions:**

- **Already used:** Each recovery code can only be used once. Check if it has been used previously. Used codes are marked with `is_used = 1` in the database.
- **Case sensitivity:** Codes are normalized to uppercase automatically, so case should not be an issue.
- **Formatting:** Ensure the code is entered in the correct `XXXX-XXXX` format, or at minimum contains the right characters (whitespace is stripped automatically).
- **No remaining codes:** Use `get_remaining_recovery_codes()` to check how many unused codes remain. If zero, an admin must reset MFA.

### MFA Setup Fails

**Problem:** The `setup_totp()` call raises an `MFAError`.

**Possible causes:**

- **Database error:** Ensure the `mfa_secrets` and `mfa_recovery_codes` tables exist in the database.
- **Missing dependency:** Ensure `pyotp` is installed (`pip install pyotp`).

### Account Locked During MFA

**Problem:** The user entered the wrong password too many times before reaching the MFA step.

**Solution:** Account lockout applies to the password phase only. Wait 15 minutes for the lockout to expire, or have an administrator clear the lockout by resetting `locked_until` and `failed_login_attempts` in the `users` table.

---

## API Endpoints for MFA Operations

The following describes the MFA-related API interactions based on the authentication infrastructure.

### Login (Phase 1)

```
POST /api/auth/login
Content-Type: application/json

{
    "username": "jdoe",
    "password": "SecureP@ss1"
}
```

**Response when MFA is required:**

```json
{
    "mfa_required": true,
    "mfa_token": "<short-lived-jwt>",
    "message": "MFA verification required."
}
```

The `mfa_token` is a JWT valid for 5 minutes with `purpose: "mfa_verify"`.

### MFA Verification (Phase 2)

```
POST /api/auth/mfa/verify
Authorization: Bearer <mfa_token>
Content-Type: application/json

{
    "code": "123456"
}
```

Or with a recovery code:

```
POST /api/auth/mfa/verify
Authorization: Bearer <mfa_token>
Content-Type: application/json

{
    "code": "ABCD-1234"
}
```

**Success response:**

```json
{
    "token": "<full-session-jwt>",
    "user": {
        "user_id": 42,
        "username": "jdoe",
        "role": "staff"
    }
}
```

### MFA Setup

```
POST /api/auth/mfa/setup
Authorization: Bearer <session-jwt>
```

**Response:**

```json
{
    "secret": "BASE32ENCODEDSECRET",
    "provisioning_uri": "otpauth://totp/College%20Management%20System:jdoe?secret=...&issuer=...",
    "recovery_codes": [
        "ABCD-1234",
        "EFGH-5678",
        "..."
    ]
}
```

### Disable MFA

```
DELETE /api/auth/mfa
Authorization: Bearer <session-jwt>
```

**Response:**

```json
{
    "message": "MFA disabled successfully."
}
```

### Check MFA Status

```
GET /api/auth/mfa/status
Authorization: Bearer <session-jwt>
```

**Response:**

```json
{
    "mfa_enabled": true,
    "remaining_recovery_codes": 8
}
```

---

## Summary

| Item | Detail |
|---|---|
| MFA method | TOTP (RFC 6238) via `pyotp` |
| Code length | 6 digits |
| Code validity window | Current period +/- 1 step (30 seconds each) |
| Recovery codes | 10 codes in `XXXX-XXXX` format |
| Recovery code storage | SHA-256 hashed |
| Recovery code usage | Single-use (marked as used after consumption) |
| MFA token expiry | 5 minutes |
| Session token expiry (API) | 24 hours |
| Session token expiry (GUI/CLI) | 30 minutes |
| Issuer name | "College Management System" |
