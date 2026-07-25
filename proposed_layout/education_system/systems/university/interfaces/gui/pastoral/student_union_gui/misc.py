import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domain.pastoral.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False

# Import local classes - use lazy imports to avoid circular dependencies
def _get_student_union_gui():
    from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.core.main_gui import StudentUnionGUI
    return StudentUnionGUI

def _get_event_attendance_dialog():
    from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.events.event_dialogs import EventAttendanceDialog
    return EventAttendanceDialog


def main():
    """Main entry point"""
    import argparse
    from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.core.utilities import launch_cli, launch_gui

    parser = argparse.ArgumentParser(description='Student Union Management System')
    parser.add_argument('--mode', choices=['gui', 'cli', 'auto'], default='auto',
                       help='Interface mode (default: auto)')
    parser.add_argument('--db-path', default=str(DEFAULT_DB_PATH),
                       help='Database file path (default: student_records.db)')

    args = parser.parse_args()

    if args.mode == 'cli':
        if CLI_AVAILABLE:
            launch_cli()
        else:
            print("CLI mode not available. Starting GUI instead.")
            launch_gui()
    elif args.mode == 'gui':
        launch_gui()
    else:  # auto mode
        # Try to determine best mode based on environment
        try:
            import tkinter
            launch_gui()
        except ImportError:
            print("GUI not available. Starting CLI mode.")
            if CLI_AVAILABLE:
                launch_cli()
            else:
                print("Neither GUI nor CLI available. Please check your installation.")


# ============================================================================
# NEW DIALOG CLASSES FOR 26 MISSING FUNCTIONS
# ============================================================================


def launch_student_union_gui(auth_manager=None):
    """Launch the Student Union GUI application"""
    # Use lazy import to avoid circular dependencies
    StudentUnionGUI = _get_student_union_gui()
    app = StudentUnionGUI()

    # Set auth_manager if provided
    if auth_manager:
        app.auth_manager = auth_manager

    # Set window icon if available
    try:
        # You could set an icon here if you have one
        # app.root.iconbitmap('path/to/icon.ico')
        pass
    except (tk.TclError, OSError, IOError):
        pass

    return app.root, app

# Backwards compatibility function - FIXED: Added missing import and error handling

def _on_mousewheel(self, event):
    """Handle mouse wheel scrolling on sidebar"""
    self.sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")


def open_event_attendance_dialog(self):
    """Open event attendance tracking"""
    EventAttendanceDialog = _get_event_attendance_dialog()
    dialog = EventAttendanceDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
# THIRD ROUND - Virtual Events & Knowledge Sharing

def display_result(self, text_widget: scrolledtext.ScrolledText, content: str):
    """Display content in the specified text widget"""
    text_widget.delete(1.0, tk.END)
    text_widget.insert(tk.END, content)
    text_widget.see(tk.END)


def capture_cli_output(self, func, *args, **kwargs):
    """Capture output from CLI functions by redirecting stdout"""
    from io import StringIO

    # Save original stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        # Call the function
        result = func(*args, **kwargs)
        output = captured_output.getvalue()
        return output, result
    except (tk.TclError, AttributeError) as e:
        return f"Error: {str(e)}", None
    finally:
        # Restore stdout
        sys.stdout = old_stdout




def run_in_thread(self, func, callback=None, *args, **kwargs):
    """Run a function in a separate thread to prevent GUI freezing"""
    def thread_worker():
        try:
            output, result = self.capture_cli_output(func, *args, **kwargs)
            if callback:
                self.master.after(0, callback, output, result)
        except (tk.TclError, AttributeError) as e:
            error_msg = f"Error: {str(e)}"
            if callback:
                self.master.after(0, callback, error_msg, None)

    thread = threading.Thread(target=thread_worker)
    thread.daemon = True
    thread.start()

# Club Management GUI Methods

def call_cli_function(self, function_name: str, text_widget: scrolledtext.ScrolledText,
                     status_message: str = None):
    """Generic method to call CLI functions and display results"""
    if not hasattr(student_union_cli, function_name):
        messagebox.showerror(_t("common.error"), _t("student_union.cli.function_not_found", function=function_name))
        return

    if status_message:
        self.update_status(status_message)

    func = getattr(student_union_cli, function_name)

    def callback(output, result):
        self.display_result(text_widget, output)
        if status_message:
            self.update_status(f"{status_message} - Complete")

    self.run_in_thread(func, callback)

# GUI methods for advanced features

def manage_event_attendance(self):
    """Manage event attendance with GUI dialog"""
    try:
        EventAttendanceDialog = _get_event_attendance_dialog()
        dialog = EventAttendanceDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t("common.error"), _t("student_union.dialogs.open_failed", error=str(e)))


