# Idle / Inactivity Auto-Logout — College System

This document describes the session-timeout behaviour added in
**v8.74.0** for the Sixth Form College Management System. The same
mechanism is also installed in the Secondary and Primary subsystems
(see their respective `SESSION_TIMEOUT.md` files).

---

## Summary

The College GUI **and** CLI auto-log-out the active user after
**30 minutes of inactivity**. This protects against unattended
terminals exposing student data and is enabled by default — no
configuration is required.

| Interface | Default | Configurable in |
|-----------|---------|------------------|
| GUI | 30 minutes | `college_system/modules/shared/gui/main_gui.py` (`CollegeApp.__init__`) |
| CLI | 30 minutes | `college_system/modules/shared/cli/cli_main.py` (`main()`) |

---

## How activity is tracked

### GUI

The GUI uses the shared helper
`education_system.shared.gui.idle_timeout.attach_idle_timeout` which:

- Records a `last_activity` timestamp on the root window using `time.monotonic()`.
- Binds `<Motion>`, `<KeyPress>`, `<ButtonPress>`, and `<MouseWheel>`
  events via `bind_all` so any user interaction anywhere in the
  application resets the timer.
- Wakes up every 30 seconds via `root.after()` and checks
  `now - last_activity` against the configured timeout.
- On `WM_DELETE_WINDOW`, the watchdog is cancelled cleanly so no stray
  `after` callbacks fire into a destroyed root.

This is **real activity tracking** — a user clicking around stays
logged in indefinitely; only walking away triggers the logout.

### CLI

The CLI uses `education_system.shared.cli.cli_helpers.enable_idle_timeout`
which wraps the menu prompt (`get_choice`) in a `signal.SIGALRM` watchdog:

- Each call to `get_choice()` installs a fresh `SIGALRM` for `timeout * 60` seconds.
- If the user enters input within the window, the alarm is cancelled and the timer resets.
- If the alarm fires while waiting on `input()`, an internal exception unwinds the stack, the message is printed, the logout callback runs, and the process exits cleanly.
- The previous `SIGALRM` handler is restored in a `finally` block.

> **Note:** Long-running actions inside menu handlers (e.g. typing a
> long message body, browsing through a paginated report) are **not**
> bounded by the timeout. The clock starts again the next time you
> return to a menu prompt. In practice this means the timeout measures
> "time since the last menu navigation", which is close enough to
> idleness for most cases.

> **Platform note:** `signal.SIGALRM` is Unix-only. On Windows the CLI
> idle timeout is silently a no-op. The GUI watchdog works on all
> platforms because it uses tk events instead of signals.

---

## What the user sees on timeout

### GUI

1. A `Session Expired` warning dialog appears:
   > *You have been logged out due to inactivity.*
2. Click `OK`.
3. `auth.logout()` is called, the universal-login redirect is requested via `request_logout()`, and the main window is destroyed.

### CLI

```
⚠ Logged out after 30 minutes of inactivity.
```

The process then exits with status 0.

---

## Changing the default timeout

### GUI

Edit `CollegeApp.__init__` in
`education_system/college_system/modules/shared/gui/main_gui.py`:

```python
self._cancel_idle_timeout = attach_idle_timeout(
    self, self._idle_logout, timeout_minutes=30,  # ← change this
)
```

### CLI

Edit the `main()` function in
`education_system/college_system/modules/shared/cli/cli_main.py`:

```python
enable_idle_timeout(30, _idle_logout)  # ← change this
```

To **disable** the timeout entirely, set the value to `0` (the helper
treats anything `<= 0` as disabled) or call `disable_idle_timeout()`
directly in the CLI.

---

## Security rationale

| Risk | Mitigation |
|------|------------|
| Lab/staffroom workstation left unattended | Auto-logout after 30 min ensures the next user can't see the previous session's records |
| Remote-desktop session left open overnight | Same — the watchdog fires regardless of who is physically at the keyboard |
| Forgotten SSH/CLI session | The CLI watchdog kills the process, freeing locked DB connections |
| Long-running batch operation that legitimately needs more than 30 min | Timeout only applies between menu prompts, not inside an action's own `input()` calls |

---

## Implementation references

| Component | File |
|-----------|------|
| Shared GUI helper | `education_system/shared/gui/idle_timeout.py` |
| Shared CLI helper | `education_system/shared/cli/cli_helpers.py` |
| College GUI wiring | `education_system/college_system/modules/shared/gui/main_gui.py` |
| College CLI wiring | `education_system/college_system/modules/shared/cli/cli_main.py` |

---

## Related documentation

- [`SECURITY.md`](SECURITY.md) — overall college security architecture
- [`MFA_GUIDE.md`](MFA_GUIDE.md) — multi-factor authentication setup
- [`../guides/communication.md`](../guides/communication.md) — Communication guide (also references the timeout)
