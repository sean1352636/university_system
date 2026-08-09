# Idle / Inactivity Auto-Logout — Primary School System

This document describes the session-timeout behaviour added in
**v8.74.0** for the Primary School Management System. The same
mechanism is also installed in the College and Secondary subsystems
(see their respective `SESSION_TIMEOUT.md` files).

---

## Summary

The Primary GUI **and** CLI auto-log-out the active user after
**30 minutes of inactivity**. This is particularly important on shared
classroom and staffroom machines where pupil data could otherwise be
exposed to the next user. Enabled by default — no configuration
required.

| Interface | Default | Configurable in |
|-----------|---------|------------------|
| GUI | 30 minutes | `primary_school/main_gui.py` (`MainApplication.__init__`) |
| CLI | 30 minutes | `primary_school/cli/cli_main.py` (`main()`) |

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
- On `WM_DELETE_WINDOW`, the watchdog is cancelled cleanly.

This is **real activity tracking** — a teacher clicking through pupil
records stays logged in indefinitely; only walking away triggers the
logout.

### CLI

The CLI uses `education_system.shared.cli.cli_helpers.enable_idle_timeout`
which wraps the menu prompt (`get_choice`) in a `signal.SIGALRM` watchdog:

- Each call to `get_choice()` installs a fresh `SIGALRM` for `timeout * 60` seconds.
- If the user enters input within the window, the alarm is cancelled and the timer resets.
- If the alarm fires while waiting on `input()`, the timeout message is printed, the logout callback runs, and the process exits cleanly.

> **Note:** Long-running actions inside menu handlers (e.g. typing a
> long pastoral note) are **not** bounded by the timeout. The clock
> starts again the next time you return to a menu prompt.

> **Platform note:** `signal.SIGALRM` is Unix-only. On Windows the CLI
> idle timeout is silently a no-op. The GUI watchdog works on all
> platforms.

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

Edit `MainApplication.__init__` in
`education_system/primary_school/main_gui.py`:

```python
self._cancel_idle_timeout = attach_idle_timeout(
    self, self._idle_logout, timeout_minutes=30,  # ← change this
)
```

### CLI

Edit the `main()` function in
`education_system/primary_school/cli/cli_main.py`:

```python
enable_idle_timeout(30, _idle_logout)  # ← change this
```

To **disable** the timeout entirely, set the value to `0`.

---

## Security rationale

| Risk | Mitigation |
|------|------------|
| Shared classroom workstation left logged in between lessons | Auto-logout ensures the next teacher / TA / supply can't see the previous session's records |
| Staffroom laptop forgotten at break time | Pupil safeguarding records remain protected |
| Remote-desktop session left open overnight | Same — the watchdog fires regardless of who is physically at the keyboard |
| Forgotten SSH/CLI session | The CLI watchdog kills the process, freeing locked DB connections |

Primary schools handle data on the youngest and most vulnerable
children in the system; the 30-minute default is deliberately
conservative. **Lower it on shared/lab machines if your DPO recommends.**

---

## Implementation references

| Component | File |
|-----------|------|
| Shared GUI helper | `education_system/shared/gui/idle_timeout.py` |
| Shared CLI helper | `education_system/shared/cli/cli_helpers.py` |
| Primary GUI wiring | `education_system/primary_school/main_gui.py` |
| Primary CLI wiring | `education_system/primary_school/cli/cli_main.py` |

---

## Related documentation

- [`SECURITY.md`](SECURITY.md) — overall primary school security architecture
- [`MFA_GUIDE.md`](MFA_GUIDE.md) — multi-factor authentication setup
- [`../guides/communication.md`](../guides/communication.md) — Communication guide (also references the timeout)
