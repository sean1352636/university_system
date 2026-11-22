import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import make_toplevel

class ImportProgressDialog:
    def __init__(self, parent, total: int):
        self.window = make_toplevel(parent)
        self.progress = ttk.Progressbar(self.window, maximum=max(1, total))
        self.progress.pack(fill="x", padx=12, pady=12)
    def update(self, completed: int) -> None:
        self.progress["value"] = completed
        self.window.update_idletasks()
