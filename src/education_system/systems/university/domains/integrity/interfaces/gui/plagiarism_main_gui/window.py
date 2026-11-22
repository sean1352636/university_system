"""The Academic Integrity window: one window for everyone, with the
sections the signed-in person's role allows, chosen from a sidebar of
buttons. A section is built the first time its button is pressed and kept
afterwards, so switching back keeps its search, selection and scroll.

It always runs as the person signed in to the university window that
opened it. With nobody signed in it refuses to open; there is no fallback
user.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.university.application.integrity import access
from education_system.systems.university.infrastructure.ui.record_screens import TITLE, call

WINDOW_TITLE = "Academic Integrity"


def signed_in_user(auth) -> dict | None:
    """The ``current_user`` dict behind any of the university's auth objects."""
    if isinstance(auth, dict):
        return auth if auth.get("username") else None
    user = getattr(auth, "current_user", None) if auth is not None else None
    if callable(user):
        try:
            user = user()
        except Exception:
            user = None
    if user is None and hasattr(auth, "get_current_user"):
        try:
            user = auth.get_current_user()
        except Exception:
            user = None
    return user if isinstance(user, dict) and user.get("username") else None


def _tabs(who, officer):
    from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui import (  # noqa: E501
        ai_writing, officer_tabs, staff_tabs, student_tabs, tools_view,
    )
    if who.is_student:
        return [("How work is checked", student_tabs.NoticeTab),
                ("My work", student_tabs.MyWorkTab),
                ("Check a draft", student_tabs.DraftCheckTab),
                ("My cases", student_tabs.MyCasesTab),
                ("My AI-writing readings", ai_writing.MyAiReadingsTab)]
    if not who.is_staff:
        return []
    found = [("Review queue", staff_tabs.ReviewQueueTab), ("Documents", staff_tabs.DocumentsTab),
             ("Failed checks", staff_tabs.FailedChecksTab),
             ("AI writing", ai_writing.AiWritingTab),
             ("Module settings", staff_tabs.ModuleSettingsTab),
             ("Statistics", staff_tabs.StatisticsTab),
             ("Tools", tools_view.ToolsTab)]
    # Officers see every case; other staff the cases they raised (to add evidence).
    found.append(("Cases" if officer else "Cases I raised", officer_tabs.CasesTab))
    if officer:
        found += [("Settings", officer_tabs.SettingsTab),
                  ("Records", officer_tabs.RecordsTab), ("Audit", officer_tabs.AuditTab)]
    if who.is_admin:
        found.append(("Roles", officer_tabs.RolesTab))
    return found


#: Sidebar headings, by section label (sections keep the order of ``_tabs``).
GROUPS = {
    "How work is checked": "My integrity", "My work": "My integrity",
    "Check a draft": "My integrity", "My cases": "My integrity",
    "My AI-writing readings": "My integrity",
    "Review queue": "Review", "Documents": "Review", "Failed checks": "Review",
    "AI writing": "Review",
    "Module settings": "Modules and tools", "Statistics": "Modules and tools",
    "Tools": "Modules and tools",
    "Cases": "Cases", "Cases I raised": "Cases",
    "Settings": "Administration", "Records": "Administration", "Audit": "Administration",
    "Roles": "Administration",
}
NAV_BG, NAV_ACTIVE, NAV_FG = "#eef1f5", "#1f4e79", "#1a1a1a"


