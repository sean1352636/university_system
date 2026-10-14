
from education_system.systems.university.infrastructure.i18n import get_text as _t
import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.safeguarding.application.api import (
    _get_current_user,
    _is_staff_role,
    _remove_legacy_db,
    init_db,
    quick_exit,
    tr,
)
from education_system.systems.university.domains.safeguarding.infrastructure import config  # noqa: F401  (runs sys.path/logging bootstrap)
from education_system.systems.university.domains.safeguarding.interfaces.gui.wizard_mixin import (
    WizardMixin,
)
from education_system.systems.university.domains.safeguarding.interfaces.gui.staff_dashboard_mixin import (
    StaffDashboardMixin,
)
from education_system.systems.university.domains.safeguarding.interfaces.gui.case_detail_mixin import (
    CaseDetailMixin,
)
from education_system.systems.university.domains.safeguarding.interfaces.gui.case_actions_mixin import (
    CaseActionsMixin,
)
from education_system.systems.university.domains.safeguarding.interfaces.gui.tools_mixin import (
    ToolsMixin,
)
from education_system.systems.university.domains.safeguarding.interfaces.gui.register_mixin import (
    RegisterMixin,
)
from education_system.systems.university.domains.safeguarding.interfaces.gui.session_lock_mixin import (
    SessionLockMixin,
)
from education_system.platform.delivery.gui.portal_dismiss import add_dismiss_button


