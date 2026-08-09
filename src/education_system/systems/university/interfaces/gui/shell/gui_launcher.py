"""
GUI Launcher Utility

This module provides a centralized way to launch GUI components,
helping to avoid circular import issues by providing late-binding functions.
"""

from typing import Any, Optional

from education_system.systems.university.infrastructure.i18n import get_text, _


def launch_main_gui(auth: Any = None) -> None:
    """
    Launch the main UnifiedManagementGUI.

    This function provides a late-binding way to launch the main GUI,
    avoiding circular import issues when called from child GUI modules.

    Parameters
    ----------
    auth : Any, optional
        The authentication object to pass to the GUI.
    """
    from education_system.systems.university.interfaces.gui.shell.main import UnifiedManagementGUI
    app = UnifiedManagementGUI(auth)
    app.run()


def get_main_gui_class() -> type:
    """
    Get the UnifiedManagementGUI class.

    Returns the class itself for cases where you need to check
    isinstance() or access class attributes.

    Returns
    -------
    type
        The UnifiedManagementGUI class.
    """
    from education_system.systems.university.interfaces.gui.shell.main import UnifiedManagementGUI
    return UnifiedManagementGUI


def is_child_of_main_gui(widget: Any) -> bool:
    """
    Check if a widget is a child window of the main GUI.

    Parameters
    ----------
    widget : Any
        A tkinter widget to check.

    Returns
    -------
    bool
        True if the widget is a child of the main GUI, False otherwise.
    """
    try:
        # Check if this is a Toplevel window
        import tkinter as tk
        if not isinstance(widget, (tk.Tk, tk.Toplevel)):
            return False

        # Check if the master is the main GUI
        master = widget.master
        if master is None:
            return False

        main_gui_class = get_main_gui_class()
        return isinstance(getattr(master, '_gui_instance', None), main_gui_class)
    except Exception:
        return False


def return_to_main_menu(current_window: Any, auth: Any = None) -> None:
    """
    Return to the main menu from a child window.

    This handles both cases:
    - When running as a child window (just closes the window)
    - When running standalone (launches the main GUI)

    Parameters
    ----------
    current_window : Any
        The current tkinter window to close.
    auth : Any, optional
        The authentication object to pass if launching main GUI.
    """
    import tkinter as tk

    try:
        # Get the root widget
        if hasattr(current_window, 'root'):
            root_widget = current_window.root
        elif hasattr(current_window, 'master') and current_window.master:
            root_widget = current_window.master
        else:
            root_widget = current_window

        # Check if we're a Toplevel (child window)
        if isinstance(root_widget, tk.Toplevel):
            # Just close the child window
            root_widget.destroy()
        else:
            # Running standalone, need to create main GUI
            root_widget.destroy()
            launch_main_gui(auth)
    except Exception as e:
        print(get_text("gui.launcher.error_returning_to_main", error=str(e)))
        import traceback
        traceback.print_exc()
