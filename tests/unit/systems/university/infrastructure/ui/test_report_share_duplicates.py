"""A report window offers each of Save and Email once, whoever provides it."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from education_system.systems.university.infrastructure.ui import report_share as rs


def _classify(text):
    root = type("B", (), {"cget": lambda self, _k: text})()
    return rs._action_of(root)


@pytest.mark.parametrize("label", [
    "Save Report", "💾 Save Report to File", "Export to CSV", "Export", "Save as TXT",
    "Download", "️ Export CSV",
])
def test_labels_that_save_the_report(label):
    assert _classify(label) == "save"


@pytest.mark.parametrize("label", [
    "Send to Admin", "📧 Email to Admin", "Email Report to Admin", "Send Report",
    "Send to Admin via Email", "Email Report", "Send Email",
])
def test_labels_that_email_the_report(label):
    assert _classify(label) == "email"


@pytest.mark.parametrize("label", [
    "Save Settings", "Save Changes", "Save Configuration", "Send", "Send Message",
    "Send Reminders", "Send Email Alert", "Test Email", "Import CSV", "Close", "Schedule Export",
    "Save Attendance", "Save Budget", "Save Policy", "Export Template",
])
def test_labels_that_are_something_else(label):
    assert _classify(label) is None


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    window.withdraw()
    yield window
    window.destroy()


def _labels(window):
    out = []

    def walk(w):
        for child in w.winfo_children():
            if isinstance(child, (tk.Button, ttk.Button)):
                out.append(child.cget("text"))
            walk(child)
    walk(window)
    return out


def _window(root, *labels):
    window = tk.Toplevel(root)
    frame = ttk.Frame(window)
    frame.pack()
    for label in labels:
        ttk.Button(frame, text=label).pack()
    return window


@pytest.mark.gui
def test_window_with_both_gets_no_bar(root):
    window = _window(root, "Save Report", "Send to Admin")
    rs.add_bar(window)
    assert _labels(window) == ["Save Report", "Send to Admin"]


@pytest.mark.gui
def test_window_with_one_gets_only_the_other(root):
    window = _window(root, "Export to CSV")
    rs.add_bar(window)
    assert sorted(_labels(window)) == sorted(["Export to CSV", rs.EMAIL_TEXT])


@pytest.mark.gui
def test_unrelated_buttons_still_get_both(root):
    window = _window(root, "Save Settings", "Close")
    rs.add_bar(window)
    assert {rs.SAVE_TEXT, rs.EMAIL_TEXT} <= set(_labels(window))


@pytest.mark.gui
def test_button_added_later_withdraws_ours(root):
    window = _window(root, "Generate")
    window.update()
    rs.add_bar(window)
    assert rs.SAVE_TEXT in _labels(window)
    frame = ttk.Frame(window)
    frame.pack()
    ttk.Button(frame, text="Save Report").pack()
    window.update()
    assert rs.SAVE_TEXT not in _labels(window)
    assert rs.EMAIL_TEXT in _labels(window)


@pytest.mark.gui
def test_opened_dialogs_do_not_count_as_the_windows_buttons(root):
    window = _window(root, "Close")
    dialog = tk.Toplevel(window)
    ttk.Button(dialog, text="Save Report").pack()
    rs.add_bar(window)
    assert rs.SAVE_TEXT in _labels(window)
