"""Section chooser shared by the two student-facing registration screens.

A module that runs in sections cannot be joined without naming one — the
enrolment gate returns ``BLOCK_SECTION_REQUIRED`` with the open sections
attached. Both registration GUIs need the same small dialog to turn that block
into a choice, so it lives here rather than twice.

Modules with no sections never reach this: the gate raises no section block,
and registration stays module-level exactly as before.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional


class SectionPickerDialog(tk.Toplevel):
    """Modal chooser listing a module's open sections.

    ``result`` holds the chosen section id after the dialog closes, or None if
    the student cancelled. Full sections are shown but not selectable — seeing
    that the 9am group is full is more use than it silently missing.
    """

    def __init__(self, parent, module_code: str, sections: list[dict[str, Any]]):
        super().__init__(parent)
        self.result: Optional[Any] = None
        self._sections = sections

        self.title(f"Choose a section — {module_code}")
        self.transient(parent)
        self.resizable(False, False)

        ttk.Label(
            self,
            text=f"{module_code} runs in sections. Choose the one you will attend:",
            font=("Arial", 11),
        ).pack(padx=15, pady=(15, 10), anchor="w")

        cols = ("section", "when", "mode", "instructor", "seats")
        self.tree = ttk.Treeview(self, columns=cols, show="headings",
                                 height=min(8, max(3, len(sections))))
        for col, title, width in (
            ("section", "Section", 90),
            ("when", "Location / term", 170),
            ("mode", "Delivery", 100),
            ("instructor", "Instructor", 150),
            ("seats", "Seats", 90),
        ):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width,
                             anchor="center" if col in ("section", "seats") else "w")
        self.tree.pack(padx=15, fill=tk.BOTH, expand=True)

        for sec in sections:
            capacity = sec.get("capacity") or 0
            enrolled = sec.get("enrolled", 0)
            seats = f"{enrolled}/{capacity}" if capacity else f"{enrolled}/–"
            label = f"{sec.get('location') or ''} {sec.get('term_id') or ''}".strip() or "—"
            self.tree.insert(
                "", tk.END, iid=str(sec["id"]),
                values=(sec.get("section_number") or sec["id"], label,
                        sec.get("delivery_mode") or "—",
                        sec.get("instructor") or "—",
                        seats + (" FULL" if sec.get("full") else "")),
                tags=("full",) if sec.get("full") else (),
            )
        self.tree.tag_configure("full", foreground="#888888")

        selectable = [s for s in sections if not s.get("full")]
        if selectable:
            self.tree.selection_set(str(selectable[0]["id"]))

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=15, pady=12)
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Choose", command=self._choose).pack(side=tk.RIGHT, padx=6)
        self.tree.bind("<Double-1>", lambda _e: self._choose())

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()

    def _choose(self):
        selection = self.tree.selection()
        if not selection:
            return
        chosen = next((s for s in self._sections
                       if str(s["id"]) == selection[0]), None)
        if chosen is None or chosen.get("full"):
            return
        self.result = chosen["id"]
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def choose_section(parent, module_code: str, sections: list[dict[str, Any]]):
    """Show the chooser and return the selected section id (None if cancelled).

    With a single open section there is nothing to decide, so it is returned
    without troubling the student.
    """
    if not sections:
        return None
    open_sections = [s for s in sections if not s.get("full")]
    if len(open_sections) == 1 and len(sections) == 1:
        return open_sections[0]["id"]
    dialog = SectionPickerDialog(parent, module_code, sections)
    parent.wait_window(dialog)
    return dialog.result
