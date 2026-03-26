# Secondary School Management System - Multi-Factor Authentication Guide

> Last Updated: March 2026

## Overview

Multi-Factor Authentication (MFA) adds a second layer of security to user accounts beyond the password. The Secondary School Management System supports MFA through the shared authentication module, offering TOTP (Time-based One-Time Password) and email OTP methods.

MFA is strongly recommended for all staff accounts (admin and teacher roles) and can be optionally enabled for student accounts.

## Supported MFA Methods

### TOTP (Time-based One-Time Password)

TOTP generates a 6-digit code that changes every 30 seconds, using a shared secret between the server and an authenticator app on the user's device.

**Compatible authenticator apps:**

- Google Authenticator (Android/iOS)
- Microsoft Authenticator (Android/iOS)
- Authy (Android/iOS/Desktop)
- Any TOTP-compatible app (RFC 6238)

**Technical details:**

- Algorithm: HMAC-SHA1 (standard TOTP)
- Code length: 6 digits
- Time step: 30 seconds
- Library: `pyotp`

### Email OTP

A one-time code is sent to the user's registered email address. This method is available as a fallback when TOTP is not set up.

**Note:** Email OTP is less secure than TOTP because it depends on the security of the user's email account. TOTP is the preferred method for staff accounts.

## Setting Up MFA

### Via the GUI

1. Log in to the Secondary School system.
2. Navigate to **Settings** (or click your username in the top-right corner).
3. Select **Security** or **Multi-Factor Authentication**.
4. Click **Enable MFA**.
5. A QR code is displayed on screen.
6. Open your authenticator app and scan the QR code.
   - Alternatively, click **Show manual key** and enter the text code into your app.
7. Enter the 6-digit code shown in your authenticator app to verify setup.
8. MFA is now active. A set of recovery codes is displayed.
9. **Save your recovery codes** in a secure location. These are shown only once.

### Via the CLI

```bash
python -m secondary_school.cli mfa enable --username <username>
```

The CLI will:

1. Display the TOTP secret as a text string (suitable for manual entry into an authenticator app).
2. Prompt for a verification code to confirm setup.
3. Display recovery codes on successful verification.

## Login with MFA

Once MFA is enabled, the login flow adds a second step:

1. Enter your username and password as normal.
2. If credentials are valid, a second prompt appears requesting your MFA code.
3. Open your authenticator app and enter the current 6-digit code.
4. If the code is valid, login proceeds.

The TOTP code is valid for the current 30-second window plus one window before and after (to account for minor clock drift).

## Recovery Codes

Recovery codes provide emergency access to your account if you lose access to your authenticator app (e.g., lost or replaced phone).

### Key Facts

- **10 recovery codes** are generated when MFA is first enabled.
- Each code is **single-use** -- once used, it cannot be used again.
- Recovery codes are displayed **only once** at setup time. Store them securely.
- Used codes are marked in the database (`is_used = 1`).
- Recovery codes are hashed before storage -- the system cannot display them again after initial setup.

### Using a Recovery Code

1. On the MFA code prompt during login, select **Use recovery code** (or enter a recovery code in place of the TOTP code).
2. Enter one of your unused recovery codes.
3. Login proceeds. That recovery code is now consumed.
4. After logging in, set up a new authenticator app or generate new recovery codes immediately.

### Regenerating Recovery Codes

If you have used most of your recovery codes or suspect they have been compromised:

1. Log in to your account.
2. Go to **Settings > Security > Multi-Factor Authentication**.
3. Click **Regenerate Recovery Codes**.
4. A new set of 10 codes is generated. All previous unused codes are invalidated.
5. Save the new codes in a secure location.

## Disabling MFA

### Self-Service (User)

1. Log in (you will need your current MFA code or a recovery code).
2. Go to **Settings > Security > Multi-Factor Authentication**.
3. Click **Disable MFA**.
4. Confirm by entering your current password.
5. MFA is removed. The TOTP secret and unused recovery codes are deleted from the database.

### Administrator Override

Administrators can disable MFA for a user account (e.g., if a user has lost both their authenticator device and all recovery codes):

**Via GUI:**
1. Go to **Administration > User Management**.
2. Select the user account.
3. Click **Disable MFA**.
4. Confirm the action.

**Via CLI:**
```bash
python -m secondary_school.cli mfa disable --username <username> --admin
```

This action is recorded in the audit log with the administrator's identity.

## Troubleshooting

### "Invalid MFA code" errors

| Possible Cause | Solution |
|----------------|----------|
| Clock out of sync | Ensure your device's time is set to automatic/network time. TOTP depends on accurate clocks. |
| Wrong account in app | Verify you are reading the code for the correct account (check the label in your authenticator app). |
| Code expired | Wait for the next code. Each code is valid for approximately 30 seconds. |
| MFA not fully set up | The verification step during setup may not have completed. Disable and re-enable MFA. |

### Lost authenticator device

1. Use one of your saved recovery codes to log in.
2. After logging in, disable MFA and re-enable it with your new device.
3. If you have no recovery codes, contact a system administrator to disable MFA on your account.

### Locked out of account

If you cannot log in due to MFA issues and have no recovery codes:

1. Contact a system administrator.
2. The administrator can disable MFA for your account (see Administrator Override above).
3. You will be asked to verify your identity through an alternative method (e.g., in person with photo ID).
4. Once MFA is disabled, log in with your password and re-enable MFA with a new authenticator setup.

### Recovery codes not working

- Ensure you are entering the code exactly as shown (codes are case-sensitive).
- Verify the code has not already been used. Each code works only once.
- If all codes are used, contact an administrator for an MFA reset.

## Recommendations

### For Administrators

1. **Mandate MFA for all staff accounts** -- both admin and teacher roles should have MFA enabled as a matter of policy.
2. **Provide setup guidance** during staff onboarding, including how to install an authenticator app.
3. **Keep a secure process** for MFA resets. Require in-person identity verification before disabling MFA for a user.
4. **Audit MFA status** regularly. Review which accounts have MFA disabled and follow up.
5. **Train staff on recovery codes** -- ensure they understand the importance of saving codes securely.

### For Users

1. **Use TOTP over email OTP** when possible. It is more secure and does not depend on email availability.
2. **Save recovery codes** in a secure location separate from your device (e.g., a locked drawer, a password manager).
3. **Do not share recovery codes** or screenshots of your QR code.
4. **If you change phones**, disable MFA before wiping the old device, then re-enable on the new device. Alternatively, use your recovery codes to log in and set up the new device.
5. **Report suspected account compromise** to an administrator immediately.

## Technical Reference

### Database Tables (in `auth.db`)

**`mfa_secrets`**: Stores the TOTP shared secret per user.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `user_id` | INTEGER | FK to `users.id` |
| `secret` | TEXT | TOTP shared secret (base32 encoded) |
| `is_enabled` | INTEGER | 1 if MFA is active, 0 if disabled |
| `created_at` | TIMESTAMP | When MFA was set up |

**`mfa_recovery_codes`**: Stores hashed recovery codes.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `user_id` | INTEGER | FK to `users.id` |
| `code` | TEXT | Hashed recovery code |
| `is_used` | INTEGER | 1 if consumed, 0 if available |
| `created_at` | TIMESTAMP | When the code was generated |

### TOTP Verification (Code Flow)

```python
import pyotp

def verify_totp(secret, code):
    """Verify a TOTP code with a +/- 1 window tolerance."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
```

The `valid_window=1` parameter accepts codes from the previous, current, and next 30-second intervals, accommodating up to 30 seconds of clock drift.
