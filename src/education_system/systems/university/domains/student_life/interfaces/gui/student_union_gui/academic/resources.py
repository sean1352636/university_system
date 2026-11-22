
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
logger = logging.getLogger(__name__)
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.academic._hub_gui import (
    hub, hub_conn, owner_id, report_error, fill_tree, selected_id, ask_form, show_list, stars,
)

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
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
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
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class SharedResourcesDialog:
    """Shared academic resources platform"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.academic.resources.windows.shared_academic_resources', default="Shared Academic Resources"))
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_resources()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.labels.shared_academic_resources', default="📂 Shared Academic Resources"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Top button
        top_btn_frame = ttk.Frame(main_frame)
        top_btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(top_btn_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.upload_resource', default="📤 Upload Resource"),
                  command=self.upload_resource).pack(side='left')

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.labels.course', default="Course:")).pack(side='left', padx=(0, 5))
        self.course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=self.course_var, width=25, state='readonly')
        self.course_combo = course_combo
        course_combo['values'] = ('All Courses',)
        course_combo.current(0)
        course_combo.pack(side='left', padx=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.labels.type', default="Type:")).pack(side='left', padx=(0, 5))
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(filter_frame, textvariable=self.type_var, width=20, state='readonly')
        self.type_combo = type_combo
        type_combo['values'] = ('All Types',) + hub.RESOURCE_TYPES
        type_combo.current(0)
        type_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.filter', default="Filter"), command=self.load_resources).pack(side='left')

        # Resources list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.labels.available_resources', default="Available Resources"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Resource Name', 'Course', 'Type', 'Uploaded By', 'Date', 'Rating', 'Downloads')
        self.resources_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.resources_tree.heading(col, text=col)
            if col == 'Resource Name':
                self.resources_tree.column(col, width=250)
            elif col == 'Course':
                self.resources_tree.column(col, width=100)
            else:
                self.resources_tree.column(col, width=110)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.resources_tree.yview)
        self.resources_tree.configure(yscrollcommand=scrollbar.set)

        self.resources_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.download', default="Download"), command=self.download_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.preview', default="Preview"), command=self.preview_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.rate_resource', default="Rate Resource"), command=self.rate_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_resources(self):
        """Resources from shared_resources, with ratings from su_resource_ratings."""
        self._resources = {}
        course = self.course_var.get()
        course = None if course in ('', 'All Courses') else course
        rtype = self.type_var.get()
        rtype = None if rtype in ('', 'All Types') else rtype
        try:
            with hub_conn() as conn:
                self.course_combo['values'] = ['All Courses'] + hub.course_options(conn, owner_id(conn, self.auth))
                self.type_combo['values'] = ['All Types'] + hub.resource_types(conn)
                resources = hub.list_resources(conn, course, rtype)
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = []
        for r in resources:
            self._resources[r['resource_id']] = r
            rows.append((r['resource_id'], (r['resource_title'] or '(untitled)', r['subject'] or '-',
                                            r['resource_type'] or '-', r['uploader_name'],
                                            (r['upload_date'] or '')[:10],
                                            stars(r['avg_rating']), r['downloads'] or 0)))
        fill_tree(self.resources_tree, rows,
                  "No resources have been shared yet - use 'Upload Resource' to add one.")

    def _selected_resource(self, prompt="Please select a resource."):
        r = self._resources.get(selected_id(self.resources_tree))
        if not r:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.academic.resources.dialogs.warning', default="Warning"), prompt, parent=self.dialog)
        return r

    def upload_resource(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.dialog, title="Select a file to share")
        if not path:
            return
        try:
            with hub_conn() as conn:
                courses = hub.course_options(conn, owner_id(conn, self.auth))
                types = hub.resource_types(conn)
        except Exception as e:
            report_error(self.dialog, e)
            return
        form = ask_form(self.dialog, _t('gui.pastoral.student_union_gui.academic.resources.dialogs.upload_resource', default="Upload Resource"), [
            ('title', "Title:", 'entry', None, os.path.splitext(os.path.basename(path))[0]),
            ('course', "Course / module code:", 'combo', courses, courses[0] if courses else ''),
            ('type', "Resource type:", 'choice', types, types[0]),
            ('description', "Description:", 'text', None, ''),
        ], submit_text="Upload")
        if not form:
            return
        try:
            with hub_conn() as conn:
                hub.upload_resource(conn, owner_id(conn, self.auth), title=form['title'],
                                    course=form['course'], resource_type=form['type'],
                                    source_path=path, description=form['description'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.resources.dialogs.upload_resource', default="Upload Resource"),
                            f"'{form['title']}' is now shared.", parent=self.dialog)
        self.load_resources()

    def download_resource(self):
        r = self._selected_resource()
        if r and save_resource_copy(self.dialog, r):
            self.load_resources()

    def preview_resource(self):
        r = self._selected_resource(_t('gui.pastoral.student_union_gui.academic.resources.dialogs.please_select_a_resource_to_preview', default="Please select a resource to preview."))
        if not r:
            return
        dialog = ResourcePreviewDialog(self.dialog, self.auth, r['resource_title'], resource_id=r['resource_id'])
        self.dialog.wait_window(dialog.dialog)
        self.load_resources()

    def rate_resource(self):
        r = self._selected_resource()
        if r and rate_resource_dialog(self.dialog, self.auth, r):
            self.load_resources()


def save_resource_copy(parent, resource) -> bool:
    """Ask where to save, copy the stored file, count the download."""
    from tkinter import filedialog
    src = resource.get('file_path') or ''
    dest = filedialog.asksaveasfilename(parent=parent, title="Save resource as",
                                        initialfile=os.path.basename(src).split('_', 1)[-1] if src else '')
    if not dest:
        return False
    try:
        with hub_conn() as conn:
            hub.download_resource(conn, resource['resource_id'], dest)
    except Exception as e:
        report_error(parent, e)
        return False
    messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.resources.dialogs.download', default="Download"),
                        f"Saved to {dest}", parent=parent)
    return True


def rate_resource_dialog(parent, auth, resource) -> bool:
    form = ask_form(parent, _t('gui.pastoral.student_union_gui.academic.resources.dialogs.rate_resource', default="Rate Resource") + f" - {resource['resource_title']}", [
        ('rating', "Your rating (1-5):", 'spin', (1, 5), 5),
    ], submit_text="Rate")
    if not form:
        return False
    try:
        with hub_conn() as conn:
            avg = hub.rate_resource(conn, resource['resource_id'], owner_id(conn, auth), form['rating'])
    except Exception as e:
        report_error(parent, e)
        return False
    messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.resources.dialogs.rate', default="Rate"),
                        f"Thanks - your rating is saved. Average now {avg:.1f}/5.", parent=parent)
    return True



class ResourcePreviewDialog:
    """Dialog for previewing academic resources"""

    def __init__(self, parent, auth_manager, resource_name, resource_id=None):
        self.parent = parent
        self.auth = auth_manager
        self.resource_name = resource_name
        self.resource = None
        try:
            with hub_conn() as conn:
                if resource_id is None:
                    match = [r for r in hub.list_resources(conn) if r['resource_title'] == resource_name]
                    self.resource = match[0] if match else None
                else:
                    self.resource = hub.get_resource(conn, resource_id)
        except Exception:
            logger.debug("resource lookup failed", exc_info=True)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Preview: {resource_name}")
        self.dialog.geometry("800x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(header_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.labels.resource_preview', default="Resource Preview"), font=('Arial', 14, 'bold')).pack(side='left')

        # Resource info
        info_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.labels.resource_information', default="Resource Information"))
        info_frame.pack(fill='x', pady=(0, 15))

        info_grid = ttk.Frame(info_frame)
        info_grid.pack(padx=15, pady=10, fill='x')

        r = self.resource or {}
        rating = stars(r.get('avg_rating'))
        if r:
            rating += f" ({r.get('rating_count') or 0} ratings, {r.get('downloads') or 0} downloads)"
        info = [
            (_t('gui.pastoral.student_union_gui.academic.resources.labels.name', default="Name:"), self.resource_name),
            (_t('gui.pastoral.student_union_gui.academic.resources.labels.type', default="Type:"), r.get('resource_type') or '-'),
            (_t('gui.pastoral.student_union_gui.academic.resources.labels.course', default="Course:"), r.get('subject') or '-'),
            (_t('gui.pastoral.student_union_gui.academic.resources.labels.uploaded_by', default="Uploaded by:"), r.get('uploader_name') or '-'),
            (_t('gui.pastoral.student_union_gui.academic.resources.labels.rating', default="Rating:"), rating if r else '-'),
        ]
        for i, (label, value) in enumerate(info):
            ttk.Label(info_grid, text=label, font=('Arial', 10, 'bold')).grid(row=i, column=0, sticky='w', pady=5)
            ttk.Label(info_grid, text=value).grid(row=i, column=1, sticky='w', padx=10, pady=5)

        # Preview content
        preview_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.labels.content_preview', default="Content Preview"))
        preview_frame.pack(fill='both', expand=True, pady=(0, 15))

        self.preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, font=('Courier', 10))
        self.preview_text.pack(fill='both', expand=True, padx=10, pady=10)

        if not self.resource:
            content = "This resource could not be found."
        else:
            text = hub.preview_text(r.get('file_path'))
            if text is None:
                content = ((r.get('description') or '') + "\n\n" if r.get('description') else '') + \
                    "A text preview is not available for this file. Download it to open it."
            else:
                content = text
                if len(text) >= hub.PREVIEW_CHARS:
                    content += "\n\n... (preview truncated - download for the full file)"
        self.preview_text.insert(1.0, content)
        self.preview_text.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.download_full_resource', default="Download Full Resource"),
                  command=self.download_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.rate_resource', default="Rate Resource"),
                  command=self.rate_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.resources.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def rate_resource(self):
        if self.resource:
            rate_resource_dialog(self.dialog, self.auth, self.resource)

    def download_resource(self):
        if self.resource:
            save_resource_copy(self.dialog, self.resource)
        else:
            messagebox.showwarning("Download", "This resource could not be found.", parent=self.dialog)

