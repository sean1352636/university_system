# Multi-Factor Authentication (MFA) Guide

This guide covers MFA as implemented in the shared authentication module (`education_system/shared/auth/mfa_service.py`), which is used by all four systems.

---

## Overview

MFA adds a second verification step after password authentication. Even if a password is compromised, the account remains protected.

## Supported Methods

### TOTP (Authenticator App)

The primary MFA method. Works with any TOTP-compatible app:

- Google Authenticator
- Microsoft Authenticator
- Authy
- 1Password, Bitwarden, etc.

Setup produces a QR code that the user scans with their authenticator app. Codes rotate every 30 seconds.

### Recovery Codes

On MFA setup, a set of one-time recovery codes is generated and stored (hashed) in the `mfa_recovery_codes` table. Each code can only be used once.

## Setup Flow

1. User navigates to account settings and selects "Enable MFA"
2. System generates a TOTP secret and displays a QR code
3. User scans the QR code with their authenticator app
4. User enters the current 6-digit code to verify setup
5. System stores the secret in `mfa_secrets` and generates recovery codes
6. Recovery codes are displayed once — user must save them

## Login Flow with MFA

1. User enters username and password
2. If credentials are valid and MFA is enabled, the login pauses
3. User is prompted for a 6-digit TOTP code (or a recovery code)
4. On successful verification, the session is created

## Admin Management

Administrators can:

- View which users have MFA enabled
- Reset/disable MFA for a user (e.g. if they lose their device)
- Enforce MFA for specific roles

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Code rejected | Check device clock is synced (TOTP is time-based) |
| Lost authenticator | Use a recovery code, then re-enroll MFA |
| No recovery codes | Contact an administrator to reset MFA |

## Technical Details

- Secret storage: `mfa_secrets` table, linked by `user_id`
- Recovery codes: hashed with bcrypt in `mfa_recovery_codes`
- TOTP implementation: `pyotp` library
- Code validity window: 30 seconds (standard)

---

See also: [Shared Authentication](AUTHENTICATION.md) | [Universal Login](UNIVERSAL_LOGIN.md)
