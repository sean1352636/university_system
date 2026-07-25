#!/usr/bin/env python3
"""
Shared Extras & Tools Launcher GUI

A launcher for utilities and tools shared across all education systems.
Location: education_system/shared/extras/
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import sys
from pathlib import Path


class ExtrasLauncher:
    """Launcher GUI for shared extras utilities."""

    def __init__(self, root, standalone=True):
        self.root = root
        self.standalone = standalone
        self.root.title("Extras & Tools Launcher")
        self.root.geometry("900x600")
        self.root.minsize(700, 500)

        self.base_dir = Path(__file__).parent
        self.running_processes = []

        self.setup_style()
        self.setup_gui()
        self.load_programs()

    def setup_style(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

    def setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        self._create_header(main_frame)
        self._create_nav_panel(main_frame)
        self._create_content_area(main_frame)
        self._show_welcome()

    def _create_header(self, parent):
        header = ttk.LabelFrame(parent, text="Extras & Tools Launcher", padding="10")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(header, text="Launch utilities and tools",
                  font=('Arial', 11)).grid(row=0, column=0, sticky="w")

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(header, text="Status:").grid(row=0, column=1, sticky="e", padx=(20, 5))
        ttk.Label(header, textvariable=self.status_var).grid(row=0, column=2, sticky="w")

        ttk.Button(header, text="Close",
                   command=self.close_launcher).grid(row=0, column=3, padx=(20, 0))
        header.columnconfigure(0, weight=1)

    def _create_nav_panel(self, parent):
        nav_frame = ttk.LabelFrame(parent, text="Categories", padding="5")
        nav_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        self.nav_buttons_frame = ttk.Frame(nav_frame)
        self.nav_buttons_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def _create_content_area(self, parent):
        self.content_frame = ttk.LabelFrame(parent, text="Programs", padding="10")
        self.content_frame.grid(row=1, column=1, sticky="nsew")
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        self.content_canvas = tk.Canvas(self.content_frame, highlightthickness=0, bg='#f0f0f0')
        scrollbar_y = ttk.Scrollbar(self.content_frame, orient="vertical",
                                     command=self.content_canvas.yview)

        self.programs_frame = ttk.Frame(self.content_canvas)
        self.canvas_window = self.content_canvas.create_window(
            (0, 0), window=self.programs_frame, anchor="nw")

        self.content_canvas.configure(yscrollcommand=scrollbar_y.set)
        self.content_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")

        self.programs_frame.bind("<Configure>", self._on_frame_configure)
        self.content_canvas.bind("<Configure>", self._on_canvas_configure)
        self.content_canvas.bind('<Enter>', self._bind_mousewheel)
        self.content_canvas.bind('<Leave>', self._unbind_mousewheel)

    def _on_frame_configure(self, event):
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.content_canvas.itemconfig(self.canvas_window, width=event.width)

    def _bind_mousewheel(self, event):
        self.content_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.content_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.content_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, event):
        self.content_canvas.unbind_all("<MouseWheel>")
        self.content_canvas.unbind_all("<Button-4>")
        self.content_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.content_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.content_canvas.yview_scroll(1, "units")

    def _show_welcome(self):
        self._clear_content()
        self.content_frame.configure(text="Programs")

        frame = ttk.Frame(self.programs_frame)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(frame, text="Extras & Tools",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        text = (
            "Select a category from the left panel to browse available tools.\n\n"
            "Categories:\n"
            "  Utilities - Calculator, countdown timer, decision maker\n"
            "  Data & Analysis - Query builder, log analyzer, JSON tools\n"
            "  Security - Password analyzer, hash generator\n"
            "  Tracking - Habit tracker, skill generator, evidence organizer\n\n"
            "Click any tool button to launch it."
        )
        ttk.Label(frame, text=text, justify="left", wraplength=500).pack(pady=10)
        self._update_canvas()

    def _clear_content(self):
        for widget in self.programs_frame.winfo_children():
            widget.destroy()

    def _update_canvas(self):
        self.programs_frame.update_idletasks()
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        self.content_canvas.yview_moveto(0)

    def load_programs(self):
        """Define categories and populate navigation."""
        self.categories = {
            "Utilities": [
                ("Calculator", self.base_dir / "calculator.py"),
                ("Countdown Timer", self.base_dir / "countdown.py"),
                ("Decision Maker", self.base_dir / "decision-maker" / "decision_maker.py"),
            ],
            "Data & Analysis": [
                ("Query Builder", self.base_dir / "query-builder" / "query_builder.py"),
                ("Log Analyzer", self.base_dir / "log-analyzer" / "log_analyzer.py"),
            ],
            "Security": [
                ("Password Analyzer", self.base_dir / "password-analyzer" / "password_analyzer.py"),
                ("Hash Generator", self.base_dir / "hash-generator" / "hash_generator.py"),
            ],
            "Tracking": [
                ("Habit Tracker", self.base_dir / "habit-tracker" / "habit_tracker.py"),
                ("Skill Generator", self.base_dir / "random-skill-generator" / "random_skill_generator.py"),
            ],
        }

        for name in self.categories:
            btn = ttk.Button(
                self.nav_buttons_frame, text=name,
                command=lambda n=name: self._show_category(n))
            btn.pack(fill="x", pady=3, padx=2)

        # Show All button
        ttk.Separator(self.nav_buttons_frame).pack(fill="x", pady=6)
        ttk.Button(
            self.nav_buttons_frame, text="Show All",
            command=self._show_all).pack(fill="x", pady=3, padx=2)

    def _show_category(self, category_name):
        self._clear_content()
        self.content_frame.configure(text=f"Programs - {category_name}")

        grid_frame = ttk.Frame(self.programs_frame)
        grid_frame.pack(fill="both", expand=True, padx=10, pady=10)

        items = self.categories[category_name]
        for i, (name, path) in enumerate(items):
            if path.exists():
                btn = ttk.Button(grid_frame, text=name,
                                 command=lambda p=path: self._run_program(p))
                btn.grid(row=i // 3, column=i % 3, padx=5, pady=5, sticky="ew")

        for c in range(3):
            grid_frame.columnconfigure(c, weight=1)

        self._update_canvas()
        self.status_var.set(f"Showing {category_name}")

    def _show_all(self):
        self._clear_content()
        self.content_frame.configure(text="All Programs")

        for cat_name, items in self.categories.items():
            section = ttk.LabelFrame(self.programs_frame, text=cat_name, padding="5")
            section.pack(fill="x", padx=10, pady=5)

            for i, (name, path) in enumerate(items):
                if path.exists():
                    btn = ttk.Button(section, text=name,
                                     command=lambda p=path: self._run_program(p))
                    btn.grid(row=i // 3, column=i % 3, padx=5, pady=3, sticky="ew")

            for c in range(3):
                section.columnconfigure(c, weight=1)

        self._update_canvas()
        self.status_var.set("Showing all programs")

    def _is_gui_program(self, program_path):
        try:
            with open(program_path, 'r', errors='ignore') as f:
                content = f.read(8192)
            gui_indicators = ['import tkinter', 'from tkinter', 'import pygame',
                              'from pygame', 'Tk()', 'tk.Tk()']
            return any(ind in content for ind in gui_indicators)
        except Exception:
            return False

    def _run_program(self, program_path):
        try:
            program_path = Path(program_path)
            self.status_var.set(f"Launching {program_path.stem}...")
            self.root.update()

            cwd = program_path.parent
            is_gui = self._is_gui_program(program_path)

            if sys.platform == "win32":
                process = subprocess.Popen(
                    [sys.executable, str(program_path)],
                    cwd=str(cwd),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            elif is_gui:
                env = os.environ.copy()
                env['DISPLAY'] = os.environ.get('DISPLAY', ':0')
                process = subprocess.Popen(
                    [sys.executable, str(program_path)],
                    cwd=str(cwd), env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            else:
                env = os.environ.copy()
                env['DISPLAY'] = os.environ.get('DISPLAY', ':0')
                title = program_path.stem.replace('_', ' ').title()
                terminal_cmd = None
                for term in ['xterm', 'gnome-terminal', 'konsole',
                             'xfce4-terminal', 'lxterminal']:
                    if subprocess.run(['which', term],
                                      capture_output=True).returncode == 0:
                        if term == 'gnome-terminal':
                            terminal_cmd = [
                                term, '--title', title, '--', 'bash', '-c',
                                f'{sys.executable} "{program_path}"; '
                                f'echo ""; echo "Press Enter to close..."; read']
                        else:
                            terminal_cmd = [
                                term, '-T', title, '-e',
                                f'{sys.executable} {program_path}; '
                                f'echo ""; echo "Press Enter to close..."; read']
                        break

                if terminal_cmd:
                    process = subprocess.Popen(
                        terminal_cmd, cwd=str(cwd), env=env,
                        start_new_session=True)
                else:
                    self._run_in_output_window(program_path, cwd)
                    return

            self.running_processes.append(process)
            self.status_var.set(f"Launched {program_path.stem}")

        except Exception as e:
            messagebox.showerror("Launch Error",
                                 f"Failed to launch {program_path.name}:\n{e}")
            self.status_var.set(f"Failed to launch {program_path.name}")

    def _run_in_output_window(self, program_path, cwd):
        import threading

        win = tk.Toplevel(self.root)
        win.title(program_path.stem.replace('_', ' ').title())
        win.geometry("700x500")

        text = tk.Text(win, wrap="word", font=('Consolas', 11),
                       bg='#1e1e1e', fg='#d4d4d4', insertbackground='white')
        scrollbar = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)

        text.insert("end", f"Running {program_path.name}...\n{'=' * 50}\n\n")
        text.configure(state="disabled")

        def run():
            try:
                result = subprocess.run(
                    [sys.executable, str(program_path)],
                    cwd=str(cwd), capture_output=True, text=True, timeout=60)
                output = result.stdout
                if result.stderr:
                    output += f"\n--- STDERR ---\n{result.stderr}"
                if result.returncode != 0:
                    output += f"\n\nProcess exited with code {result.returncode}"
            except subprocess.TimeoutExpired:
                output = "\n[Program timed out after 60 seconds]"
            except Exception as e:
                output = f"\n[Error: {e}]"

            def update():
                text.configure(state="normal")
                text.insert("end", output)
                text.insert("end", "\n\n--- Done ---")
                text.configure(state="disabled")
                text.see("end")
            win.after(0, update)

        threading.Thread(target=run, daemon=True).start()
        self.status_var.set(f"Running {program_path.stem}")

    def close_launcher(self):
        if self.standalone:
            if messagebox.askokcancel("Quit", "Close the launcher?"):
                self._cleanup()
                self.root.destroy()
        else:
            self._cleanup()
            self.root.destroy()

    def _cleanup(self):
        for process in self.running_processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass


def main():
    """Launch as standalone application."""
    root = tk.Tk()
    app = ExtrasLauncher(root, standalone=True)
    root.protocol("WM_DELETE_WINDOW", app.close_launcher)
    root.mainloop()


def launch_as_toplevel(parent_window):
    """Launch as a child window of another Tk application.

    Args:
        parent_window: The parent Tk window.

    Returns:
        ExtrasLauncher instance.
    """
    toplevel = tk.Toplevel(parent_window)
    app = ExtrasLauncher(toplevel, standalone=False)
    toplevel.protocol("WM_DELETE_WINDOW", app.close_launcher)
    return app


if __name__ == "__main__":
    main()
