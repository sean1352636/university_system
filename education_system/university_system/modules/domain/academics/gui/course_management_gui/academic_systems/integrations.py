# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.constants import paths

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this GUI. Many database calls within this
# module reference 'courses.db' or str(DEFAULT_DB_PATH) directly. Without
# overriding, these calls would create separate database files in the
# working directory, leading to inconsistencies and missing tables. By
# redirecting those names to the central student_records.db located in
# university_system/data/db_files, we ensure a single database file is
# used across the entire application. Only connections specifying no
# database or targeting courses.db/student_records.db are redirected;
# all other database paths are left untouched.

_original_sqlite_connect = sqlite3.connect

def _patched_sqlite_connect(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "courses.db"):
            return _original_sqlite_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect
import re
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading
import os
import logging

# Import chart generation utility
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    plt = None
    Figure = None
    FigureCanvasTkAgg = None
    sns = None
    np = None

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.university_system.modules.domain.academics.services.course_management import (
        add_prerequisite, create_course, create_enhanced_course,
        display_enhanced_course_menu, find_alternative_courses,
        generate_course_analytics, generate_enrollment_report,
        initialize_enhanced_database, remove_prerequisite, search_courses,
        update_course, update_schedule, view_all_courses, view_course_details
    )
    ORIGINAL_MODULE_AVAILABLE = True
except ImportError:
    ORIGINAL_MODULE_AVAILABLE = False
    print(_("course_management.warnings.original_module_not_found"))

# Import academic system launchers
try:
    from education_system.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def create_academic_systems_tab(self):
    """Create the academic systems tab with LMS, Degree Audit, and Course Evaluation"""
    systems_frame = ttk.Frame(self.notebook)
    self.notebook.add(systems_frame, text=_("course_management.tabs.academic_systems"))

    # Title
    title_label = ttk.Label(systems_frame, text=_("course_management.labels.academic_management_systems"),
                           font=('Arial', 14, 'bold'))
    title_label.pack(pady=20)

    # Description
    desc_label = ttk.Label(systems_frame,
                          text=_("course_management.labels.academic_systems_description"),
                          wraplength=600, justify=tk.CENTER)
    desc_label.pack(pady=10)

    # Create scrollable canvas for systems
    canvas_frame = ttk.Frame(systems_frame)
    canvas_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

    canvas = tk.Canvas(canvas_frame, bg='#f0f0f0', highlightthickness=0)
    scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Systems container inside canvas
    container = ttk.Frame(canvas)
    canvas_window = canvas.create_window((0, 0), window=container, anchor='nw')

    # Configure canvas scrolling
    def configure_scroll(event):
        canvas.configure(scrollregion=canvas.bbox('all'))
        # Make the container width match the canvas width
        canvas.itemconfig(canvas_window, width=event.width - 20)

    canvas.bind('<Configure>', configure_scroll)
    container.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

    # Enable mouse wheel scrolling
    def on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    canvas.bind_all('<MouseWheel>', on_mousewheel)
    canvas.bind_all('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
    canvas.bind_all('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))

    # LMS System
    lms_frame = ttk.LabelFrame(container, text=_("course_management.labels.lms"), padding=20)
    lms_frame.pack(fill=tk.X, pady=10)

    lms_desc = ttk.Label(lms_frame,
                        text=_("course_management.labels.lms_description"),
                        wraplength=500)
    lms_desc.pack(pady=5)

    ttk.Button(lms_frame, text=_("course_management.buttons.launch_lms"),
              command=self.show_lms_gui,
              width=30).pack(pady=10)

    # Degree Audit System
    audit_frame = ttk.LabelFrame(container, text=_("course_management.labels.degree_audit"), padding=20)
    audit_frame.pack(fill=tk.X, pady=10)

    audit_desc = ttk.Label(audit_frame,
                          text=_("course_management.labels.degree_audit_description"),
                          wraplength=500)
    audit_desc.pack(pady=5)

    ttk.Button(audit_frame, text=_("course_management.buttons.launch_degree_audit"),
              command=self.show_degree_audit_gui,
              width=30).pack(pady=10)

    # Course Evaluation System
    eval_frame = ttk.LabelFrame(container, text=_("course_management.labels.course_evaluation"), padding=20)
    eval_frame.pack(fill=tk.X, pady=10)

    eval_desc = ttk.Label(eval_frame,
                         text=_("course_management.labels.course_evaluation_description"),
                         wraplength=500)
    eval_desc.pack(pady=5)

    ttk.Button(eval_frame, text=_("course_management.buttons.launch_course_evaluation"),
              command=self.show_course_evaluation_gui,
              width=30).pack(pady=10)

    # Status message if systems not available
    if not ACADEMIC_SYSTEMS_AVAILABLE:
        warning_label = ttk.Label(container,
                                text=_("course_management.messages.systems_not_available"),
                                foreground="orange")
        warning_label.pack(pady=10)


def show_lms_gui(self):
    """Switch to the LMS tab in the course management notebook."""
    try:
        for i in range(self.notebook.index("end")):
            if self.notebook.tab(i, "text") == _("lms.title"):
                self.notebook.select(i)
                return
        messagebox.showinfo("LMS", "LMS tab is available in the Course Management tabs above.")
    except Exception as e:
        messagebox.showerror(_("common.error"), f"Failed to open LMS tab: {e}")


def show_degree_audit_gui(self):
    """Launch the Degree Audit GUI"""
    try:
        if ACADEMIC_SYSTEMS_AVAILABLE:
            launch_degree_audit_gui(self.root, self.auth)
        else:
            messagebox.showerror(_("common.error"), _("course_management.messages.degree_audit_not_available"))
    except Exception as e:
        messagebox.showerror(_("common.error"), _("course_management.messages.degree_audit_launch_failed").format(error=e))


def show_course_evaluation_gui(self):
    """Launch the Course Evaluation GUI"""
    try:
        if ACADEMIC_SYSTEMS_AVAILABLE:
            launch_course_evaluation_gui(self.root, self.auth)
        else:
            messagebox.showerror(_("common.error"), _("course_management.messages.course_evaluation_not_available"))
    except Exception as e:
        messagebox.showerror(_("common.error"), _("course_management.messages.course_evaluation_launch_failed").format(error=e))
