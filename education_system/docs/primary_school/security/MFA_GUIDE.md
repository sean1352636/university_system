# Primary School MFA Guide

> Last Updated: March 2026

## Overview

Multi-Factor Authentication (MFA) adds a second layer of security to user accounts. Even if a password is compromised, an attacker cannot access the system without the second factor.

The Primary School system supports MFA through the shared authentication module (`education_system/shared/auth/`), which provides:

- **TOTP (Time-based One-Time Password)** via authenticator apps (Google Authenticator, Microsoft Authenticator, Authy, etc.)
- **Email OTP** as an alternative second factor
- **Recovery codes** for emergency access when the primary MFA method is unavailable

---

## Who Should Use MFA

| User Category | Recommendation |
|---|---|
| **Admin accounts** | **Required.** Admins have full system access including user management and data export. |
| **Safeguarding leads** | **Required.** These accounts can access sensitive safeguarding records about children. |
| **Teachers** | **Strongly recommended.** Teachers access pupil personal data and assessment records. |
| **superadmin** | **Required.** This account has access to all four Education System subsystems. |
| **Student accounts** | Optional. Typically not needed given limited access scope. |
| **Parent accounts** | Optional. Recommended if parents access sensitive pupil information remotely. |

---

## Setting Up MFA via GUI

### Step 1: Access MFA Settings

1. Log in to the Primary School system.
2. Navigate to your account settings or profile.
3. Select **Security** or **Multi-Factor Authentication**.
4. Click **Enable MFA**.

### Step 2: Choose Your Method

**TOTP (Authenticator App) -- Recommended:**

1. A QR code is displayed on screen.
2. Open your authenticator app (Google Authenticator, Microsoft Authenticator, Authy, or any TOTP-compatible app).
3. Scan the QR code, or manually enter the secret key shown below the QR code.
4. The app will begin generating 6-digit codes that refresh every 30 seconds.
5. Enter the current code from your app to verify setup.

**Email OTP:**

1. Select **Email** as your MFA method.
2. Confirm your email address.
3. A one-time code is sent to your email.
4. Enter the code to verify setup.

### Step 3: Save Recovery Codes

After enabling MFA, the system generates **recovery codes**. These are one-time-use codes that allow you to log in if you lose access to your authenticator app or email.

- **Write down or securely store these codes.** They are shown only once.
- Each code can be used exactly once.
- Store them separately from your device (e.g., in a locked drawer or password manager).
- A typical set includes 8-10 recovery codes.

Example recovery codes:

```
a7b2c-d9e4f
k3m8n-p1q6r
x5y0z-h2j7w
...
```

---

## Setting Up MFA via CLI

For administrators managing accounts in bulk or via scripting:

```bash
# Enable MFA for a specific user (interactive)
/home/seancatchpole989/venv/bin/python -m primary_school.cli mfa enable --username primary_admin

# Generate new recovery codes for a user
/home/seancatchpole989/venv/bin/python -m primary_school.cli mfa recovery --username primary_admin
```

---

## Logging In with MFA

Once MFA is enabled, the login flow adds a second step:

1. Enter your **username** and **password** as normal.
2. The system prompts for a **verification code**.
3. Open your authenticator app and enter the current 6-digit code.
   - Or enter a **recovery code** if your authenticator is unavailable.
   - Or enter the code sent to your **email** (if email OTP is configured).
4. If the code is valid, login completes.

The MFA prompt appears in the Universal Login Window (`run.py`) as well as direct system launches.

---

## Recovery Codes

Recovery codes are your backup access method. Use them when:

- Your phone is lost, broken, or unavailable.
- Your authenticator app is uninstalled or reset.
- Email delivery is delayed or failing (for email OTP users).

### Using a Recovery Code

1. At the MFA verification prompt, select **Use recovery code** (or enter the recovery code directly in the code field).
2. Enter one of your saved recovery codes.
3. The code is consumed and cannot be used again.

### Generating New Recovery Codes

If you are running low on recovery codes or suspect they have been compromised:

1. Log in to the system (you need at least one working MFA method or recovery code).
2. Go to **Account Settings** > **Security** > **MFA**.
3. Click **Regenerate Recovery Codes**.
4. **All previous recovery codes are invalidated.** Save the new codes securely.

---

## Disabling MFA

MFA can be disabled when necessary, but this is discouraged for staff accounts.

### Self-Service (User)

1. Log in to the system (MFA verification required).
2. Go to **Account Settings** > **Security** > **MFA**.
3. Click **Disable MFA**.
4. Confirm with your current password.
5. MFA is removed. Future logins require only username and password.

### Admin Override

Administrators can disable MFA for other users (e.g., if a user is locked out with no recovery codes):

1. Log in as admin.
2. Go to **Admin** > **User Management**.
3. Select the affected user.
4. Click **Reset MFA** or **Disable MFA**.
5. Advise the user to re-enable MFA and generate new recovery codes immediately.

This action is recorded in the audit log.

---

## Troubleshooting

### "Invalid code" when entering TOTP code

**Cause:** Clock synchronisation issue. TOTP codes are time-based and require the device clock to be accurate within approximately 30 seconds.

**Solution:**
- Ensure your phone's date and time are set to **automatic** (network-provided time).
- On Android: Settings > System > Date & time > Use network-provided time.
- On iOS: Settings > General > Date & Time > Set Automatically.
- If the clock is correct, try waiting for the next code (codes rotate every 30 seconds).

### Email OTP code not received

**Cause:** Email delivery delay, spam filtering, or misconfigured email settings.

**Solutions:**
1. Check your spam/junk folder.
2. Wait 2-3 minutes for delivery. Email can be slower than app-based TOTP.
3. Request a new code (if the interface allows resending).
4. Verify the email address on file is correct (ask an administrator).
5. Check that the system's email configuration is working (see [CONFIGURATION.md](../infrastructure/CONFIGURATION.md)).
6. Use a recovery code as a fallback.

### Lost authenticator app / new phone

**Solutions:**
1. Use a **recovery code** to log in.
2. Once logged in, disable MFA and re-enable it to register your new device.
3. If you have no recovery codes, contact your school administrator to perform an admin MFA reset.

### Locked out entirely (no password, no MFA)

This requires administrator intervention:

1. An admin resets the user's password via the admin panel.
2. The admin disables MFA for the account.
3. The user logs in with the new password.
4. The user sets a new password and re-enables MFA.
5. All steps are recorded in the audit log.

---

## Technical Details

### TOTP Specification

| Parameter | Value |
|---|---|
| Algorithm | HMAC-SHA1 (RFC 6238) |
| Digits | 6 |
| Period | 30 seconds |
| Library | `pyotp` |

### Storage

| Data | Location | Notes |
|---|---|---|
| TOTP secrets | `mfa_secrets` table in `auth.db` | Encrypted or hashed at rest. One secret per user. |
| Recovery codes | `mfa_recovery_codes` table in `auth.db` | Hashed. Consumed codes are deleted. |
| MFA status | `users` table flag in `auth.db` | Indicates whether MFA is enabled for the account. |

### Security Considerations

- TOTP secrets are generated using a cryptographically secure random number generator.
- Recovery codes are stored as hashed values; the plaintext is shown only once at generation time.
- MFA verification failures contribute to the account lockout counter (5 attempts, 15-minute lockout).
- All MFA-related operations (enable, disable, recovery code use, admin reset) are recorded in the audit log.
