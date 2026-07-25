# Universal Login

The Universal Login window provides a single entry point for all four Education System subsystems.

Source: `education_system/shared/gui/login_gui.py` (`UniversalLoginWindow`)

---

## How It Works

1. **Authentication** — User enters their username and password. Credentials are verified against the shared auth database (`shared/data/db_files/auth.db`).
2. **MFA challenge** — If MFA is enabled, the user is prompted for a TOTP code or recovery code.
3. **System selection** — After authentication, the window displays colour-coded buttons for each system the user has access to (based on their `user_systems` entries).
4. **Launch** — The selected system's GUI or CLI is launched with the authenticated session, skipping any local login screen.

## System Colours

| System | Colour |
|--------|--------|
| University | Blue |
| College | Green |
| Secondary School | Purple |
| Primary School | Orange |

## Entry Point

The top-level `run.py` launches `UniversalLoginWindow` for GUI mode. After a successful login and system selection, it passes `user_info`, `role`, and `shared_auth` to the chosen system's launcher, which skips its own login screen.

## Returned Attributes

After successful login and system selection, `UniversalLoginWindow` exposes:

| Attribute | Description |
|-----------|-------------|
| `user_info` | Dict returned by `UserAuth.login()` |
| `system_key` | e.g. `"college"`, `"school"`, `"primary"` |
| `system_role` | The user's role in the chosen system |
| `auth` | The `UserAuth` instance with an active session |

---

See also: [Shared Authentication](AUTHENTICATION.md) | [MFA Guide](MFA_GUIDE.md)
