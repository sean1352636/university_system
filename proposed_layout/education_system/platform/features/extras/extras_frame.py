"""
Extras & Tools Frame

A tk.Frame that provides access to shared extras utilities.
Can be embedded in any education system's sidebar/navigation.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
from pathlib import Path

EXTRAS_DIR = Path(__file__).parent


class ExtrasFrame(tk.Frame):
    """Frame listing all shared extras with launch buttons.

    Compatible with all 4 education system GUIs. Accepts the standard
    constructor signature: (parent, db_path=..., auth=...).
    """

    # Catalogue of extras: (display_name, relative_script_path, category)
    _TOOLS = [
        ("Calculator",          "calculator.py",                                   "Utilities"),
        ("Countdown Timer",     "countdown.py",                                    "Utilities"),
        ("Decision Maker",      "decision-maker/decision_maker.py",                "Utilities"),
        ("Query Builder",       "query-builder/query_builder.py",                  "Data & Analysis"),
        ("Log Analyzer",        "log-analyzer/log_analyzer.py",                    "Data & Analysis"),
        ("Password Analyzer",   "password-analyzer/password_analyzer.py",          "Security"),
        ("Hash Generator",      "hash-generator/hash_generator.py",                "Security"),
        ("Habit Tracker",       "habit-tracker/habit_tracker.py",                   "Tracking"),
        ("Skill Generator",     "random-skill-generator/random_skill_generator.py", "Tracking"),
    ]

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, bg="#f5f6fa", **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#2c3e50", height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Extras & Tools", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=15, pady=10)

        # Status
        self._status_var = tk.StringVar(value="Select a tool to launch")
        tk.Label(hdr, textvariable=self._status_var, font=("Helvetica", 10),
                 bg="#2c3e50", fg="#bdc3c7").pack(side="right", padx=15)

        # Scrollable content
        canvas = tk.Canvas(self, bg="#f5f6fa", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#f5f6fa")

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel
        def _on_enter(e):
            canvas.bind_all("<MouseWheel>",
                            lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))
            canvas.bind_all("<Button-4>",
                            lambda ev: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>",
                            lambda ev: canvas.yview_scroll(1, "units"))

        def _on_leave(e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

        # Group by category
        categories: dict[str, list[tuple[str, str]]] = {}
        for name, script, cat in self._TOOLS:
            categories.setdefault(cat, []).append((name, script))

        for cat, tools in categories.items():
            # Section header
            section = tk.LabelFrame(inner, text=cat, font=("Helvetica", 11, "bold"),
                                    bg="#f5f6fa", fg="#2c3e50", padx=10, pady=5)
            section.pack(fill="x", padx=5, pady=(8, 2))

            for i, (name, script) in enumerate(tools):
                path = EXTRAS_DIR / script
                btn = tk.Button(
                    section, text=name, font=("Helvetica", 10),
                    bg="#3498db", fg="white", activebackground="#2980b9",
                    activeforeground="white", relief="flat", cursor="hand2",
                    padx=12, pady=6,
                    command=lambda p=path, n=name: self._launch(p, n),
                )
                btn.grid(row=i // 3, column=i % 3, padx=5, pady=4, sticky="ew")

            for c in range(3):
                section.columnconfigure(c, weight=1)

        # Launch All button
        tk.Button(inner, text="Open Full Launcher", font=("Helvetica", 10, "bold"),
                  bg="#27ae60", fg="white", activebackground="#219a52",
                  activeforeground="white", relief="flat", cursor="hand2",
                  padx=15, pady=8,
                  command=self._open_launcher).pack(pady=15)

    def _launch(self, program_path: Path, name: str):
        """Launch a single extras tool."""
        if not program_path.exists():
            messagebox.showerror("Error", f"Tool not found:\n{program_path}")
            return

        self._status_var.set(f"Launching {name}...")
        self.update()

        try:
            env = os.environ.copy()
            env['DISPLAY'] = os.environ.get('DISPLAY', ':0')
            subprocess.Popen(
                [sys.executable, str(program_path)],
                cwd=str(program_path.parent),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._status_var.set(f"Launched {name}")
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch {name}:\n{e}")
            self._status_var.set(f"Failed: {name}")

    def _open_launcher(self):
        """Open the full extras launcher as a Toplevel window."""
        try:
            from education_system.platform.features.extras.launcher import launch_as_toplevel
            launch_as_toplevel(self.winfo_toplevel())
            self._status_var.set("Full launcher opened")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open launcher:\n{e}")
