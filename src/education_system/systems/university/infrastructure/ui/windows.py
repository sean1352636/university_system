"""Opening another domain's window without importing that domain.

A slice may not reach into another university domain (the slice boundary
tests), yet a screen sometimes needs to hand the user over — the
disciplinary portal opening the academic integrity case it just raised.
The window is named here and loaded on first use, the same lazy lookup the
domain packages use for their own GUI exports.
"""

from __future__ import annotations

import importlib

_INTEGRITY_WINDOW = ("education_system.systems.university.domains.integrity.interfaces.gui."
                     "plagiarism_main_gui.window")
_AI_DETECTOR = "education_system.systems.university.domains.integrity.interfaces.gui.ai_detector.main"
# Shell screens a domain hands the user over to (a domain may not import the shell).
_CHAT_LAUNCHERS = "education_system.systems.university.shell.gui.email.email_gui.chat_launchers"
_EMAIL_DIALOGS = "education_system.systems.university.shell.gui.email.email_gui.email_dialogs"
_LINK_BAR = "education_system.systems.university.shell.gui.main.features.academic_link_bar"
_MAIN_GUI = "education_system.systems.university.shell.gui.main"

#: Roles that may use the AI Content Detector (a staff tool: it shows
#: every reading on the modules the person reviews).
DETECTOR_ROLES = ("staff", "instructor", "lecturer", "teacher", "faculty", "admin",
                  "administrator", "superadmin")


def _current_user(auth):
    if isinstance(auth, dict):
        return auth if auth.get("username") else None
    user = getattr(auth, "current_user", None) if auth is not None else None
    if callable(user):
        try:
            user = user()
        except Exception:
            user = None
    return user if isinstance(user, dict) and user.get("username") else None


def may_use_ai_detector(auth) -> bool:
    """Is someone signed in to ``auth`` with a staff role?"""
    user = _current_user(auth)
    return bool(user) and str(user.get("role") or "").lower() in DETECTOR_ROLES


def open_ai_detector(parent, auth):
    """The AI Content Detector in its own window, running as the person
    signed in to ``auth``. Staff only: anyone else (or nobody signed in) is
    told so and nothing opens. Returns the detector GUI, or ``None``."""
    from tkinter import messagebox
    if _current_user(auth) is None:
        messagebox.showerror("AI Content Detector",
                             "Sign in to the University system to use the AI Content Detector.",
                             parent=parent)
        return None
    if not may_use_ai_detector(auth):
        messagebox.showinfo("AI Content Detector",
                            "The AI Content Detector is for staff. Your own AI-writing readings "
                            "are in Academic Integrity (My AI-writing readings).", parent=parent)
        return None
    import tkinter as tk
    window = tk.Toplevel(parent)
    window.title("AI Content Detector")
    try:
        return importlib.import_module(_AI_DETECTOR).AIDetectorGUI(window, auth)
    except Exception:
        window.destroy()
        raise


def open_academic_integrity(parent, auth, case_id=None):
    """The Academic Integrity window for whoever is signed in to ``auth``,
    showing case ``case_id`` in its Cases section when given (and the person may
    see it). Returns the window, or ``None`` when it could not open."""
    window = importlib.import_module(_INTEGRITY_WINDOW).open_integrity_window(parent, auth)
    if window is None or case_id is None:
        return window
    cases = window.select("CasesTab")
    if cases is not None:
        cases.open_record(str(case_id))
    return window


def open_ai_writing(parent, auth):
    """The Academic Integrity window opened on its AI-writing section (the
    readings and review queue that replaced the retired AI Content
    Detector). Students land on their own readings; staff on the module
    queue. Stays on the first section when the person has no AI-writing
    section. Returns the window, or ``None`` when it could not open."""
    window = importlib.import_module(_INTEGRITY_WINDOW).open_integrity_window(parent, auth)
    if window is None:
        return None
    window.select("AiWriting") or window.select("MyAiReadings")
    return window


# ── shell screens ───────────────────────────────────────────────────────


def open_event_chat(parent, auth, event_id, event_name):
    """Open (or create) the chat room linked to a calendar event."""
    from education_system.systems.university.infrastructure.email.admin import (
        CommunicationDashboard,
    )
    dashboard = CommunicationDashboard(auth=auth)
    return importlib.import_module(_CHAT_LAUNCHERS).open_chat_for_event(
        parent, dashboard, event_id, event_name)


def compose_email(parent, auth, subject="", body="", recipient=None):
    """The standard Compose Email dialog, filled in with ``subject`` and
    ``body``; the person signed in reviews, picks recipients and sends."""
    import tkinter as tk
    dialog = importlib.import_module(_EMAIL_DIALOGS).ComposeEmailDialog(parent, auth,
                                                                       recipient=recipient)
    if subject:
        dialog.subject_entry.delete(0, tk.END)
        dialog.subject_entry.insert(0, subject)
    if body:
        dialog.body_text.delete("1.0", tk.END)
        dialog.body_text.insert("1.0", body)
    return dialog


def request_open(action, context=None):
    """Ask the main window to open another screen (the academic link bar)."""
    return importlib.import_module(_LINK_BAR).request_open(action, context or {})


def open_main_menu(auth):
    """Start the main university window (for screens run on their own)."""
    app = importlib.import_module(_MAIN_GUI).UnifiedManagementGUI(auth)
    app.run()
    return app
