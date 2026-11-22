# Idle / Inactivity Auto-Logout — College System

This document describes the session-timeout behaviour of the Sixth Form
College Management System. It uses the system's own idle-timeout
helpers rather than the shared ones in `platform/delivery/`.

---

## Summary

The College GUI **and** CLI auto-log-out the active user after
**30 minutes of inactivity**. This protects against unattended
terminals exposing student data and is enabled by default — no
configuration is required.

| Interface | Default | Configurable with |
|-----------|---------|------------------|
| GUI | 30 minutes | `EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES` |
| CLI | 30 minutes | `EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES` |

---

## How activity is tracked

### GUI

`SixthFormMainGUI` starts an `IdleTimeoutWatcher` from
`education_system.systems.sixth_form.interfaces.gui.idle_timeout`, which:

- Records the time of the last activity.
- Binds key, mouse-button, mouse-motion and mouse-wheel events so any
  user interaction in the application resets the timer.
- Wakes up every 30 seconds via `after()` and checks the idle time
  against the configured timeout.
- Shows a warning 60 seconds before the cut-off.
- Is stopped cleanly when the window closes.

This is **real activity tracking** — a user clicking around stays
logged in indefinitely; only walking away triggers the logout.

The parent and student portal windows start the same watcher.

### CLI

The CLI uses `timed_input` from
`education_system.systems.sixth_form.interfaces.cli.idle_timeout` for its
menu prompts:

- `timed_input()` is a drop-in replacement for `input()` that raises
  `SessionTimeoutError` if nothing arrives within the timeout.
- `stamp_activity()` records that the user just did something, so the
  next main-loop prompt measures idle time across the whole session.
- The main loop catches `SessionTimeoutError` and returns to the
  universal login.

> **Note:** Prompts inside a domain CLI's own menus (e.g. typing a long
> message body) use plain `input()` and are **not** bounded by the
> timeout. The clock is checked the next time you return to a main menu
> prompt.

---

## What the user sees on timeout

### GUI

A warning appears 60 seconds before the cut-off. On timeout, the watcher
calls `_idle_logout()`, which runs the same teardown as the Logout button
and shows a notice explaining why the user is back at the login screen.

### CLI

The menu prompt stops waiting, the session ends and the CLI returns to the
login.

---

## Changing the default timeout

Set the environment variable before launching, for both interfaces:

```bash
export EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES=15
python -m education_system --college --gui
```

To **disable** the timeout entirely, set the value to `0`. An invalid or
negative value is ignored and the default of 30 minutes is used.

---

## Security rationale

| Risk | Mitigation |
|------|------------|
| Lab/staffroom workstation left unattended | Auto-logout after 30 min ensures the next user can't see the previous session's records |
| Remote-desktop session left open overnight | Same — the watchdog fires regardless of who is physically at the keyboard |
| Forgotten SSH/CLI session | The CLI prompt times out and ends the session |
| Long-running batch operation that legitimately needs more than 30 min | Timeout only applies at main menu prompts, not inside an action's own `input()` calls |

---

## Implementation references

| Component | File |
|-----------|------|
| GUI watcher | `src/education_system/systems/sixth_form/interfaces/gui/idle_timeout.py` |
| CLI helper | `src/education_system/systems/sixth_form/interfaces/cli/idle_timeout.py` |
| College GUI wiring | `src/education_system/systems/sixth_form/interfaces/gui/gui_main.py` |
| College CLI wiring | `src/education_system/systems/sixth_form/interfaces/cli/cli_main.py` |

---

## Related documentation

- [`SECURITY.md`](SECURITY.md) — overall college security architecture
- [`MFA_GUIDE.md`](MFA_GUIDE.md) — multi-factor authentication setup
- [`../guides/communication.md`](../guides/communication.md) — Communication guide (also references the timeout)
