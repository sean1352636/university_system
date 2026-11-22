"""Disability & Accessibility Services — one portal for students and staff.

Merged 2026-10-19 from the Accessibility Services Portal (students' requests)
and the health portal's Medical Accommodations (staff management), which
already shared the ``accommodations`` table but had no screen in common.

* A student gets **My Support**: the five tabs they had (dashboard, submit a
  request, messages, my accommodations, renewals), and **My Disabilities**.
* Disability services and the health team get **Requests** (the queue of
  student requests: open, review, approve, deny, message, documents),
  **Renewals**, **Disabilities** (a student's recorded disabilities),
  **Accommodations** — the full Medical Accommodations tool
  with every menu it had — **DSA** (Disabled Students' Allowances casework)
  and **Evacuation Plans (PEEPs)**. Students also get **My DSA** and
  **My Evacuation Plan** (2026-10-30).

Who sees what is ``domain/disability/access``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.domains.student_support.domain.disability import access

logger = logging.getLogger(__name__)

TITLE = "Disability & Accessibility Services"
SECTIONS = ("my_support", "my_disabilities", "requests", "renewals", "disabilities",
            "accommodations", "dsa", "peeps", "my_dsa", "my_peep")


class DisabilityPortal:
    """``parent`` is a window (the portal opens its own) or a frame to build
    into (the main window's workspace). ``section`` picks the tab shown first.

    ``intake`` opens it for a student who is still being created (Create
    Student → "Does the student have a disability?"): there is no student
    record yet, so the window holds only the list being entered, and Save
    hands it to ``on_save(items)`` and closes; the caller records it once the
    student exists. ``intake`` carries ``name``, ``course`` and any ``items``
    already entered."""

    def __init__(self, parent=None, auth=None, section=None, *, intake=None, on_save=None):
        if auth is None:
            from education_system.systems.university.infrastructure.shared_context import get_auth
            auth = get_auth()
        self.auth = auth
        self.intake = dict(intake) if intake is not None else None
        self._on_save = on_save
        self._owns_window = parent is None or hasattr(parent, "wm_title")
        if self._owns_window:
            self.window = tk.Toplevel(parent) if parent is not None else tk.Tk()
            self.window.title(TITLE if self.intake is None else
                              f"{TITLE} — {self.intake.get('name') or 'new student'}")
            from education_system.platform.delivery.gui import window_sizing
            window_sizing.install()
            window_sizing.center(self.window, 1400, 900, minsize=(1200, 800))
            self.frame = ttk.Frame(self.window)
            self.frame.pack(fill=tk.BOTH, expand=True)
        else:
            self.window = parent.winfo_toplevel()
            self.frame = parent
        self.tabs: dict[str, ttk.Frame] = {}
        if self.intake is not None:
            self._build_intake(parent)
        else:
            self._build(section)

    def _build(self, section):
        try:
            staff = access.scope(self.auth) is None
        except PermissionError as exc:
            ttk.Label(self.frame, text=str(exc), font=("Arial", 12), wraplength=900).pack(
                padx=20, pady=20)
            return

        head = ttk.Frame(self.frame, padding=(10, 8, 10, 0))
        head.pack(fill=tk.X)
        ttk.Label(head, text=TITLE, font=("Arial", 16, "bold")).pack(side=tk.LEFT)
        ttk.Label(head, text=("Requests, adjustments and renewals for every student"
                              if staff else
                              "Ask for reasonable adjustments and see the ones you have"),
                  foreground="#555555").pack(side=tk.LEFT, padx=12)

        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        if staff:
            self._add("requests", "Requests", self._requests)
            self._add("renewals", "Renewals", self._renewals)
            self._add("disabilities", "Disabilities", self._disabilities)
            self._add("accommodations", "Accommodations", self._accommodations)
            self._add("dsa", "DSA", self._dsa)
            self._add("peeps", "Evacuation Plans (PEEPs)", self._peeps)
        else:
            self._add("my_support", "My Support", self._my_support)
            self._add("my_disabilities", "My Disabilities", self._disabilities)
            self._add("my_dsa", "My DSA", self._dsa)
            self._add("my_peep", "My Evacuation Plan", self._peeps)
        tab = self.tabs.get(section)
        if tab is not None:
            self.notebook.select(tab)

    def _build_intake(self, parent):
        """The new-student window: the disabilities list and Save/Cancel."""
        if parent is not None and self._owns_window:
            # Modal over Create Student, which holds its own grab; give the
            # grab back when this window closes.
            self.window.transient(parent)
            self.window.bind("<Destroy>", lambda e: self._return_grab(e, parent), add="+")
            try:
                self.window.grab_set()
            except tk.TclError:
                pass
        from education_system.systems.university.domains.student_support.interfaces.gui.disability.disabilities import (
            DisabilityEditor,
        )
        head = ttk.Frame(self.frame, padding=(10, 8, 10, 0))
        head.pack(fill=tk.X)
        ttk.Label(head, text=TITLE, font=("Arial", 16, "bold")).pack(side=tk.LEFT)
        who = ttk.Frame(self.frame, padding=(10, 6, 10, 0))
        who.pack(fill=tk.X)
        ttk.Label(who, text=f"New student: {self.intake.get('name') or '(name not entered yet)'}",
                  font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        if self.intake.get("course"):
            ttk.Label(who, text=f"   Course: {self.intake['course']}").pack(side=tk.LEFT)
        ttk.Label(self.frame, text="Enter each disability the student has told you about. They "
                                   "are saved to the student's record when the student is "
                                   "created; any adjustment chosen goes to disability services "
                                   "as a request to approve.",
                  foreground="#555555", wraplength=1100, justify=tk.LEFT).pack(
            fill=tk.X, padx=10, pady=(4, 0))
        bar = ttk.Frame(self.frame, padding=10)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.editor = DisabilityEditor(self.frame, self.intake.get("items") or [])
        self.editor.pack(fill=tk.BOTH, expand=True, padx=10)
        ttk.Button(bar, text="Save and return to Create Student",
                   command=self._save_intake).pack(side=tk.RIGHT)
        ttk.Button(bar, text="Cancel", command=self.window.destroy).pack(side=tk.RIGHT, padx=6)

    def _save_intake(self):
        from tkinter import messagebox
        from education_system.systems.university.domains.student_support.domain.disability import portal
        try:
            items = portal.clean_disabilities(self.editor.get_items())
            if not items:
                raise ValueError("Add at least one disability to the list, or cancel.")
        except ValueError as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.window)
            return
        if self._on_save is not None:
            self._on_save(items)
        self.window.destroy()

    def _return_grab(self, event, parent):
        if event.widget is not self.window:
            return
        try:
            if parent.winfo_exists():
                parent.grab_set()
                parent.focus_set()
        except tk.TclError:
            pass

    def _add(self, key, label, builder):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=label)
        self.tabs[key] = tab
        try:
            builder(tab)
        except Exception as exc:
            logger.exception("Disability portal tab %s failed", key)
            ttk.Label(tab, text=f"{label} could not be loaded: {exc}",
                      font=("Arial", 12)).pack(padx=20, pady=20)

    # ------------------------------------------------------------- tabs
    def _my_support(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.disability.accessibility_gui import (
            AccessibilityGUI,
        )
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        self.student_portal = AccessibilityGUI(parent=tab, auth=self.auth)

    def _disabilities(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.disability.disabilities import (
            DisabilitiesPanel,
        )
        DisabilitiesPanel(tab, self.auth).pack(fill=tk.BOTH, expand=True)

    def _requests(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.disability.staff_tabs import (
            RequestsPanel,
        )
        RequestsPanel(tab, self.auth).pack(fill=tk.BOTH, expand=True)

    def _renewals(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.disability.staff_tabs import (
            RenewalsPanel,
        )
        RenewalsPanel(tab, self.auth).pack(fill=tk.BOTH, expand=True)

    def _accommodations(self, tab):
        from education_system.systems.university.domains.health.interfaces.gui.health.medical_accommodation import (
            AccommodationGUI,
        )
        self.accommodations = AccommodationGUI(
            self.window, self.auth, host=tab,
            on_close=self.window.destroy if self._owns_window else None)


    def _dsa(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.disability.dsa_gui import (
            DsaPanel,
        )
        DsaPanel(tab, self.auth).pack(fill=tk.BOTH, expand=True)

    def _peeps(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.disability.peeps_gui import (
            PeepsPanel,
        )
        PeepsPanel(tab, self.auth).pack(fill=tk.BOTH, expand=True)


def open_portal(parent=None, auth=None, section=None) -> DisabilityPortal:
    return DisabilityPortal(parent, auth, section)
