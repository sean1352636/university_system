"""Regression checks for explicit Library GUI commands."""

import pytest

from education_system.systems.university.interfaces.gui.academics.library import LibraryGUI


EXPLICIT_CONTEXT_COMMANDS = {
    "add_book_to_list", "edit_reading_list", "share_reading_list",
    "delete_reading_list", "contact_overdue_user", "process_overdue_return",
    "waive_fine", "view_user_history", "show_download_stats",
    "manage_digital_access_dialog",
}


def test_context_menu_commands_are_explicit_class_attributes():
    assert all(name in LibraryGUI.__dict__ for name in EXPLICIT_CONTEXT_COMMANDS)


def test_unknown_command_is_not_fabricated():
    gui = object.__new__(LibraryGUI)
    with pytest.raises(AttributeError):
        getattr(gui, "show_typo_that_does_not_exist")


def test_digital_access_command_delegates_to_real_dialog():
    gui = object.__new__(LibraryGUI)
    called = []
    gui.manage_digital_access_permissions_gui = lambda: called.append(True)
    gui.manage_digital_access_dialog()
    assert called == [True]
