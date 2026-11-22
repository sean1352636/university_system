"""History: the readings on the signed-in person's modules, newest first,
filtered by module and student (pickers, not free text). Double-click a
reading to see it whole."""

import logging
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)

_COLUMNS = (("result_id", "Reading", 70), ("id", "Submission", 80),
            ("student_id", "Student", 110), ("title", "Title", 220),
            ("course_code", "Module", 100), ("date", "Taken", 130), ("level", "Level", 160),
            ("strength", "Strength", 70), ("review", "Review", 120))


def create_history_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    header = ttk.Frame(frame)
    header.pack(fill="x", padx=15, pady=(15, 6))
    ttk.Label(header, text="History", style="Title.TLabel").pack(side="left")
    self.refresh_history_btn = ttk.Button(header, text="🔄 Refresh",
                                          command=self.refresh_history)
    self.refresh_history_btn.pack(side="right")

    filters = ttk.Frame(frame)
    filters.pack(fill="x", padx=15, pady=(0, 8))
    ttk.Label(filters, text="Module").pack(side="left")
    self.history_module = common.IdPicker(filters, common.modules(self), allow_blank=True,
                                          blank_label="(all my modules)", width=32)
    self.history_module.pack(side="left", padx=(4, 12))
    ttk.Label(filters, text="Student").pack(side="left")
    self.history_student = common.IdPicker(filters, (), allow_blank=True,
                                           blank_label="(all students)", width=32)
    self.history_student.pack(side="left", padx=4)

    def module_chosen(_event=None):
        module = self.history_module.value()
        self.history_student.set_choices(common.students(module) if module else ())
        self.refresh_history()

    self.history_module.bind("<<ComboboxSelected>>", module_chosen)
    self.history_student.bind("<<ComboboxSelected>>", lambda _e: self.refresh_history())
    ttk.Button(filters, text="Clear", command=self.clear_filter).pack(side="left", padx=6)

    tree_frame = ttk.Frame(frame)
    tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
    self.history_tree = ttk.Treeview(tree_frame, columns=[c[0] for c in _COLUMNS],
                                     show="headings", height=16)
    for col, label, width in _COLUMNS:
        self.history_tree.heading(col, text=label)
        self.history_tree.column(col, width=width, anchor="w")
    self.history_tree.tag_configure("review", background="#fff4e5")
    scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.history_tree.yview)
    self.history_tree.configure(yscrollcommand=scroll.set)
    self.history_tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    self.history_tree.bind("<Double-1>", self.view_submission_details)
    self.refresh_history()


def refresh_history(self):
    """Reload the readings for the chosen module and student."""
    tree = self.__dict__.get("history_tree")
    if tree is None or not tree.winfo_exists():
        return
    student = self.history_student.value()
    module = self.history_module.value()
    data = common.call(self, self.detector.get_submission_history, student_id=student,
                       limit=500)
    if data is None:
        return
    tree.delete(*tree.get_children())
    shown = 0
    for s in data.get("submissions", []):
        if module and s.get("course_code") != module:
            continue
        date = s.get("analysis_date") or s.get("submission_date") or ""
        try:
            date = datetime.fromisoformat(str(date).replace("Z", "+00:00")).strftime(
                "%Y-%m-%d %H:%M")
        except ValueError:
            pass
        review = "waits for review" if s.get("needs_review") else "below review level"
        tree.insert("", "end", tags=("review",) if s.get("needs_review") else (),
                    values=(s.get("result_id"), s.get("id"), s.get("student_id"),
                            s.get("title"), s.get("course_code"), date, s.get("level") or "—",
                            f"{float(s.get('ai_score') or 0):.2f}", review))
        shown += 1
    self.update_status(f"{shown} reading(s)")


def clear_filter(self):
    self.history_module.set("")
    self.history_student.set_choices(())
    self.refresh_history()


def view_submission_details(self, event=None):
    selection = self.history_tree.selection()
    if not selection:
        return
    submission_id = self.history_tree.item(selection[0])["values"][1]
    details = common.call(self, self.detector.get_submission_details, int(submission_id))
    if details is not None:
        self.show_submission_details_window(details)


def show_submission_details_window(self, details):
    """One reading: the facts, the indicators and the highlighted text."""
    win = tk.Toplevel(self.root)
    win.title(f"Reading {details.get('result_id')} — {details.get('title') or 'Untitled'}")
    win.geometry(f"{min(1000, win.winfo_screenwidth() - 60)}x"
                 f"{min(720, win.winfo_screenheight() - 100)}")
    win.transient(self.root)
    ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=6)
    facts = ttk.Frame(win, padding=(10, 6))
    facts.pack(fill="x")
    for label, key in (("Student", "student_id"), ("Module", "course_code"),
                       ("Assignment", "assignment_id"), ("Submission", "assignment_submission_id"),
                       ("Taken by", "checked_by"), ("Method", "method"),
                       ("Words", "word_count")):
        if details.get(key) not in (None, ""):
            ttk.Label(facts, text=f"{label}: {details.get(key)}").pack(side="left", padx=(0, 14))
    reading = details.get("detailed_results") or {}
    result = {**reading, "strength": reading.get("strength"),
              "needs_review": details.get("needs_review"), "detailed_results": reading}
    if not reading.get("indicators"):
        ttk.Label(win, wraplength=900, text=(
            "This reading was taken by the detector before indicators were recorded; its "
            "score is not reliable and is not shown.")).pack(anchor="w", padx=10, pady=6)
    common.show_reading(self, win, result, details.get("submission_text"))
    text = details.get("submission_text")
    if text and reading.get("indicators"):
        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self.create_sentences_tab(notebook, result, text)
