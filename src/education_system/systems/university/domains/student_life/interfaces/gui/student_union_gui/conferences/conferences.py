
import logging

logger = logging.getLogger(__name__)

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
import shutil
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.email.email_service.core import send_email
from education_system.systems.university.infrastructure.database.db import get_connection
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

from tkinter import filedialog

from education_system.systems.university.domains.student_life.domain.student_life.student_union.events import (
    conferences as conf_service,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
    current_student_id as _current_student_id,
)

_K = 'gui.pastoral.student_union_gui.conferences.conferences'


def _k(kind, key):
    return f"{_K}.{kind}.{key}"


def _fmt_date(value):
    """'2027-05-15' -> 'May 15, 2027' (falls back to the raw value)."""
    if not value:
        return "TBA"
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').strftime('%b %d, %Y')
    except ValueError:
        return str(value)


def _fmt_status(value):
    return (value or '').replace('_', ' ').title()


class _ConferenceUI:
    """Shared plumbing for the three conference windows.

    Every read and write goes through ``student_union.events.conferences``;
    this class only owns the connection, the signed-in identity and the
    small dialogs the windows share.
    """

    dialog = None
    auth = None

    # -- data access ------------------------------------------------------
    _schema_ready = False

    def _conn(self):
        conn = get_connection()
        if not _ConferenceUI._schema_ready:
            conf_service.ensure_schema(conn)
            _ConferenceUI._schema_ready = True
        return conn

    def _run(self, fn, *args, **kwargs):
        """Run a service call on a fresh connection; show refusals honestly."""
        conn = None
        try:
            conn = self._conn()
            return fn(conn, *args, **kwargs)
        except conf_service.ConferenceError as e:
            self._warn(str(e))
        except sqlite3.IntegrityError as e:
            self._error(_t(_k('dialogs', 'record_rejected'),
                           default="The record was rejected by the database:") + f"\n{e}")
        except sqlite3.Error as e:
            logger.exception("conference database error")
            self._error(_t(_k('dialogs', 'database_error'), default="Database error:") + f"\n{e}")
        finally:
            if conn is not None:
                conn.close()
        return None

    def _owner_id(self):
        conn = None
        try:
            conn = get_connection()
            return _current_student_id(conn.cursor(), self.auth)
        except sqlite3.Error:
            return None
        finally:
            if conn is not None:
                conn.close()

    def _user(self):
        return (getattr(self.auth, 'current_user', None) or {}) if self.auth else {}

    def _display_name(self):
        user = self._user()
        full = " ".join(p for p in (user.get('first_name'), user.get('last_name')) if p)
        return full or user.get('full_name') or user.get('name') or user.get('username') or ''

    def _username(self):
        return self._user().get('username') or ''

    def _user_type(self):
        role = (self._user().get('role') or '').lower()
        return 'student' if role in ('', 'student') else 'staff'

    def _is_organiser(self):
        user = self._user()
        if not user:
            return False
        if (user.get('role') or '').lower() in ('admin', 'superadmin', 'union_rep'):
            return True
        try:
            return bool(self.auth.check_permission('organize_conferences'))
        except Exception:
            return False

    def _require_organiser(self):
        if self._is_organiser():
            return True
        self._warn(_t(_k('dialogs', 'organisers_only'),
                      default="Only conference organisers (union reps and admins) can do this."))
        return False

    def _require_signed_in(self):
        owner = self._owner_id()
        if not owner:
            self._warn(_t(_k('dialogs', 'sign_in_required'),
                          default="You must be signed in to do this."))
        return owner

    # -- messages (always parented to this window) ------------------------
    def _info(self, text, title=None):
        messagebox.showinfo(title or _t(_k('dialogs', 'success'), default="Success"),
                            text, parent=self.dialog)

    def _warn(self, text, title=None):
        messagebox.showwarning(title or _t(_k('dialogs', 'warning'), default="Warning"),
                               text, parent=self.dialog)

    def _error(self, text):
        messagebox.showerror(_t(_k('dialogs', 'error'), default="Error"), text, parent=self.dialog)

    def _ask(self, text, title=None):
        return messagebox.askyesno(title or _t(_k('dialogs', 'confirm'), default="Confirm"),
                                   text, parent=self.dialog)

    def _email(self, to, subject, body):
        if not to:
            return False
        try:
            send_email(to, subject, body)
            return True
        except Exception:
            logger.debug("conference e-mail failed", exc_info=True)
            return False

    # -- shared widgets ----------------------------------------------------
    def _conference_picker(self, parent, on_change=None, label=None):
        """A 'Conference:' combobox listing real conferences."""
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=(0, 10))
        ttk.Label(row, text=label or _t(_k('labels', 'conference'), default="Conference:")).pack(
            side='left', padx=(0, 10))
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, width=60, state='readonly')
        combo.pack(side='left', fill='x', expand=True)
        holder = {'map': {}}

        def reload(select_id=None):
            confs = self._run(conf_service.list_conferences) or []
            holder['map'] = {f"{c['title']} ({_fmt_date(c['start_date'])})": c['event_id']
                             for c in confs}
            combo['values'] = list(holder['map'])
            if not confs:
                var.set('')
                return
            names = list(holder['map'])
            pick = next((n for n, i in holder['map'].items() if i == select_id), None)
            if pick is None and var.get() in holder['map']:
                pick = var.get()
            var.set(pick or names[0])

        def current():
            return holder['map'].get(var.get())

        if on_change:
            combo.bind('<<ComboboxSelected>>', lambda e: on_change())
        reload()
        return current, reload

    def _form(self, title, fields, initial=None):
        """Modal form. ``fields`` = [(key, label, kind, options)] where kind is
        'entry' | 'text' | 'combo' | 'spin'. Returns a dict or None."""
        initial = initial or {}
        win = tk.Toplevel(self.dialog)
        win.title(title)
        win.transient(self.dialog)
        win.grab_set()
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill='both', expand=True)
        widgets = {}
        for r, (key, label, kind, options) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky='nw', pady=4, padx=(0, 10))
            if kind == 'text':
                w = scrolledtext.ScrolledText(frame, width=50, height=5, wrap=tk.WORD)
                if initial.get(key):
                    w.insert('1.0', str(initial[key]))
            elif kind == 'combo':
                w = ttk.Combobox(frame, width=48, state='readonly', values=list(options or ()))
                if initial.get(key) in (options or ()):
                    w.set(initial[key])
                elif options:
                    w.current(0)
            elif kind == 'spin':
                lo, hi = options
                w = ttk.Spinbox(frame, from_=lo, to=hi, width=10)
                w.set(initial.get(key, lo))
            else:
                w = ttk.Entry(frame, width=50)
                if initial.get(key) not in (None, ''):
                    w.insert(0, str(initial[key]))
            w.grid(row=r, column=1, sticky='ew', pady=4)
            widgets[key] = (kind, w)
        frame.columnconfigure(1, weight=1)
        result = {}

        def ok():
            for key, (kind, w) in widgets.items():
                result[key] = (w.get('1.0', 'end-1c') if kind == 'text' else w.get()).strip()
            win.destroy()

        btns = ttk.Frame(frame)
        btns.grid(row=len(fields), column=0, columnspan=2, sticky='ew', pady=(10, 0))
        ttk.Button(btns, text=_t(_k('buttons', 'save'), default="Save"), command=ok).pack(side='left')
        ttk.Button(btns, text=_t(_k('buttons', 'cancel'), default="Cancel"),
                   command=win.destroy).pack(side='right')
        self.dialog.wait_window(win)
        return result or None

    def _choose(self, title, prompt, options):
        """Pick one of ``options`` ({label: value}); returns the value or None."""
        if not options:
            return None
        data = self._form(title, [('choice', prompt, 'combo', list(options))])
        if not data or not data.get('choice'):
            return None
        return options.get(data['choice'])

    def _fill(self, tree, rows, empty_text, ncols):
        for item in tree.get_children():
            tree.delete(item)
        if not rows:
            tree.insert('', 'end', values=(empty_text,) + ('',) * (ncols - 1), tags=('empty',))
            return
        for iid, values in rows:
            tree.insert('', 'end', iid=str(iid), values=values)

    def _selected_id(self, tree, what):
        sel = [s for s in tree.selection() if 'empty' not in tree.item(s, 'tags')]
        if not sel:
            self._warn(_t(_k('dialogs', 'please_select'), default="Please select") + f" {what}.",
                       _t(_k('dialogs', 'no_selection'), default="No Selection"))
            return None
        return int(sel[0])

    def _set_text(self, widget, content):
        widget.config(state='normal')
        widget.delete('1.0', tk.END)
        widget.insert('1.0', content)
        widget.config(state='disabled')


