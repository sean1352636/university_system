# Idle / Inactivity Auto-Logout — Primary School System

The Primary School GUI and CLI log a signed-in user out after a period of inactivity
and return to the login screen. Lock the workstation as well when you walk
away: the default leaves a screen open for up to 30 minutes.

---

## Summary

| Interface | Idle logout | Installed in |
|-----------|-------------|--------------|
| GUI | 30 minutes | `src/education_system/systems/primary/gui_main.py` (`PrimarySchoolMainGUI.__init__`) |
| CLI | 30 minutes, on Unix | `src/education_system/systems/primary/cli_main.py` (`run_authenticated()`) |

Set `EDU_IDLE_TIMEOUT_MINUTES` to change the period, or to `0` to turn idle
logout off. The same setting covers Primary, Secondary, Nursery and FE College.
An invalid or negative value uses the default.

Separately, each session row in `auth.db` has an expiry, set at login from
`SESSION_TIMEOUT_MINUTES` (30 by default, `EDU_SESSION_TIMEOUT` to change). A
token past that time fails validation, but this does not close the window or
end the CLI.

---

## How it works

### GUI

`install_idle_logout` in `platform/delivery/gui/idle_timeout.py`:

- Treats any mouse movement, key press, click or wheel event, in any window of
  the application, as activity.
- Checks every 30 seconds whether the period has passed.
- Then runs the same `_logout` as the Logout button, followed by a notice saying
  why you were signed out. The notice comes second so that an unattended session
  has already ended, and its window has closed, while the notice waits for OK.
- Cancels its pending check when the main window is destroyed, however that
  happens.

### CLI

`idle_session` in `platform/delivery/cli/cli_helpers.py` times every prompt in
the signed-in session with `signal.SIGALRM`, including `input()` and `getpass`
prompts in individual screens. If nobody answers in time, it prints a message,
runs the same `_logout` as the **L** key, and returns to the login prompt.

The timer runs only while waiting at a prompt, so a long-running report is not
interrupted. The login prompt itself is not timed.

> **Platform note:** `signal.SIGALRM` is Unix-only, so on Windows the CLI does
> not log out idle users. The GUI works on all platforms.

---

## Security rationale

| Risk | Mitigation |
|------|------------|
| Shared classroom workstation left logged in between lessons | Logged out after the idle period |
| Staffroom laptop forgotten at break time | Same; also use the operating system's screen lock |
| Remote-desktop session left open overnight | The GUI logs out regardless of who is at the keyboard |
| Forgotten SSH/CLI session | The CLI logs out at its prompt (Unix) |

---

## Implementation references

| Component | File |
|-----------|------|
| Setting | `src/education_system/platform/delivery/idle_settings.py` |
| Shared GUI helper | `src/education_system/platform/delivery/gui/idle_timeout.py` |
| Shared CLI helper | `src/education_system/platform/delivery/cli/cli_helpers.py` |
| Primary GUI entry point | `src/education_system/systems/primary/gui_main.py` |
| Primary CLI entry point | `src/education_system/systems/primary/cli_main.py` |

---

## Related documentation

- [`SECURITY.md`](SECURITY.md) — overall security architecture
- [`MFA_GUIDE.md`](MFA_GUIDE.md) — multi-factor authentication setup
- [`../guides/communication.md`](../guides/communication.md) — Communication guide (also references the timeout)
