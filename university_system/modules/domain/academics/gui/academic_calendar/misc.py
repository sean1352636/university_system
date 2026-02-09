"""
misc.py
---------

This module houses a handful of top-level functions from the original
``academic_calendar_gui.py`` that don't logically fit into the core
modules such as exceptions, database management or the GUI mixins.  They
provide convenience wrappers for launching the calendar GUI and
integrating it with an existing authentication system.  By isolating
these helpers here, the rest of the package can remain focused on
business logic and presentation while still exposing simple entry
points for external code.

These functions are copied verbatim from the original monolithic
implementation with only minimal adjustments to import paths so they
can reference the refactored classes.  They intentionally catch and
display user‑friendly messages rather than letting exceptions bubble up
to the top level.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from university_system.modules.shared.utils.i18n import get_text as _

# Import the refactored CalendarGUI from this package.  The GUI class
# lives in ``main_gui.py`` and aggregates all mixin behaviour via
# inheritance, so instantiating it here provides the full calendar UI.
from .main_gui import CalendarGUI


def launch_calendar_gui(auth_manager: Optional[object] = None) -> Optional[CalendarGUI]:
    """Launch the calendar GUI application.

    This helper creates an instance of :class:`CalendarGUI` and
    initializes any necessary permissions before returning the GUI
    instance.  On errors it displays a message box to the user and
    returns ``None``.

    Args:
        auth_manager: Optional authentication manager used to obtain
            the current user and their permissions.

    Returns:
        A fully configured :class:`CalendarGUI` instance if
        initialization succeeded, otherwise ``None``.
    """
    try:
        # Ensure calendar permissions are provisioned using the
        # underlying service.  This import may fail if the domain
        # service layer isn't available, in which case we display a
        # friendly error below.
        from university_system.modules.domain.academics.services.academic_calendar.cli import (  # type: ignore
            ensure_calendar_permissions,
        )
        ensure_calendar_permissions()

        gui = CalendarGUI(auth_manager)
        return gui

    except ImportError as e:
        # Handle missing domain dependencies gracefully by showing
        # users an error dialog.  We avoid using the GUI class here
        # because it may not be initialized when imports fail.
        root = tk.Tk()
        root.withdraw()
        error_msg = _("academic_calendar.messages.import_error").format(error=e)
        messagebox.showerror(_("academic_calendar.messages.import_error_title"), error_msg)
        root.destroy()
        return None

    except Exception as e:
        # Catch any other initialization error, show a friendly
        # message, and return None.
        root = tk.Tk()
        root.withdraw()
        error_msg = _("academic_calendar.messages.initialization_error").format(error=e)
        messagebox.showerror(_("academic_calendar.messages.initialization_error_title"), error_msg)
        root.destroy()
        return None


def run_gui_calendar(auth_manager: Optional[object] = None) -> None:
    """Convenience function to launch and run the calendar GUI.

    This function simply calls :func:`launch_calendar_gui` and, if a
    GUI is created successfully, invokes its ``run`` method to enter
    the main event loop.

    Args:
        auth_manager: Optional authentication manager to pass through
            to :func:`launch_calendar_gui`.
    """
    gui = launch_calendar_gui(auth_manager)
    if gui:
        gui.run()


def display_academic_calendar_gui(auth_manager: Optional[object] = None) -> None:
    """Backward compatibility wrapper for launching the GUI.

    Historically the calendar API exposed a function named
    ``display_academic_calendar_gui``.  To maintain compatibility
    callers can still invoke this name which simply delegates to
    :func:`run_gui_calendar`.

    Args:
        auth_manager: Optional authentication manager used when
            launching the GUI.
    """
    return run_gui_calendar(auth_manager)


def integrate_with_main_system() -> Optional[CalendarGUI]:
    """Integrate and launch the GUI within the main system.

    This function attempts to use the central authentication system
    provided by the infrastructure package.  If a user is currently
    authenticated it launches the calendar GUI with that user.  If no
    authentication is available it displays an appropriate message and
    returns ``None``.

    Returns:
        A :class:`CalendarGUI` instance if launched, otherwise ``None``.
    """
    try:
        from university_system.infrastructure.auth import _current_auth_instance  # type: ignore
        if _current_auth_instance and getattr(_current_auth_instance, "current_user", None):
            # User is authenticated, launch the GUI with their context
            return run_gui_calendar(_current_auth_instance)
        else:
            # No authentication present; prompt user
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                _("academic_calendar.messages.auth_required_title"),
                _("academic_calendar.messages.auth_required")
            )
            root.destroy()
            return None
    except ImportError:
        # If authentication infrastructure isn't available, fallback to
        # running without authentication but warn the user.
        messagebox.showwarning(
            _("academic_calendar.messages.auth_unavailable_title"),
            _("academic_calendar.messages.auth_unavailable")
        )
        run_gui_calendar()
        return None
