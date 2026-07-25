from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.systems.university.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.systems.university.infrastructure.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path

# This ensures full backward compatibility
try:
    from education_system.systems.university.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']

    # Import the ModuleScheduler class from the document
    try:
        from education_system.systems.university.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

def launch_cli_mode(self):
    """Launch the CLI mode in a separate window"""
    try:
        # Create a new window for CLI mode
        cli_window = tk.Toplevel(self.root)
        cli_window.title(_t("module_scheduling.cli.window_title"))
        cli_window.geometry("800x600")

        # CLI text area
        cli_frame = ttk.Frame(cli_window)
        cli_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(cli_frame, text=_t("module_scheduling.cli.title"), font=('Arial', 14, 'bold')).pack(pady=5)

        # Instructions
        instructions = _t("module_scheduling.cli.instructions")

        ttk.Label(cli_frame, text=instructions, justify=tk.LEFT).pack(pady=5)

        # CLI output area
        cli_output = scrolledtext.ScrolledText(cli_frame, height=20, font=('Courier', 10))
        cli_output.pack(fill=tk.BOTH, expand=True, pady=5)

        # CLI input
        input_frame = ttk.Frame(cli_frame)
        input_frame.pack(fill=tk.X, pady=5)

        ttk.Label(input_frame, text=_t("module_scheduling.cli.command_label")).pack(side=tk.LEFT)
        cli_input = ttk.Entry(input_frame)
        cli_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        def execute_cli_command():
            command = cli_input.get().strip().lower()
            cli_input.delete(0, tk.END)

            cli_output.insert(tk.END, f"> {command}\n")

            if command == 'exit':
                cli_window.destroy()
            elif command == 'help':
                help_text = """
Available Commands:
- help: Show this help message
- menu: Show main menu options
- stats: Show system statistics
- conflicts: Check for conflicts
- backup: Create a backup
- exit: Close CLI mode

For full CLI functionality, run the original script from command line.
                """
                cli_output.insert(tk.END, help_text + "\n")
            elif command == 'menu':
                cli_output.insert(tk.END, "Main menu options available in the GUI tabs above.\n")
            elif command == 'stats':
                try:
                    from education_system.systems.university.infrastructure.database.db import sqlite3
                    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                        cursor = conn.cursor()

                        cursor.execute("SELECT COUNT(*) FROM module_schedule")
                        schedules = cursor.fetchone()[0]
                        cursor.execute("SELECT COUNT(*) FROM rooms WHERE is_active = 1")
                        rooms = cursor.fetchone()[0]
                        cursor.execute("SELECT COUNT(*) FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
                        instructors = cursor.fetchone()[0]

                    stats_text = f"""
System Statistics:
- Total Schedules: {schedules}
- Active Rooms: {rooms}
- Active Instructors: {instructors}
                    """
                    cli_output.insert(tk.END, stats_text + "\n")
                except Exception as e:
                    cli_output.insert(tk.END, f"Error getting stats: {e}\n")
            elif command == 'conflicts':
                try:
                    conflicts = self.scheduler.detect_all_conflicts()
                    cli_output.insert(tk.END, f"Detected {len(conflicts)} conflicts.\n")
                except Exception as e:
                    cli_output.insert(tk.END, f"Error detecting conflicts: {e}\n")
            elif command == 'backup':
                try:
                    backup_path = self.scheduler.create_backup(description="CLI backup")
                    if backup_path:
                        cli_output.insert(tk.END, f"Backup created: {backup_path}\n")
                    else:
                        cli_output.insert(tk.END, "Failed to create backup.\n")
                except Exception as e:
                    cli_output.insert(tk.END, f"Error creating backup: {e}\n")
            else:
                cli_output.insert(tk.END, f"Unknown command: {command}\nType 'help' for available commands.\n")

            cli_output.see(tk.END)

        ttk.Button(input_frame, text=_t("module_scheduling.cli.execute"), command=execute_cli_command).pack(side=tk.RIGHT)

        # Bind Enter key
        cli_input.bind('<Return>', lambda e: execute_cli_command())

        cli_output.insert(tk.END, _t("module_scheduling.cli.welcome") + "\n")
        cli_output.insert(tk.END, _t("module_scheduling.cli.help_prompt") + "\n\n")

        cli_input.focus()

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("module_scheduling.cli.launch_failed", error=str(e)), parent=self.root)

# Import the GUI class and assign the method
from education_system.systems.university.interfaces.gui.academics.module_scheduling.main_gui import ModuleSchedulingGUI
ModuleSchedulingGUI.launch_cli_mode = launch_cli_mode