def _paper_tracks():
    return ('Computer Science', 'Engineering', 'Social Sciences', 'Physical Sciences',
            'Life Sciences', 'Humanities', 'Business', 'Interdisciplinary', 'Other')


class AcademicConferencesDialog(_ConferenceUI):
    """Dialog for organizing academic conferences"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.conferences.conferences.windows.academic_conferences', default="Academic Conferences"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self._load_upcoming()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.academic_conferences_research', default="🎓 Academic Conferences & Research"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Button(main_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        # Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Upcoming conferences
        upcoming_frame = ttk.Frame(notebook)
        notebook.add(upcoming_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.upcoming_conferences', default="Upcoming Conferences"))

        ttk.Button(upcoming_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.register', default="Register"),
                  command=self._register_for_conference).pack(side='bottom', anchor='w', padx=10, pady=(0, 10))

        columns = ('Conference', 'Date', 'Papers', 'Speakers', 'Attendees')
        tree = ttk.Treeview(upcoming_frame, columns=columns, show='tree headings')

        for col in columns:
            tree.heading(col, text=col)
        tree.column('Conference', width=320)

        tree.pack(fill='both', expand=True, padx=10, pady=10)
        self._upcoming_tree = tree

        # Paper submissions
        papers_frame = ttk.Frame(notebook)
        notebook.add(papers_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.submit_paper', default="Submit Paper"))

        form = ttk.Frame(papers_frame)
        form.pack(padx=15, pady=15, fill='both', expand=True)

        self._paper_conf, self._reload_paper_conf = self._conference_picker(form)

        track_row = ttk.Frame(form)
        track_row.pack(fill='x', pady=(0, 10))
        ttk.Label(track_row, text=_t(_k('labels', 'track'), default="Track:")).pack(side='left', padx=(0, 10))
        self._track_combo = ttk.Combobox(track_row, values=_paper_tracks(), width=30)
        self._track_combo.pack(side='left')

        ttk.Label(form, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.paper_title', default="Paper Title:")).pack(anchor='w', pady=(0, 5))
        self._paper_title_entry = ttk.Entry(form, width=60)
        self._paper_title_entry.pack(fill='x', pady=(0, 15))

        ttk.Button(form, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.submit_paper', default="Submit Paper"),
                  command=self._submit_paper).pack(side='bottom', anchor='w')

        # File upload section
        self._selected_file_path = None
        upload_frame = ttk.Frame(form)
        upload_frame.pack(side='bottom', fill='x', pady=(0, 15))
        ttk.Label(upload_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.or_upload_file', default="Or upload file:")).pack(side='left', padx=(0, 10))
        self._file_label = ttk.Label(upload_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.no_file_selected', default="No file selected"))
        self._file_label.pack(side='left', padx=(0, 10))
        ttk.Button(upload_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.browse', default="Browse"),
                  command=self._browse_paper_file).pack(side='left')

        ttk.Label(form, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.abstract', default="Abstract:")).pack(anchor='w', pady=(0, 5))
        self._abstract_text = scrolledtext.ScrolledText(form, height=10, wrap=tk.WORD)
        self._abstract_text.pack(fill='both', expand=True, pady=(0, 15))

    def _load_upcoming(self):
        confs = self._run(conf_service.list_conferences, upcoming_only=True) or []
        self._fill(self._upcoming_tree,
                   [(c['event_id'], (c['title'], _fmt_date(c['start_date']), c['papers'],
                                     c['speakers'],
                                     f"{c['registrations']}/{c['max_capacity']}" if c['max_capacity']
                                     else c['registrations']))
                    for c in confs],
                   _t(_k('labels', 'no_upcoming_conferences'),
                      default="No upcoming conferences have been scheduled."), 5)

    def _get_user_email(self):
        """Look up the current user's email address."""
        user = self._user()
        if user.get('email'):
            return user['email']
        conn = None
        try:
            conn = get_connection()
            from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import contact_email
            return contact_email(conn.cursor(), _current_student_id(conn.cursor(), self.auth))
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        finally:
            if conn is not None:
                conn.close()
        return None

    def _register_for_conference(self):
        """Register for the selected conference."""
        event_id = self._selected_id(self._upcoming_tree,
                                     _t(_k('dialogs', 'a_conference'), default="a conference"))
        if event_id is None:
            return
        owner = self._require_signed_in()
        if not owner:
            return
        conf = self._run(conf_service.get_conference, event_id)
        if not conf:
            return
        if not self._ask(f"Register for '{conf['title']}'?",
                         _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.confirm_registration', default="Confirm Registration")):
            return
        reg = self._run(conf_service.register, event_id, owner,
                        attendee_name=self._display_name() or self._username(),
                        user_type=self._user_type())
        if reg is None:
            return
        sent = self._email(self._get_user_email(),
                           f"Conference Registration Confirmation: {conf['title']}",
                           f"You have been registered for '{conf['title']}'.\n\n"
                           f"Date: {_fmt_date(conf['start_date'])}\n"
                           f"Venue: {conf['location'] or 'TBA'}\n\nThank you for registering!")
        self._info(f"You have been registered for '{conf['title']}'."
                   + ("\nA confirmation email has been sent." if sent else
                      "\nNo confirmation e-mail could be sent (no address on file)."))
        self._load_upcoming()

    def _browse_paper_file(self):
        """Browse for a paper file to upload."""
        filename = filedialog.askopenfilename(
            parent=self.dialog,
            title=_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.select_paper_file', default="Select Paper File"),
            filetypes=[("PDF files", "*.pdf"), ("Word documents", "*.docx"), ("All files", "*.*")]
        )
        if filename:
            self._selected_file_path = filename
            self._file_label.config(text=os.path.basename(filename))

    def _submit_paper(self):
        """Store the paper against the chosen conference, with its file."""
        title = self._paper_title_entry.get().strip()
        if not title:
            self._warn(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.please_enter_a_paper_title', default="Please enter a paper title."),
                       _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.validation_error', default="Validation Error"))
            return
        event_id = self._paper_conf()
        if not event_id:
            self._warn(_t(_k('dialogs', 'no_conference_to_submit_to'),
                          default="There is no conference to submit to yet."))
            return
        owner = self._require_signed_in()
        if not owner:
            return
        abstract = self._abstract_text.get('1.0', tk.END).strip()
        if not abstract and not self._selected_file_path:
            self._warn(_t(_k('dialogs', 'abstract_or_file'),
                          default="Enter an abstract or attach the paper file."))
            return

        sub_id = self._run(conf_service.submit, event_id, kind='paper', title=title,
                           author_id=owner, author_name=self._display_name() or self._username(),
                           abstract=abstract, track=self._track_combo.get())
        if sub_id is None:
            return

        if self._selected_file_path:
            try:
                dest = conf_service.store_upload(self._selected_file_path, event_id, sub_id)
                self._run(conf_service.attach_file, sub_id, dest)
            except (OSError, conf_service.ConferenceError) as e:
                self._error(f"Your paper was submitted, but the file could not be stored: {e}")

        sent = self._email(self._get_user_email(), f"Paper Submission Confirmation: {title}",
                           f"Your paper '{title}' has been submitted.\n\n"
                           "You will be e-mailed when the organisers reach a decision.")
        self._info(f"Paper '{title}' submitted successfully."
                   + ("\nA confirmation email has been sent." if sent else ""))
        self._paper_title_entry.delete(0, tk.END)
        self._abstract_text.delete('1.0', tk.END)
        self._selected_file_path = None
        self._file_label.config(text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.no_file_selected', default="No file selected"))
        self._load_upcoming()


# ============================================================================
# CONFERENCE ORGANISATION
# ============================================================================


class AcademicConferencesOrganizerDialog(_ConferenceUI):
    """Organize and manage academic conferences"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.conferences.conferences.windows.academic_conference_organization', default="Academic Conference Organization"))
        self.dialog.geometry("1200x800")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh_all()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.academic_conference_organization', default="📚 Academic Conference Organization"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Button(main_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        # The conference the Submissions / Speakers / Schedule / Registration tabs show
        self._current_conf, self._reload_conf_picker = self._conference_picker(
            main_frame, on_change=self.refresh_detail_tabs,
            label=_t(_k('labels', 'working_on'), default="Working on:"))

        # Create notebook for conference management
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Conferences tab
        conferences_frame = ttk.Frame(notebook)
        notebook.add(conferences_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.conferences', default="Conferences"))
        self.create_conferences_tab(conferences_frame)

        # Paper Submissions tab
        submissions_frame = ttk.Frame(notebook)
        notebook.add(submissions_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.paper_submissions', default="Paper Submissions"))
        self.create_submissions_tab(submissions_frame)

        # Speakers tab
        speakers_frame = ttk.Frame(notebook)
        notebook.add(speakers_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.speakers', default="Speakers"))
        self.create_speakers_tab(speakers_frame)

        # Schedule tab
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.session_schedule', default="Session Schedule"))
        self.create_schedule_tab(schedule_frame)

        # Registration tab
        registration_frame = ttk.Frame(notebook)
        notebook.add(registration_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.attendee_registration', default="Attendee Registration"))
        self.create_registration_tab(registration_frame)

    # -- refresh ------------------------------------------------------------
    def refresh_all(self, select_id=None):
        self._reload_conf_picker(select_id)
        self.load_conferences()
        self.refresh_detail_tabs()

    def refresh_detail_tabs(self):
        self.load_submissions()
        self.load_speakers()
        self.load_schedule()
        self.load_registrations()

    def _need_conference(self):
        event_id = self._current_conf()
        if not event_id:
            self._warn(_t(_k('dialogs', 'create_a_conference_first'),
                          default="Create a conference first."))
        return event_id

    # -- conferences tab ------------------------------------------------------
    def create_conferences_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.upcoming_conferences', default="Upcoming Conferences"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.create_conference', default="➕ Create Conference"),
                  command=self.create_conference).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.edit_details', default="📝 Edit Details"),
                  command=self.edit_conference).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.view_analytics', default="📊 View Analytics"),
                  command=self.conference_analytics).pack(side='left')

        # Conferences list
        columns = ('Conference', 'Date', 'Venue', 'Papers', 'Attendees', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Conference':
                tree.column(col, width=250)

        tree.pack(fill='both', expand=True, pady=(0, 10))
        self.conf_tree = tree

    def load_conferences(self):
        confs = self._run(conf_service.list_conferences) or []
        self._fill(self.conf_tree,
                   [(c['event_id'], (c['title'], _fmt_date(c['start_date']), c['location'] or 'TBA',
                                     c['papers'],
                                     f"{c['registrations']}/{c['max_capacity']}" if c['max_capacity']
                                     else c['registrations'],
                                     _fmt_status(c['status'])))
                    for c in confs],
                   _t(_k('labels', 'no_conferences'),
                      default="No conferences yet — use Create Conference."), 6)

    def _conference_fields(self):
        return [
            ('title', _t(_k('labels', 'name'), default="Name:"), 'entry', None),
            ('start_date', _t(_k('labels', 'start_date'), default="Start date (YYYY-MM-DD):"), 'entry', None),
            ('end_date', _t(_k('labels', 'end_date'), default="End date (YYYY-MM-DD):"), 'entry', None),
            ('start_time', _t(_k('labels', 'start_time'), default="Start time (HH:MM):"), 'entry', None),
            ('location', _t(_k('labels', 'venue'), default="Venue:"), 'entry', None),
            ('capacity', _t(_k('labels', 'capacity'), default="Capacity (0 = unlimited):"), 'spin', (0, 5000)),
            ('status', _t(_k('labels', 'status'), default="Status:"), 'combo', conf_service.CONFERENCE_STATUSES),
            ('description', _t(_k('labels', 'description'), default="Description / call for papers:"), 'text', None),
        ]

    @staticmethod
    def _capacity(value):
        try:
            return int(value or 0)
        except ValueError:
            raise conf_service.ConferenceError("Capacity must be a whole number.")

    def create_conference(self):
        if not self._require_organiser():
            return
        data = self._form(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.create_conference', default="Create Conference"),
                          self._conference_fields(), {'status': 'call_for_papers'})
        if not data:
            return
        try:
            capacity = self._capacity(data['capacity'])
        except conf_service.ConferenceError as e:
            self._warn(str(e))
            return
        event_id = self._run(conf_service.create_conference, title=data['title'],
                             start_date=data['start_date'], end_date=data['end_date'],
                             start_time=data['start_time'], location=data['location'],
                             description=data['description'], capacity=capacity,
                             status=data['status'], organizer_id=self._owner_id(),
                             organizer_name=self._display_name() or self._username())
        if event_id:
            self._info(f"Conference '{data['title']}' created and added to the university calendar.")
            self.refresh_all(event_id)

    def edit_conference(self):
        if not self._require_organiser():
            return
        sel = [s for s in self.conf_tree.selection() if 'empty' not in self.conf_tree.item(s, 'tags')]
        event_id = int(sel[0]) if sel else self._current_conf()
        if not event_id:
            self._warn(_t(_k('dialogs', 'create_a_conference_first'), default="Create a conference first."))
            return
        conf = self._run(conf_service.get_conference, event_id)
        if not conf:
            return
        initial = dict(conf, capacity=conf['max_capacity'] or 0)
        statuses = conf_service.CONFERENCE_STATUSES
        fields = [f if f[0] != 'status' else (f[0], f[1], 'combo', statuses)
                  for f in self._conference_fields()]
        data = self._form(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.edit_conference', default="Edit Conference"),
                          fields, initial)
        if not data:
            return
        try:
            capacity = self._capacity(data['capacity'])
        except conf_service.ConferenceError as e:
            self._warn(str(e))
            return
        if capacity and capacity < conf['registrations']:
            self._warn(f"{conf['registrations']} people are already registered; "
                       "capacity cannot be set below that.")
            return
        done = self._run(lambda c: conf_service.update_conference(
            c, event_id, title=data['title'], start_date=data['start_date'],
            end_date=data['end_date'], start_time=data['start_time'],
            location=data['location'], description=data['description'],
            capacity=capacity, status=data['status']) or True)
        if done:
            self._info(f"'{data['title']}' updated.")
            self.refresh_all(event_id)

    def conference_analytics(self):
        event_id = self._need_conference()
        if not event_id:
            return
        a = self._run(conf_service.analytics, event_id)
        if not a:
            return
        def pct(v):
            return f"{v:.0f}%" if v is not None else "n/a"
        status = ", ".join(f"{_fmt_status(k)}: {v}" for k, v in sorted(a['by_status'].items())) or "none"
        kinds = ", ".join(f"{k}: {v}" for k, v in sorted(a['by_kind'].items())) or "none"
        cap = f"/{a['capacity']}" if a['capacity'] else ""
        rating = f"{a['avg_rating']:.1f}/5" if a['avg_rating'] else "no feedback yet"
        messagebox.showinfo(
            _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.conference_analytics', default="Conference Analytics"),
            f"{a['conference']['title']}\n\n"
            f"• Submissions: {a['submissions']} ({kinds})\n"
            f"• By status: {status}\n"
            f"• Acceptance rate: {pct(a['acceptance_rate'])} of decided submissions\n"
            f"• Registration: {a['registrations']}{cap} ({pct(a['fill_rate'])} full)\n"
            f"• Speakers: {a['speakers']}   Sessions: {a['sessions']}\n"
            f"• Feedback: {a['feedback_responses']} responses, average {rating}\n"
            f"• Awards granted: {a['awards']}",
            parent=self.dialog)

    # -- submissions tab ----------------------------------------------------
    def create_submissions_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.paper_submissions', default="Paper Submissions"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.accept_paper', default="✅ Accept Paper"),
                  command=self.accept_paper).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.reject_paper', default="❌ Reject Paper"),
                  command=self.reject_paper).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.request_revisions', default="📧 Request Revisions"),
                  command=self.request_revisions).pack(side='left')

        columns = ('Title', 'Author', 'Track', 'Submitted', 'Status', 'Reviews')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Title':
                tree.column(col, width=280)

        tree.pack(fill='both', expand=True, pady=(0, 10))
        self.sub_tree = tree

    def load_submissions(self):
        event_id = self._current_conf()
        subs = (self._run(conf_service.list_submissions, event_id=event_id) or []) if event_id else []
        self._fill(self.sub_tree,
                   [(s['submission_id'], (f"{s['title']} ({s['kind']})", s['author_name'] or s['author_id'],
                                          s['track'] or '—', _fmt_date(s['submitted_at']),
                                          _fmt_status(s['status']), s['feedback_count']))
                    for s in subs],
                   _t(_k('labels', 'no_submissions'), default="No submissions for this conference yet."), 6)

    def _decide(self, status, verb, ask_note):
        if not self._require_organiser():
            return
        sub_id = self._selected_id(self.sub_tree, _t(_k('dialogs', 'a_submission'), default="a submission"))
        if sub_id is None:
            return
        sub = self._run(conf_service.get_submission, sub_id)
        if not sub:
            return
        note = ''
        if ask_note:
            note = simpledialog.askstring(verb, f"Comments for the author of '{sub['title']}':",
                                          parent=self.dialog)
            if note is None:
                return
            if status == 'revisions_requested' and not note.strip():
                self._warn(_t(_k('dialogs', 'say_what_to_revise'),
                              default="Tell the author what needs revising."))
                return
        elif not self._ask(f"{verb} '{sub['title']}' by {sub['author_name'] or sub['author_id']}?"):
            return
        updated = self._run(conf_service.decide, sub_id, status, decided_by=self._username(), note=note)
        if not updated:
            return
        email = self._run(conf_service.author_email, updated)
        sent = self._email(email, f"Your submission to {updated['conference']}: {_fmt_status(status)}",
                           f"Your {updated['kind']} '{updated['title']}' submitted to "
                           f"{updated['conference']} has been {_fmt_status(status).lower()}."
                           + (f"\n\nComments from the organisers:\n{note}" if note else ""))
        self._info(f"'{updated['title']}' marked {_fmt_status(status).lower()}."
                   + ("\nThe author has been e-mailed." if sent else
                      "\nThe author has no e-mail address on file — tell them directly."))
        self.load_submissions()
        self.load_conferences()

    def accept_paper(self):
        self._decide('accepted', _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.accept_paper', default="Accept Paper"), False)

    def reject_paper(self):
        self._decide('rejected', _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.reject_paper', default="Reject Paper"), True)

    def request_revisions(self):
        self._decide('revisions_requested', _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.request_revisions', default="Request Revisions"), True)

    # -- speakers tab -----------------------------------------------------------
    def create_speakers_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.conference_speakers', default="Conference Speakers"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.invite_speaker', default="➕ Invite Speaker"),
                  command=self.invite_speaker).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.send_details', default="📧 Send Details"),
                  command=self.send_speaker_details).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(_k('buttons', 'set_speaker_status'), default="✔ Set Status"),
                  command=self.set_speaker_status).pack(side='left')

        columns = ('Name', 'Institution', 'Topic', 'Session', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, pady=(0, 10))
        self.speaker_tree = tree

    def load_speakers(self):
        event_id = self._current_conf()
        rows = (self._run(conf_service.list_speakers, event_id) or []) if event_id else []
        self._fill(self.speaker_tree,
                   [(s['speaker_id'], (s['name'], s['institution'] or '—', s['topic'] or '—',
                                       s['sessions'] or 'Not scheduled', _fmt_status(s['status'])))
                    for s in rows],
                   _t(_k('labels', 'no_speakers'), default="No speakers invited yet."), 5)

    def invite_speaker(self):
        if not self._require_organiser():
            return
        event_id = self._need_conference()
        if not event_id:
            return
        data = self._form(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.invite_speaker', default="Invite Speaker"), [
            ('name', _t(_k('labels', 'speaker_name'), default="Speaker name:"), 'entry', None),
            ('email', _t(_k('labels', 'email'), default="E-mail:"), 'entry', None),
            ('institution', _t(_k('labels', 'institution'), default="Institution:"), 'entry', None),
            ('topic', _t(_k('labels', 'proposed_topic'), default="Proposed topic:"), 'entry', None),
        ])
        if not data:
            return
        sp = self._run(conf_service.invite_speaker, event_id, name=data['name'], email=data['email'],
                       institution=data['institution'], topic=data['topic'],
                       invited_by=self._username())
        if sp is None:
            return
        conf = self._run(conf_service.get_conference, event_id) or {}
        sent = self._email(data['email'], f"Invitation to speak at {conf.get('title', 'our conference')}",
                           f"Dear {data['name']},\n\nThe Student Union would like to invite you to speak"
                           f" at {conf.get('title')} on {_fmt_date(conf.get('start_date'))}"
                           f" ({conf.get('location') or 'venue to be confirmed'})."
                           + (f"\n\nProposed topic: {data['topic']}" if data['topic'] else "")
                           + "\n\nPlease reply to confirm whether you can attend.")
        self._info(f"{data['name']} added as an invited speaker."
                   + ("\nThe invitation has been e-mailed." if sent else
                      "\nNo invitation e-mail was sent (no address given)."))
        self.load_speakers()
        self.load_conferences()

    def send_speaker_details(self):
        event_id = self._need_conference()
        if not event_id:
            return
        speaker_id = self._selected_id(self.speaker_tree, _t(_k('dialogs', 'a_speaker'), default="a speaker"))
        if speaker_id is None:
            return
        speaker = next((s for s in (self._run(conf_service.list_speakers, event_id) or [])
                        if s['speaker_id'] == speaker_id), None)
        if not speaker:
            return
        if not speaker['email']:
            self._warn(f"{speaker['name']} has no e-mail address on record.")
            return
        conf = self._run(conf_service.get_conference, event_id) or {}
        mine = [s for s in (self._run(conf_service.list_sessions, event_id) or [])
                if s['speaker_name'] == speaker['name']]
        slots = "\n".join(f"• {s['starts_at']} — {s['title']} ({s['location'] or 'room TBA'})"
                          for s in mine) or "Your session time has not been scheduled yet."
        if self._email(speaker['email'], f"Speaker details: {conf.get('title')}",
                       f"Dear {speaker['name']},\n\n{conf.get('title')}\n"
                       f"Dates: {_fmt_date(conf.get('start_date'))} – {_fmt_date(conf.get('end_date'))}\n"
                       f"Venue: {conf.get('location') or 'TBA'}\n\nYour sessions:\n{slots}\n"):
            self._info(f"Conference details sent to {speaker['email']}.")
        else:
            self._error(f"The e-mail to {speaker['email']} could not be sent.")

    def set_speaker_status(self):
        if not self._require_organiser():
            return
        speaker_id = self._selected_id(self.speaker_tree, _t(_k('dialogs', 'a_speaker'), default="a speaker"))
        if speaker_id is None:
            return
        status = self._choose(_t(_k('dialogs', 'speaker_status'), default="Speaker Status"),
                              _t(_k('labels', 'status'), default="Status:"),
                              {_fmt_status(s): s for s in conf_service.SPEAKER_STATUSES})
        if status and self._run(lambda c: conf_service.set_speaker_status(c, speaker_id, status) or True):
            self.load_speakers()
            self.load_conferences()

    # -- schedule tab -------------------------------------------------------------
    def create_schedule_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text=_t(_k('buttons', 'add_session'), default="➕ Add Session"),
                   command=self.add_session).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t(_k('buttons', 'place_submission'), default="📌 Place Accepted Work in Session"),
                   command=self.place_submission).pack(side='left')

        self.schedule_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        self.schedule_text.pack(fill='both', expand=True)

    def load_schedule(self):
        event_id = self._current_conf()
        content = (self._run(conf_service.schedule_text, event_id) or '') if event_id else ''
        if not content:
            content = _t(_k('labels', 'no_schedule'),
                         default="No sessions have been scheduled for this conference yet.\n\n"
                                 "Organisers can add keynotes, parallel sessions, poster sessions, "
                                 "workshops, panels and breaks with Add Session.")
        self._set_text(self.schedule_text, content)

    def add_session(self):
        if not self._require_organiser():
            return
        event_id = self._need_conference()
        if not event_id:
            return
        conf = self._run(conf_service.get_conference, event_id) or {}
        speakers = {'(none)': None}
        speakers.update({f"{s['name']} — {s['topic'] or ''}": s['speaker_id']
                         for s in (self._run(conf_service.list_speakers, event_id) or [])
                         if s['status'] != 'declined'})
        data = self._form(_t(_k('dialogs', 'add_session'), default="Add Session"), [
            ('title', _t(_k('labels', 'session_title'), default="Title:"), 'entry', None),
            ('session_type', _t(_k('labels', 'session_type'), default="Type:"), 'combo', conf_service.SESSION_TYPES),
            ('date', _t(_k('labels', 'date'), default="Date (YYYY-MM-DD):"), 'entry', None),
            ('start', _t(_k('labels', 'start_time'), default="Start time (HH:MM):"), 'entry', None),
            ('end', _t(_k('labels', 'end_time'), default="End time (HH:MM):"), 'entry', None),
            ('location', _t(_k('labels', 'room'), default="Room / location:"), 'entry', None),
            ('speaker', _t(_k('labels', 'speaker'), default="Speaker:"), 'combo', list(speakers)),
        ], {'date': conf.get('start_date')})
        if not data:
            return
        sid = self._run(conf_service.add_session, event_id, title=data['title'],
                        session_type=data['session_type'], date=data['date'],
                        start_time=data['start'], end_time=data['end'],
                        location=data['location'], speaker_id=speakers.get(data['speaker']))
        if sid:
            self.load_schedule()
            self.load_speakers()

    def place_submission(self):
        if not self._require_organiser():
            return
        event_id = self._need_conference()
        if not event_id:
            return
        subs = {f"{s['title']} ({s['kind']}, {s['author_name'] or s['author_id']})": s['submission_id']
                for s in (self._run(conf_service.list_submissions, event_id=event_id,
                                    statuses=('accepted',)) or [])}
        sessions = {f"{s['starts_at']} {s['title']}": s['session_id']
                    for s in (self._run(conf_service.list_sessions, event_id) or [])}
        if not subs or not sessions:
            self._warn(_t(_k('dialogs', 'need_accepted_and_session'),
                          default="You need at least one accepted submission and one session."))
            return
        data = self._form(_t(_k('dialogs', 'place_submission'), default="Place in Session"), [
            ('sub', _t(_k('labels', 'submission'), default="Submission:"), 'combo', list(subs)),
            ('sess', _t(_k('labels', 'session'), default="Session:"), 'combo', list(sessions)),
        ])
        if data and self._run(lambda c: conf_service.assign_to_session(
                c, subs[data['sub']], sessions[data['sess']]) or True):
            self.load_schedule()

    # -- registration tab -------------------------------------------------------
    def create_registration_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.attendee_registration', default="Attendee Registration"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.export_list', default="📊 Export List"),
                  command=self.export_registrations).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.send_update', default="📧 Send Update"),
                  command=self.send_registration_update).pack(side='left')

        # Statistics
        stats_frame = ttk.LabelFrame(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.registration_statistics', default="Registration Statistics"))
        stats_frame.pack(fill='x', pady=(0, 15))

        self.reg_stats_label = ttk.Label(stats_frame, text="", justify='left', font=('Courier', 9))
        self.reg_stats_label.pack(padx=15, pady=10, anchor='w')

        # Registration list
        list_frame = ttk.LabelFrame(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.recent_registrations', default="Recent Registrations"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Name', 'Affiliation', 'Type', 'Track', 'Registered')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True)
        self.reg_tree = tree

    def _affiliation(self, user_type):
        return {'student': 'Student', 'staff': 'University staff'}.get(user_type, 'External')

    def load_registrations(self):
        event_id = self._current_conf()
        if not event_id:
            self.reg_stats_label.config(text=_t(_k('labels', 'no_conference_selected'),
                                                default="No conference selected."))
            self._fill(self.reg_tree, [], _t(_k('labels', 'no_registrations'), default="No registrations yet."), 5)
            return
        stats = self._run(conf_service.registration_stats, event_id) or {
            'total': 0, 'capacity': 0, 'by_type': {}, 'by_track': {}}
        regs = self._run(conf_service.registrations, event_id) or []
        total = stats['total']
        cap = f" / {stats['capacity']} capacity" if stats['capacity'] else " (no capacity limit)"
        lines = [f"Total Registrations: {total}{cap}"]
        for t in conf_service.ATTENDEE_TYPES:
            n = stats['by_type'].get(t, 0)
            share = f" ({n / total * 100:.0f}%)" if total else ""
            lines.append(f"{t.title()} Attendees: {n}{share}")
        if stats['by_track']:
            lines.append("\nBy Track (attendees who submitted work):")
            lines += [f"  {k}: {v}" for k, v in sorted(stats['by_track'].items(), key=lambda kv: -kv[1])]
        self.reg_stats_label.config(text="\n".join(lines))
        self._fill(self.reg_tree,
                   [(r['registration_id'], (r['name'], self._affiliation(r['user_type']),
                                            r['user_type'].title(), r['track'] or '—',
                                            _fmt_date(r['registration_date'])))
                    for r in regs],
                   _t(_k('labels', 'no_registrations'), default="No registrations yet."), 5)

    def export_registrations(self):
        event_id = self._need_conference()
        if not event_id:
            return
        regs = self._run(conf_service.registrations, event_id) or []
        if not regs:
            self._warn(_t(_k('dialogs', 'nothing_to_export'), default="There are no registrations to export."))
            return
        conf = self._run(conf_service.get_conference, event_id) or {}
        path = filedialog.asksaveasfilename(
            parent=self.dialog, defaultextension='.csv', filetypes=[('CSV files', '*.csv')],
            initialfile=f"{(conf.get('title') or 'conference').replace(' ', '_')}_registrations.csv")
        if not path:
            return
        import csv
        try:
            with open(path, 'w', newline='', encoding='utf-8') as fh:
                w = csv.writer(fh)
                w.writerow(['Name', 'Account', 'Affiliation', 'Type', 'Track', 'Registered'])
                for r in regs:
                    w.writerow([r['name'], r['user_id'], self._affiliation(r['user_type']),
                                r['user_type'], r['track'] or '', r['registration_date']])
        except OSError as e:
            self._error(f"Could not write the file: {e}")
            return
        self._info(f"{len(regs)} registrations exported to:\n{path}",
                   _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.export', default="Export"))

    def send_registration_update(self):
        if not self._require_organiser():
            return
        event_id = self._need_conference()
        if not event_id:
            return
        contacts = self._run(conf_service.registrant_contacts, event_id) or []
        if not contacts:
            self._warn(_t(_k('dialogs', 'no_registrant_addresses'),
                          default="No registrant has an e-mail address on file."))
            return
        conf = self._run(conf_service.get_conference, event_id) or {}
        data = self._form(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.send_update', default="Send Update"), [
            ('subject', _t(_k('labels', 'subject'), default="Subject:"), 'entry', None),
            ('body', _t(_k('labels', 'message'), default="Message:"), 'text', None),
        ], {'subject': f"Update: {conf.get('title')}"})
        if not data or not data['body']:
            return
        sent = sum(1 for _name, email in contacts if self._email(email, data['subject'], data['body']))
        self._info(f"Update sent to {sent} of {len(contacts)} registrants with an e-mail address.")


class ResearchPresentationDialog(_ConferenceUI):
    """Research presentation and poster session platform"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.conferences.conferences.windows.research_presentation_platform', default="Research Presentation Platform"))
        self.dialog.geometry("1100x800")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.research_presentation_platform', default="🔬 Research Presentation Platform"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Button(main_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        self._current_conf, self._reload_conf = self._conference_picker(main_frame, on_change=self.refresh)

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Presentations tab
        presentations_frame = ttk.Frame(notebook)
        notebook.add(presentations_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.presentations', default="Presentations"))
        self.create_presentations_tab(presentations_frame)

        # Poster Sessions tab
        posters_frame = ttk.Frame(notebook)
        notebook.add(posters_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.poster_sessions', default="Poster Sessions"))
        self.create_posters_tab(posters_frame)

        # Q&A Forum tab
        qa_frame = ttk.Frame(notebook)
        notebook.add(qa_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.q_a_forum', default="Q&A Forum"))
        self.create_qa_tab(qa_frame)

        # Feedback tab
        feedback_frame = ttk.Frame(notebook)
        notebook.add(feedback_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.feedback', default="Feedback"))
        self.create_feedback_tab(feedback_frame)

        # Awards tab
        awards_frame = ttk.Frame(notebook)
        notebook.add(awards_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.tabs.research_awards', default="Research Awards"))
        self.create_awards_tab(awards_frame)

    def refresh(self):
        self.load_presentations()
        self.load_posters()
        self.load_questions()
        self.load_feedback()
        self.load_awards()

    def _need_conference(self):
        event_id = self._current_conf()
        if not event_id:
            self._warn(_t(_k('dialogs', 'no_conferences_yet'),
                          default="There are no conferences yet."))
        return event_id

    def _submission_options(self, event_id, kinds=None, statuses=None, author_id=None):
        return {f"{s['title']} ({s['author_name'] or s['author_id']})": s['submission_id']
                for s in (self._run(conf_service.list_submissions, event_id=event_id, kind=kinds,
                                    statuses=statuses, author_id=author_id) or [])}

    # -- presentations ------------------------------------------------------------
    def create_presentations_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Top buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.submit_presentation', default="➕ Submit Presentation"),
                  command=self.submit_presentation).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.my_presentations', default="📊 My Presentations"),
                  command=self.my_presentations).pack(side='left')

        # Presentations list
        columns = ('Title', 'Presenter', 'Field', 'Date', 'Attendees', 'Rating')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Title':
                tree.column(col, width=280)

        tree.pack(fill='both', expand=True)
        self.pres_tree = tree

    def load_presentations(self):
        event_id = self._current_conf()
        subs = (self._run(conf_service.list_submissions, event_id=event_id,
                          kind='presentation') or []) if event_id else []
        rows = []
        for s in subs:
            when = s['session_starts'] or (_fmt_status(s['status']) if s['status'] != 'accepted'
                                           else 'Not scheduled')
            rating = f"{s['avg_rating']:.1f}/5" if s['avg_rating'] else '—'
            # "Attendees" is the number of people who left feedback (the only
            # attendance the platform records per presentation).
            rows.append((s['submission_id'], (s['title'], s['author_name'] or s['author_id'],
                                              s['track'] or '—', when, s['feedback_count'], rating)))
        self._fill(self.pres_tree, rows,
                   _t(_k('labels', 'no_presentations'), default="No presentations submitted yet."), 6)

    def _submit_kind(self, kind, title):
        event_id = self._need_conference()
        if not event_id:
            return
        owner = self._require_signed_in()
        if not owner:
            return
        data = self._form(title, [
            ('title', _t(_k('labels', 'research_title'), default="Research title:"), 'entry', None),
            ('track', _t(_k('labels', 'field_track'), default="Field / track:"), 'combo', _paper_tracks()),
            ('abstract', _t(_k('labels', 'abstract'), default="Abstract:"), 'text', None),
        ])
        if not data:
            return
        filetypes = ([("PDF files", "*.pdf")] if kind == 'poster' else
                     [("Slides", "*.pdf *.ppt *.pptx"), ("All files", "*.*")])
        path = filedialog.askopenfilename(parent=self.dialog, filetypes=filetypes,
                                          title=_t(_k('dialogs', 'attach_file'),
                                                   default="Attach file (Cancel to skip)"))
        if kind == 'poster' and path and os.path.getsize(path) > 10 * 1024 * 1024:
            self._warn(_t(_k('dialogs', 'poster_too_big'), default="Posters must be 10MB or smaller."))
            return
        sub_id = self._run(conf_service.submit, event_id, kind=kind, title=data['title'],
                           author_id=owner, author_name=self._display_name() or self._username(),
                           abstract=data['abstract'], track=data['track'])
        if sub_id is None:
            return
        if path:
            try:
                self._run(conf_service.attach_file, sub_id,
                          conf_service.store_upload(path, event_id, sub_id))
            except (OSError, conf_service.ConferenceError) as e:
                self._error(f"Submitted, but the file could not be stored: {e}")
        self._info(f"'{data['title']}' submitted. The organisers will review it.")
        self.refresh()

    def submit_presentation(self):
        self._submit_kind('presentation', _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.submit_presentation', default="Submit Presentation"))

    def my_presentations(self):
        owner = self._require_signed_in()
        if not owner:
            return
        mine = self._run(conf_service.list_submissions, author_id=owner) or []
        if not mine:
            text = "You have not submitted anything to a conference yet."
        else:
            text = "\n".join(
                f"• {s['title']} ({s['kind']}) — {s['conference']}\n"
                f"   {_fmt_status(s['status'])}"
                + (f", {s['session_starts']} {s['session_title']}" if s['session_starts'] else "")
                + (f", rated {s['avg_rating']:.1f}/5 ({s['feedback_count']})" if s['avg_rating'] else "")
                + (f"\n   Organiser note: {s['decision_note']}" if s['decision_note'] else "")
                for s in mine)
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.my_presentations', default="My Presentations"),
                            text, parent=self.dialog)

    # -- posters -------------------------------------------------------------------
    def create_posters_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.poster_session_schedule', default="Poster Session Schedule"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.upload_poster', default="📤 Upload Poster"),
                  command=self.upload_poster).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.register_for_session', default="📝 Register for Session"),
                  command=self.register_poster).pack(side='left')

        self.poster_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        self.poster_text.pack(fill='both', expand=True, pady=(0, 10))

    def load_posters(self):
        event_id = self._current_conf()
        if not event_id:
            self._set_text(self.poster_text, "There are no conferences yet.")
            return
        sessions = self._run(conf_service.list_sessions, event_id, session_type='poster') or []
        posters = self._run(conf_service.list_submissions, event_id=event_id, kind='poster') or []
        lines = ["POSTER SESSION SCHEDULE", "=" * 80, ""]
        if not sessions:
            lines.append("No poster sessions have been scheduled yet.")
        for s in sessions:
            end = f" - {s['ends_at'][11:16]}" if s['ends_at'] else ""
            lines += [f"{s['title']}: {s['starts_at']}{end}",
                      f"Location: {s['location'] or 'TBA'}"]
            placed = [p for p in s['submissions'] if p['kind'] == 'poster']
            lines += [f"  P{p['submission_id']:03d}: {p['title']} - {p['author_name'] or ''}"
                      for p in placed] or ["  (no posters registered yet)"]
            lines.append("")
        unplaced = [p for p in posters if not p['session_id']]
        if unplaced:
            lines += ["", "POSTERS NOT YET IN A SESSION:"]
            lines += [f"  P{p['submission_id']:03d}: {p['title']} - {p['author_name'] or p['author_id']}"
                      f" [{_fmt_status(p['status'])}]" for p in unplaced]
        if not posters:
            lines += ["", "No posters have been uploaded for this conference."]
        self._set_text(self.poster_text, "\n".join(lines))

    def upload_poster(self):
        self._submit_kind('poster', _t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.upload_poster', default="Upload Poster"))

    def register_poster(self):
        event_id = self._need_conference()
        if not event_id:
            return
        owner = self._require_signed_in()
        if not owner:
            return
        mine = self._submission_options(event_id, kinds='poster', statuses=('accepted',), author_id=owner)
        sessions = {f"{s['starts_at']} {s['title']} ({s['location'] or 'TBA'})": s['session_id']
                    for s in (self._run(conf_service.list_sessions, event_id, session_type='poster') or [])}
        if not mine:
            self._warn("You have no accepted poster at this conference to register.")
            return
        if not sessions:
            self._warn("No poster sessions have been scheduled yet.")
            return
        data = self._form(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.register', default="Register"), [
            ('poster', _t(_k('labels', 'poster'), default="Poster:"), 'combo', list(mine)),
            ('session', _t(_k('labels', 'session'), default="Session:"), 'combo', list(sessions)),
        ])
        if data and self._run(lambda c: conf_service.assign_to_session(
                c, mine[data['poster']], sessions[data['session']], author_id=owner) or True):
            self._info("Your poster is registered for that session. Please be at your poster "
                       "for the whole session.")
            self.load_posters()

    # -- Q&A -------------------------------------------------------------------------
    def create_qa_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.research_q_a_forum', default="Research Q&A Forum"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.ask_question', default="❓ Ask Question"),
                  command=self.ask_question).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.view_thread', default="💬 View Thread"),
                  command=self.view_qa_thread).pack(side='left')

        columns = ('Question', 'Asker', 'Research Topic', 'Answers', 'Date')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Question':
                tree.column(col, width=300)

        tree.pack(fill='both', expand=True, pady=(0, 10))
        self.qa_tree = tree

    def load_questions(self):
        event_id = self._current_conf()
        qs = (self._run(conf_service.list_questions, event_id) or []) if event_id else []
        self._fill(self.qa_tree,
                   [(q['question_id'], (q['body'], q['asker'], q['topic'], q['answers'],
                                        _fmt_date(q['created_at']))) for q in qs],
                   _t(_k('labels', 'no_questions'), default="No questions asked yet."), 5)

    def ask_question(self):
        event_id = self._need_conference()
        if not event_id:
            return
        owner = self._require_signed_in()
        if not owner:
            return
        subs = self._submission_options(event_id)
        if not subs:
            self._warn("There is no research at this conference to ask about yet.")
            return
        data = self._form(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.ask_question', default="Ask Question"), [
            ('sub', _t(_k('labels', 'presentation'), default="Presentation:"), 'combo', list(subs)),
            ('body', _t(_k('labels', 'question'), default="Question:"), 'text', None),
            ('anon', _t(_k('labels', 'post_anonymously'), default="Post anonymously:"), 'combo', ('No', 'Yes')),
        ])
        if not data:
            return
        if self._run(conf_service.ask, subs[data['sub']], author_id=owner, body=data['body'],
                     author_name=self._display_name() or self._username(),
                     anonymous=data['anon'] == 'Yes'):
            self.load_questions()

    def view_qa_thread(self):
        qid = self._selected_id(self.qa_tree, _t(_k('dialogs', 'a_question'), default="a question"))
        if qid is None:
            return
        result = self._run(conf_service.thread, qid)
        if not result or not result[0]:
            return
        question, answers = result
        win = tk.Toplevel(self.dialog)
        win.title(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.q_a_thread', default="Q&A Thread"))
        win.geometry("650x500")
        win.transient(self.dialog)
        win.grab_set()
        text = scrolledtext.ScrolledText(win, wrap=tk.WORD)
        text.pack(fill='both', expand=True, padx=10, pady=10)
        body = [f"Question ({question['author']}, {question['created_at']}):\n{question['body']}\n"]
        body += [f"Answer {i} ({a['author']}, {a['created_at']}):\n{a['body']}\n"
                 for i, a in enumerate(answers, 1)] or ["No answers yet."]
        text.insert('1.0', "\n".join(body))
        text.config(state='disabled')

        def reply():
            owner = self._require_signed_in()
            if not owner:
                return
            ans = simpledialog.askstring(_t(_k('dialogs', 'reply'), default="Reply"),
                                         _t(_k('labels', 'your_answer'), default="Your answer:"), parent=win)
            if ans and self._run(lambda c: conf_service.ask(
                    c, conf_service_sub(c, qid), author_id=owner, body=ans,
                    author_name=self._display_name() or self._username(), parent_id=qid)):
                win.destroy()
                self.load_questions()

        def conf_service_sub(c, question_id):
            return c.execute("SELECT submission_id FROM su_conference_questions WHERE question_id = ?",
                             (question_id,)).fetchone()[0]

        btns = ttk.Frame(win)
        btns.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Button(btns, text=_t(_k('buttons', 'reply'), default="Reply"), command=reply).pack(side='left')
        ttk.Button(btns, text=_t(_k('buttons', 'close'), default="Close"), command=win.destroy).pack(side='right')

    # -- feedback ----------------------------------------------------------------------
    def create_feedback_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.presentation_feedback_collection', default="Presentation Feedback Collection"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x')

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.submit_feedback', default="📝 Submit Feedback"),
                  command=self.submit_feedback).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.buttons.view_my_feedback', default="📊 View My Feedback"),
                  command=self.view_my_feedback).pack(side='left')

        # Feedback stats
        stats_frame = ttk.LabelFrame(frame, text=_t('gui.pastoral.student_union_gui.conferences.conferences.labels.feedback_statistics', default="Feedback Statistics"))
        stats_frame.pack(fill='x', pady=(0, 15))

        self.feedback_label = ttk.Label(stats_frame, text="", justify='left', font=('Courier', 9))
        self.feedback_label.pack(padx=15, pady=10, anchor='w')

    @staticmethod
    def _stats_text(fb, empty):
        if not fb or not fb['responses']:
            return empty
        def avg(v):
            return f"{v:.1f}/5" if v else "not rated"
        lines = [f"Average Presentation Rating: {avg(fb['avg_rating'])}",
                 f"Total Feedback Responses: {fb['responses']}", ""]
        if fb['top']:
            lines.append("Top Rated Presentations:")
            lines += [f"  {i}. \"{t['title']}\" - {t['avg_rating']:.1f}/5 ({t['responses']} responses)"
                      for i, t in enumerate(fb['top'], 1)]
            lines.append("")
        lines += ["Feedback Categories:",
                  f"  Content Quality: {avg(fb['content'])}",
                  f"  Presentation Skills: {avg(fb['skills'])}",
                  f"  Visual Materials: {avg(fb['visuals'])}",
                  f"  Q&A Engagement: {avg(fb['qa'])}"]
        return "\n".join(lines)

    def load_feedback(self):
        event_id = self._current_conf()
        fb = self._run(conf_service.feedback_stats, event_id=event_id) if event_id else None
        self.feedback_label.config(text=self._stats_text(
            fb, _t(_k('labels', 'no_feedback'), default="No feedback has been submitted for this conference yet.")))

    def submit_feedback(self):
        event_id = self._need_conference()
        if not event_id:
            return
        owner = self._require_signed_in()
        if not owner:
            return
        subs = self._submission_options(event_id, statuses=('accepted',))
        if not subs:
            self._warn("There are no accepted presentations to give feedback on yet.")
            return
        scores = ('5', '4', '3', '2', '1')
        optional = ('', '5', '4', '3', '2', '1')
        data = self._form(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.submit_feedback', default="Submit Feedback"), [
            ('sub', _t(_k('labels', 'presentation'), default="Presentation:"), 'combo', list(subs)),
            ('rating', _t(_k('labels', 'overall_rating'), default="Overall rating (1-5):"), 'combo', scores),
            ('content', _t(_k('labels', 'content_quality'), default="Content quality:"), 'combo', optional),
            ('skills', _t(_k('labels', 'presentation_skills'), default="Presentation skills:"), 'combo', optional),
            ('visuals', _t(_k('labels', 'visual_materials'), default="Visual materials:"), 'combo', optional),
            ('qa', _t(_k('labels', 'qa_engagement'), default="Q&A engagement:"), 'combo', optional),
            ('comments', _t(_k('labels', 'comments_optional'), default="Comments (optional):"), 'text', None),
        ])
        if not data:
            return
        def num(v):
            return int(v) if v else None
        if self._run(lambda c: conf_service.give_feedback(
                c, subs[data['sub']], reviewer_id=owner, rating=int(data['rating']),
                content=num(data['content']), skills=num(data['skills']),
                visuals=num(data['visuals']), qa=num(data['qa']),
                comments=data['comments']) or True):
            self._info("Thank you — your feedback has been recorded.")
            self.load_feedback()
            self.load_presentations()

    def view_my_feedback(self):
        owner = self._require_signed_in()
        if not owner:
            return
        fb = self._run(conf_service.feedback_stats, author_id=owner)
        text = self._stats_text(fb, "Nobody has left feedback on your work yet.")
        if fb and fb['comments']:
            text += "\n\nComments:\n" + "\n".join(
                f"\"{c['comments']}\" ({c['title']}, {c['rating']}/5)" for c in fb['comments'])
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.conferences.conferences.dialogs.my_feedback_received', default="My Feedback Received"),
                            text, parent=self.dialog)

    # -- awards -------------------------------------------------------------------------
    def create_awards_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side='bottom', fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text=_t(_k('buttons', 'grant_award'), default="🏆 Grant Award"),
                   command=self.grant_award).pack(side='left')

        self.awards_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        self.awards_text.pack(fill='both', expand=True)

    def load_awards(self):
        event_id = self._current_conf()
        awards = (self._run(conf_service.list_awards, event_id) or []) if event_id else []
        if not awards:
            self._set_text(self.awards_text, _t(_k('labels', 'no_awards'),
                                                default="No research awards have been granted for this conference yet."))
            return
        lines = [f"RESEARCH AWARDS & RECOGNITION - {awards[0]['conference']}", "=" * 80, ""]
        for a in awards:
            lines += [f"🏆 {a['award_name']}",
                      f"   Winner: \"{a['submission_title']}\" ({a['kind']})",
                      f"   Researcher: {a['author_name'] or '—'}" + (f" ({a['track']})" if a['track'] else ""),
                      f"   Prize: {a['prize'] or '—'}",
                      f"   Awarded: {_fmt_date(a['awarded_at'])}", ""]
        lines.append(f"Number of awards: {len(awards)}")
        self._set_text(self.awards_text, "\n".join(lines))

    def grant_award(self):
        if not self._require_organiser():
            return
        event_id = self._need_conference()
        if not event_id:
            return
        subs = self._submission_options(event_id, statuses=('accepted',))
        if not subs:
            self._warn("Only accepted work can receive an award, and none has been accepted yet.")
            return
        data = self._form(_t(_k('dialogs', 'grant_award'), default="Grant Award"), [
            ('award', _t(_k('labels', 'award_name'), default="Award name:"), 'entry', None),
            ('sub', _t(_k('labels', 'winner'), default="Winning work:"), 'combo', list(subs)),
            ('prize', _t(_k('labels', 'prize'), default="Prize:"), 'entry', None),
        ])
        if data and self._run(conf_service.grant_award, subs[data['sub']], award_name=data['award'],
                              prize=data['prize'], awarded_by=self._username()):
            self.load_awards()


def open_academic_conferences_dialog(self):
    """Open academic conferences dialog"""
    dialog = AcademicConferencesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
