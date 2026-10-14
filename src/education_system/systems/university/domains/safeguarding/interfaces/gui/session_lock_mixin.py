"""Idle session lock, ported from the UniGuard prototype.

Safeguarding case files are the most sensitive screens in the portal and
they are routinely left open on a shared or unattended desk. The prototype
signed the user out after 15 idle minutes; the portal has no credentials of
its own — the main university GUI owns the session — so this is a **privacy
screen** rather than a re-authentication: it clears every case detail from
view, records the lock in the safeguarding audit trail, and requires a
deliberate action to bring the console back.

Deliberately not wired to the shared login manager: a mistyped unlock would
count against the real account's lockout counter, which is a worse failure
than an extra click.
"""

import logging
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.safeguarding.application.api import (
    _is_staff_role,
    audit_log,
    quick_exit,
)

#: Minutes of inactivity before the console locks. Matches the prototype.
IDLE_LOCK_MINUTES = 15

#: How often the idle check runs, in milliseconds.
_IDLE_POLL_MS = 30_000


class SessionLockMixin:
    def _start_idle_watch(self):
        """Begin tracking activity. Safe to call twice."""
        # __dict__.get, never hasattr/getattr — see SafeguardingApp.__init__:
        # tk.Misc.__getattr__ proxies missing attributes to self.tk and
        # recurses when the portal is embedded in a host frame.
        if self.__dict__.get("_idle_watch_started"):
            return
        self._idle_watch_started = True
        self._locked = False
        self._last_activity = datetime.now()
        self._idle_after_id = None

        # bind_all reaches the whole toplevel, embedded or not. add="+" so we
        # never clobber the host GUI's own bindings.
        for sequence in ("<Any-KeyPress>", "<Any-Button>", "<MouseWheel>"):
            try:
                self._host.bind_all(sequence, self._touch_activity, add="+")
            except tk.TclError:
                logger.debug("could not bind %s for idle tracking", sequence)

        self._schedule_idle_check()

    def _touch_activity(self, _event=None):
        self._last_activity = datetime.now()

    def _schedule_idle_check(self):
        try:
            self._idle_after_id = self._host.after(_IDLE_POLL_MS, self._check_idle)
        except tk.TclError:
            self._idle_after_id = None

    def _check_idle(self):
        try:
            if (
                self.user
                and not self.__dict__.get("_locked")
                and datetime.now() - self._last_activity
                > timedelta(minutes=IDLE_LOCK_MINUTES)
            ):
                self.lock_session(reason=f"idle for {IDLE_LOCK_MINUTES} minutes")
        except tk.TclError:
            return  # window went away
        except Exception:
            logger.warning("idle check failed", exc_info=True)
        self._schedule_idle_check()

    def stop_idle_watch(self):
        """Cancel the pending poll — called when the portal is torn down."""
        after_id = self.__dict__.get("_idle_after_id")
        if after_id:
            try:
                self._host.after_cancel(after_id)
            except tk.TclError:
                pass
            self._idle_after_id = None

    # -- the lock screen ---------------------------------------------------

    def lock_session(self, reason="locked by user"):
        if self.__dict__.get("_locked"):
            return
        self._locked = True
        try:
            audit_log(
                actor=(self.user or {}).get("username", "?"),
                actor_role=(self.user or {}).get("role"),
                action="session_locked",
                details=reason,
            )
        except Exception:
            logger.debug("could not audit session lock", exc_info=True)

        self._clear()
        frame = tk.Frame(self.container, bg="#f4f6fa")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            frame,
            text=_t(
                "gui.safeguarding.session_lock.labels.session_locked",
                default="🔒 Session locked",
            ),
            bg="#f4f6fa",
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(0, 8))
        tk.Label(
            frame,
            text=_t(
                "gui.safeguarding.session_lock.labels.locked_explainer",
                default=(
                    "Case details were hidden after a period without activity.\n"
                    "This lock is recorded in the safeguarding audit trail."
                ),
            ),
            bg="#f4f6fa",
            fg="#555",
            font=("Segoe UI", 10),
            justify="center",
        ).pack(pady=(0, 16))

        buttons = tk.Frame(frame, bg="#f4f6fa")
        buttons.pack()
        ttk.Button(
            buttons,
            text=_t(
                "gui.safeguarding.session_lock.buttons.resume", default="Resume session"
            ),
            command=self.unlock_session,
        ).pack(side="left", padx=6)
        tk.Button(
            buttons,
            text=_t(
                "gui.safeguarding.session_lock.buttons.close_portal",
                default="Close portal",
            ),
            bg="#d9480f",
            fg="white",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=5,
            command=quick_exit,
        ).pack(side="left", padx=6)

    def unlock_session(self):
        self._locked = False
        self._last_activity = datetime.now()
        try:
            audit_log(
                actor=(self.user or {}).get("username", "?"),
                actor_role=(self.user or {}).get("role"),
                action="session_resumed",
                details="",
            )
        except Exception:
            logger.debug("could not audit session resume", exc_info=True)

        if not self.user:
            self.show_no_auth()
        elif _is_staff_role(self.user.get("role")):
            self.show_staff_dashboard()
        else:
            self.show_student_dashboard()


__all__ = ["SessionLockMixin", "IDLE_LOCK_MINUTES"]
