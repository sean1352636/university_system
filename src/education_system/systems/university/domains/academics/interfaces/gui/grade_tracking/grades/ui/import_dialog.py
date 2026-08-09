import tkinter as tk
from tkinter import ttk

class ImportProgressDialog:
    def __init__(self, parent, total: int):
        self.window = tk.Toplevel(parent)
        self.progress = ttk.Progressbar(self.window, maximum=max(1, total))
        self.progress.pack(fill="x", padx=12, pady=12)
    def update(self, completed: int) -> None:
        self.progress["value"] = completed
        self.window.update_idletasks()