class SafeguardingApp(
    WizardMixin,
    StaffDashboardMixin,
    CaseDetailMixin,
    CaseActionsMixin,
    ToolsMixin,
    RegisterMixin,
    SessionLockMixin,
    tk.Tk,
):
    def __init__(self, host=None):
        """Build the Safeguarding portal.

        ``host`` may be:
          * ``None`` (legacy / subprocess) — initialise as a ``tk.Tk``
            root and own the window/mainloop.
          * a workspace tab ``Frame`` (passed by ``open_in_workspace``)
            — skip Tk init and build widgets onto the host frame.
            ``mainloop()`` becomes a no-op (caller owns it).

        Same shape as ComplaintsPortal (8.117.49).
        """
        if host is None:
            super().__init__()
            self.title(_t('gui.safeguarding.app.windows.university_portal_safeguarding_system', default="University Portal — Safeguarding System"))
            self.geometry("1000x680")
            self.configure(bg="#f4f6fa")
            self._host = self
            self._owns_root = True
        else:
            self._host = host
            self._owns_root = False
            try:
                host.configure(bg="#f4f6fa")
            except tk.TclError:
                pass

        self.user = _get_current_user()
        # Default language — student wizard may overwrite this later. Set
        # unconditionally because tk.Misc.__getattr__ proxies missing
        # attributes to self.tk, which recurses in embedded mode.
        self.lang = (self.user or {}).get("language") or "en"

        # Ensure schema exists — when launched embedded from the main GUI,
        # ``main()`` is bypassed so init_db() would not otherwise run.
        try:
            init_db()
        except Exception:
            logger.warning("init_db() failed during embedded launch", exc_info=True)

        # ttk theming — process-global style; only configure named styles
        # to avoid leaking into the host main GUI when embedded.
        style = ttk.Style(self._host)
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), background="#f4f6fa")
        style.configure(
            "Sub.TLabel", font=("Segoe UI", 10), background="#f4f6fa", foreground="#555"
        )

        self.container = tk.Frame(self._host, bg="#f4f6fa")
        self.container.pack(fill="both", expand=True)

        if not self.user:
            self.show_no_auth()
        elif _is_staff_role(self.user.get("role")):
            logger.info(
                "Safeguarding starting console=staff user=%s role=%s",
                self.user.get("username"),
                self.user.get("role"),
            )
            self.show_staff_dashboard()
        else:
            logger.info(
                "Safeguarding starting console=student user=%s role=%s",
                self.user.get("username"),
                self.user.get("role"),
            )
            self.show_student_dashboard()

        # Case detail is the most sensitive screen in the portal and is
        # routinely left open on an unattended desk — lock it after a period
        # without activity. Started last so a failure here cannot stop the
        # console from building.
        if self.user:
            try:
                self._start_idle_watch()
            except Exception:
                logger.warning("could not start the idle session lock", exc_info=True)

    def mainloop(self, n: int = 0):
        if not self._owns_root:
            return
        super().mainloop(n)

    def destroy(self):
        self.stop_idle_watch()
        if self._owns_root:
            super().destroy()
        else:
            try:
                self._host.destroy()
            except tk.TclError:
                pass

    def unbind(self, sequence, funcid=None):
        try:
            return self._host.unbind(sequence, funcid)
        except tk.TclError:
            pass

    def bind(self, sequence=None, func=None, add=None):
        return self._host.bind(sequence, func, add)

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_no_auth(self):
        self._clear()
        frame = tk.Frame(self.container, bg="#f4f6fa")
        frame.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(frame, text=_t('gui.safeguarding.app.labels.authentication_required', default="🔒 Authentication Required"), style="Header.TLabel").pack(pady=(0, 8))
        ttk.Label(
            frame,
            text=_t('gui.safeguarding.app.labels.please_launch_this_portal_from_the_main_university_system_after', default="Please launch this portal from the main\nUniversity System after signing in."),
            style="Sub.TLabel",
            justify="center",
        ).pack(pady=(0, 14))
        ttk.Button(frame, text=_t('gui.safeguarding.app.buttons.close', default="Close"), command=self.destroy).pack()

    def _build_topbar(self, title):
        bar = tk.Frame(self.container, bg="#1f3a5f", height=55)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text=title, bg="#1f3a5f", fg="white", font=("Segoe UI", 12, "bold")).pack(
            side="left", padx=20
        )

        # Safe-exit button always visible — disguised label, immediate effect.
        exit_lang = self.__dict__.get("lang", "en")
        exit_btn = tk.Button(
            bar,
            text=tr("safe_exit", exit_lang),
            bg="#d9480f",
            fg="white",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=4,
            activebackground="#b00020",
            activeforeground="white",
            command=quick_exit,
        )
        exit_btn.pack(side="right", padx=12, pady=10)
        # Bind ESC anywhere as a panic key
        self._host.bind_all("<Escape>", lambda _e: quick_exit())

        # Ordinary way out, distinct from the orange safe-exit above: hand the
        # user back to the main window rather than slamming the portal shut.
        # The label reflects how this instance is actually hosted.
        add_dismiss_button(
            bar,
            self._host,
            on_before=self.stop_idle_watch,
            padx=(4, 12),
        )

        # Manual lock — the idle timer is a backstop, not the primary way to
        # clear the screen before walking away from it.
        if self.user:
            tk.Button(
                bar,
                text=_t('gui.safeguarding.app.buttons.lock', default="Lock"),
                bg="#1f3a5f",
                fg="white",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=10,
                pady=4,
                activebackground="#274875",
                activeforeground="white",
                command=lambda: self.lock_session(reason="locked by user"),
            ).pack(side="right", padx=4, pady=10)

        # Tools menu — staff only (gates inside the dialogs further restrict).
        if self.user and _is_staff_role(self.user.get("role")):
            tk.Button(
                bar,
                text=_t('gui.safeguarding.app.buttons.tools', default="Tools"),
                bg="#1f3a5f",
                fg="white",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=10,
                pady=4,
                activebackground="#274875",
                activeforeground="white",
                command=self._open_tools_menu,
            ).pack(side="right", padx=4, pady=10)

        role = (self.user or {}).get("role") or "—"
        tk.Label(
            bar,
            text=f"Signed in: {(self.user or {}).get('username') or 'Guest'}  ({role})",
            bg="#1f3a5f",
            fg="#cfe0ff",
            font=("Segoe UI", 9),
        ).pack(side="right", padx=20)


def main():
    _remove_legacy_db()
    init_db()
    app = SafeguardingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
