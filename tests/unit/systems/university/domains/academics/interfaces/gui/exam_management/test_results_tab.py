"""Focused tests for the exam-results dialog helpers."""

from unittest.mock import MagicMock

import tkinter as tk

from education_system.systems.university.domains.academics.interfaces.gui.exam_management.tabs.results_tab import (
    _grab_when_viewable,
)


def test_grab_is_deferred_until_dialog_is_viewable():
    dialog = MagicMock()
    dialog.winfo_exists.return_value = True
    dialog.winfo_viewable.return_value = False

    _grab_when_viewable(dialog)

    dialog.grab_set.assert_not_called()
    dialog.after.assert_called_once()

    dialog.winfo_viewable.return_value = True
    dialog.after.call_args.args[1]()

    dialog.grab_set.assert_called_once_with()


def test_grab_ignores_dialog_destroyed_during_deferred_callback():
    dialog = MagicMock()
    dialog.winfo_exists.side_effect = tk.TclError("invalid command name")

    _grab_when_viewable(dialog)

    dialog.grab_set.assert_not_called()
    dialog.after.assert_not_called()
