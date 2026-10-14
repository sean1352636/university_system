"""Scholarship Finder window: the student scholarship portal with a finder nav bar.

The sidebar used to say the finder "moved to Finance GUI"; the pages that moved
were the recommendations, profile, deadlines, documents and awards screens of
the Financial Aid student portal. This window hosts that same ``StudentPortal``
(one instance, one set of mixins, no second copy of any page) and opens it on
the finder pages: filtered search, recommendations, the finder's application
tracker, deadlines, documents, profile and award history.

Opened in-process by the main GUI (``open_window(master, auth)``) with the
session auth, or standalone (``main``) where the EDU_AUTH_* env vars carry the
user. Nothing touches the database or tkinter-heavy modules at import time.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.platform.delivery.gui.subprocess_session import session_user
from education_system.platform.delivery.gui.window_sizing import center as _center
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)
WINDOW_TITLE = "Scholarship Finder"
WINDOW_SIZE = (1400, 900)
WINDOW_MIN = (1200, 800)

# (i18n key, default label, StudentPortal method name) in nav order.
PAGES: tuple[tuple[str, str, str], ...] = (
    ("search", "Search", "show_scholarship_search"),
    ("recommendations", "Recommendations", "show_recommendations"),
    ("applications", "My Applications", "show_application_tracker"),
    ("deadlines", "Deadlines", "show_deadlines"),
    ("documents", "Document Vault", "show_documents"),
    ("profile", "My Profile", "show_profile"),
    ("awards", "Award History", "show_award_history"),
    ("dashboard", "Aid Dashboard", "show_dashboard"),
)
HOME_PAGE = "show_scholarship_search"


def _resolve_student_id(auth: Any) -> str | None:
    """Same preference order as the portal's ``get_student_id``, over the given auth."""
    user = session_user(auth)
    if not user:
        return None
    value = (user.get("student_id") or user.get("user_id") or user.get("id")
             or user.get("username"))
    return str(value) if value else None


class ScholarshipFinderWindow(ttk.Frame):
    """Finder nav bar on top; the shared student portal fills the rest."""

    def __init__(self, parent, auth: Any = None) -> None:
        super().__init__(parent)
        self.auth = auth
        self.user = session_user(auth) or {}
        self._nav_buttons: dict[str, ttk.Button] = {}
        self._build_nav()
        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.portal = self._make_portal()
        self.show_page(HOME_PAGE)

    def _build_nav(self) -> None:
        bar = ttk.Frame(self, relief="raised", borderwidth=1, padding=(8, 4))
        bar.pack(fill="x")
        ttk.Label(bar, text=_t("gui.finance.scholarship_finder.title", default=WINDOW_TITLE),
                  font=("Arial", 12, "bold")).pack(side="left", padx=(4, 16))
        for key, label, method in PAGES:
            text = _t(f"gui.finance.scholarship_finder.nav.{key}", default=label)
            button = ttk.Button(bar, text=text, command=lambda m=method: self.show_page(m))
            button.pack(side="left", padx=2)
            self._nav_buttons[method] = button
        who = self.user.get("username") or ""
        if who:
            # t() leaves a missing key's default unformatted, hence the explicit format.
            text = _t("gui.finance.scholarship_finder.logged_in_as", default="Logged in as {username}")
            ttk.Label(bar, text=text.format(username=who)).pack(side="right", padx=8)

    def _make_portal(self):
        """Build the shared portal over ``self.content``.

        Imported here rather than at module level: ``common_imports`` pulls in
        the financial-aid services and the DB layer, which is exactly the
        import-time cost the launcher's lazy-proxy convention exists to avoid.
        """
        from education_system.systems.university.domains.finance.interfaces.gui.financial_aid.common_imports import (
            configure_styles,
        )
        from education_system.systems.university.domains.finance.interfaces.gui.financial_aid.student_portal import (
            StudentPortal,
        )
        configure_styles()
        portal = StudentPortal(self.content, self.auth)
        student_id = _resolve_student_id(self.auth)
        if student_id:
            # The portal reads the bootstrap-time global auth; a window opened
            # in-process or as a subprocess must key on the session it was given.
            portal.student_id = student_id
            portal.current_user = self.user or portal.current_user
        return portal

    def show_page(self, method: str) -> None:
        """Switch the portal to *method*; portal pages re-render ``parent_frame``."""
        self.portal.parent_frame = self.content
        try:
            getattr(self.portal, method)()
        except Exception as exc:  # a page failing must not take the window down
            logger.error("Scholarship finder page %s failed: %s", method, exc, exc_info=True)
            messagebox.showerror(WINDOW_TITLE, f"Could not open this page: {exc}")
        for name, button in self._nav_buttons.items():
            button.state(["pressed"] if name == method else ["!pressed"])


def _reject(master=None) -> None:
    messagebox.showwarning(
        WINDOW_TITLE,
        _t("gui.finance.scholarship_finder.login_required",
           default="You must be logged in to use the Scholarship Finder."),
        parent=master)


def open_window(master, auth: Any = None) -> tk.Toplevel | None:
    """Open the finder as a Toplevel of ``master`` for the logged-in session."""
    if not session_user(auth):
        _reject(master)
        return None
    top = tk.Toplevel(master)
    top.title(_t("gui.finance.scholarship_finder.title", default=WINDOW_TITLE))
    _center(top, *WINDOW_SIZE, minsize=WINDOW_MIN)
    ScholarshipFinderWindow(top, auth=auth).pack(fill="both", expand=True)
    return top


def main() -> None:
    """Standalone launch (subprocess fallback from the main GUI).

    ``require_launcher_auth`` resolves the EDU_AUTH_* bundle and publishes it
    into ``shared_context``; the portal's ``get_student_id``/``get_current_user``
    read the global auth, so without that step a child process would behave as
    logged out everywhere it was not handed ``auth`` explicitly.
    """
    from education_system.systems.university.shell.gui.auth.launch_guard import (
        require_launcher_auth,
    )
    if require_launcher_auth(WINDOW_TITLE) is None:
        return
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    _center(root, *WINDOW_SIZE, minsize=WINDOW_MIN)
    ScholarshipFinderWindow(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