class IntegrityWindow(tk.Toplevel):
    def __init__(self, parent, who, officer):
        super().__init__(parent)
        self.who = who
        self.is_officer = officer
        self.title(f"{WINDOW_TITLE} — {who.username}")
        width = min(1400, self.winfo_screenwidth() - 40)
        height = min(900, self.winfo_screenheight() - 80)
        self.geometry(f"{width}x{height}")
        self.minsize(min(1200, width), min(800, height))
        role = "integrity officer" if officer else ("staff" if who.is_staff else "student")
        ttk.Label(self, text=f"Signed in as {who.username} ({role})",
                  padding=(10, 4)).pack(side="top", anchor="w")
        self.sections = _tabs(who, officer)       # [(label, class)] in sidebar order
        self.tabs = []                            # sections built so far
        self._built: dict[str, ttk.Frame] = {}
        self._buttons: dict[str, tk.Button] = {}
        self.current = None
        self._build_sidebar()
        self.content = ttk.Frame(self)
        self.content.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=(0, 6))
        if self.sections:
            self.select(self.sections[0][0])

    # ── sidebar ─────────────────────────────────────────────────────────

    def _build_sidebar(self):
        outer = tk.Frame(self, bg=NAV_BG, width=210)
        outer.pack(side="left", fill="y", padx=(6, 6), pady=(0, 6))
        canvas = tk.Canvas(outer, bg=NAV_BG, highlightthickness=0, width=200)
        bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=NAV_BG)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=200)
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="y", expand=True)
        bar.pack(side="right", fill="y")
        heading = None
        for label, _cls in self.sections:
            group = GROUPS.get(label, "")
            if group and group != heading:
                heading = group
                tk.Label(inner, text=group.upper(), bg=NAV_BG, fg="#5a6570",
                         font=("Segoe UI", 8, "bold"), anchor="w").pack(
                    fill="x", padx=10, pady=(12, 2))
            button = tk.Button(inner, text=label, anchor="w", relief="flat", bd=0,
                               bg=NAV_BG, fg=NAV_FG, activebackground="#d6dde6",
                               font=("Segoe UI", 10), padx=14, pady=6, cursor="hand2",
                               command=lambda lbl=label: self.select(lbl))
            button.pack(fill="x", padx=4, pady=1)
            self._buttons[label] = button

    def _mark_active(self, label):
        for name, button in self._buttons.items():
            active = name == label
            button.configure(bg=NAV_ACTIVE if active else NAV_BG,
                             fg="white" if active else NAV_FG,
                             activebackground="#2b5f8f" if active else "#d6dde6",
                             activeforeground="white" if active else NAV_FG)

    # ── sections ────────────────────────────────────────────────────────

    def _match(self, wanted):
        """The section label for ``wanted``: a label, or part of a label or
        of a section's class name (case-insensitive)."""
        wanted = str(wanted or "").lower()
        for label, cls in self.sections:
            if wanted == label.lower():
                return label
        for label, cls in self.sections:
            if wanted and (wanted in label.lower() or wanted in cls.__name__.lower()):
                return label
        return None

    def select(self, wanted):
        """Show a section (building it the first time). Returns the section
        object, or ``None`` when this person has no such section."""
        label = self._match(wanted)
        if label is None:
            return None
        if self.current is not None and self.current in self._built:
            self._built[self.current].pack_forget()
        section = self._built.get(label)
        if section is None:
            cls = dict(self.sections)[label]
            section = cls(self.content, self)
            self._built[label] = section
            self.tabs.append(section)
            if hasattr(section, "refresh") and hasattr(section, "tree") and hasattr(section,
                                                                                    "columns"):
                section.refresh()
        section.pack(fill="both", expand=True)
        self.current = label
        self._mark_active(label)
        return section

    def changed(self):
        """Something was written: refresh every section built so far."""
        for tab in self.tabs:
            if not hasattr(tab, "refresh"):
                continue
            try:
                tab.refresh()
            except tk.TclError:
                continue


def open_integrity_window(parent, auth):
    """Open the window for whoever is signed in to ``auth``. Returns the
    window, or ``None`` (with a message) when nobody is signed in."""
    user = signed_in_user(auth)
    if user is None:
        messagebox.showerror(TITLE, "Sign in to the University system to use Academic "
                                    "Integrity.", parent=parent)
        return None
    who = call(parent, access.from_user, user)
    if who is None:
        return None
    if not (who.is_student or who.is_staff):
        messagebox.showerror(TITLE, "Academic Integrity is for students and staff.",
                             parent=parent)
        return None
    officer = bool(call(parent, access.is_officer, who, quiet=True))
    return IntegrityWindow(parent, who, officer)
