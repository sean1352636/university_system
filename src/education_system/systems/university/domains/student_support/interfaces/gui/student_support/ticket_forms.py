
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

from ._dialogs import make_toplevel, messagebox, filedialog
from . import common as _c
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from education_system.systems.university.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from education_system import paths

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    from education_system.systems.university.infrastructure.email.templates import load_template, render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False
    load_template = lambda *args, **kwargs: None
    render_template = lambda *args, **kwargs: (None, None)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH


# Import all functionality from student_support module (it's a single monolithic file)
try:
    # Import everything from the single student_support module
    from education_system.systems.university.domains.student_support.domain.student_support import (
        # Core constants and enums
        SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
        NotificationType, TicketSentiment, FileType,
        # Main classes
        EnhancedStudentSupport, SupportConfig,
        # Utility functions
        setup_enhanced_logging, audit_action, set_auth,
        # Display functions
        display_support_menu, display_enhanced_faqs, display_enhanced_resources,
        # Ticket management functions
        view_my_tickets_enhanced, view_all_tickets_enhanced,
        create_enhanced_ticket, display_ticket_details_enhanced,
        # Admin functions
        manage_templates_menu, manage_knowledge_base_menu, show_template_statistics,
        # Helper functions
        format_ticket_status_display, format_priority_display, format_file_size,
        truncate_text, handle_support_error, validate_ticket_permissions
    )

    # Auth handling - auth is now managed differently in the new structure
    auth = None  # Will be set via set_auth_instance()

except ImportError:
    # Backwards compatibility - if module structure changes or imports fail
    try:
        from education_system.systems.university.domains.student_support.domain.student_support import (
            SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
            EnhancedStudentSupport, SupportConfig, display_support_menu, set_auth
        )
        auth = None
    except ImportError:
        # If even the fallback import fails, define minimal stubs
        auth = None
        SUPPORT_CATEGORIES = []
        TICKET_PRIORITIES = []
        TICKET_STATUSES = []
        EnhancedStudentSupport = None
        SupportConfig = None
        display_support_menu = None

    # Define fallback functions if not available
    display_enhanced_faqs = None
    display_enhanced_resources = None
    view_my_tickets_enhanced = None
    view_all_tickets_enhanced = None
    create_enhanced_ticket = None
    display_ticket_details_enhanced = None
    manage_templates_menu = None
    manage_knowledge_base_menu = None
    show_template_statistics = None

    # Define fallback enum types
    from enum import Enum
    class NotificationType(str, Enum):
        INFO = 'info'
        WARNING = 'warning'
        ERROR = 'error'

    class TicketSentiment(str, Enum):
        POSITIVE = 'positive'
        NEUTRAL = 'neutral'
        NEGATIVE = 'negative'

    class FileType(str, Enum):
        IMAGE = 'image'
        DOCUMENT = 'document'
        OTHER = 'other'

    # Define fallback helper functions
    setup_enhanced_logging = lambda: None
    audit_action = lambda *args, **kwargs: None
    set_auth = lambda x: None  # Fallback if set_auth not available
    validate_ticket_permissions = lambda *args, **kwargs: True
    format_ticket_status_display = lambda x: str(x)
    format_priority_display = lambda x: str(x)
    format_file_size = lambda x: f"{x} bytes"
    truncate_text = lambda x, length=100: x[:length] if len(x) > length else x
    handle_support_error = lambda *args, **kwargs: None

class TicketFormsMixin:
    # ── raising a ticket ─────────────────────────────────────────────────

    def show_create_ticket(self):
        """The New Ticket screen: anyone raises their own ticket; support
        staff may raise one for a student. Self-help suggestions appear
        beside the form while the person types."""
        self._close_deflection_visit()
        self.clear_content()
        self.set_view('create_ticket')

        create_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(create_frame, text=_t('gui.pastoral.student_support.ticket_forms.tabs.create_ticket', default="🎫 Create Ticket"))

        if not _c.actor(self):
            ttk.Label(create_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.sign_in_to_raise', default="❌ Sign in to raise a ticket"),
                     style='Title.TLabel').pack(pady=20)
            return

        # Action bar first so it stays visible however the window is sized.
        button_frame = ttk.Frame(create_frame, padding=(10, 6))
        button_frame.pack(side="bottom", fill="x")
        ttk.Button(button_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.create_ticket', default="🎫 Create Ticket"),
                  command=self.create_ticket, style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.reset_form', default="🔄 Reset Form"),
                  command=self.reset_create_form).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.cancel', default="❌ Cancel"),
                  command=self.show_dashboard).pack(side="left")

        # Known issues first: "I'm affected" joins the incident instead of a new report.
        from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk import (
            support_tools,
        )
        known = support_tools.known_issues_frame(create_frame, self.auth,
                                                 on_reported=lambda _tid: self.show_my_tickets())
        if known is not None:
            known.pack(side="top", fill="x", padx=10, pady=(6, 0))

        body = ttk.Frame(create_frame)
        body.pack(fill="both", expand=True)

        # Self-help suggestions (right); the form scrolls on the left.
        suggest_frame = ttk.LabelFrame(body, text=_t('gui.pastoral.student_support.ticket_forms.labels.suggestions', default="💡 These may answer your question"), padding="8", width=360)
        suggest_frame.pack(side="right", fill="y", padx=(6, 0))
        suggest_frame.pack_propagate(False)
        self.suggestions_hint = ttk.Label(suggest_frame, wraplength=330, foreground=self.colors['text_secondary'],
                                          text=_t('gui.pastoral.student_support.ticket_forms.labels.suggestions_hint', default="Start describing your question and related help articles will appear here."))
        self.suggestions_hint.pack(anchor="w", pady=(0, 6))
        self.suggestions_list = ttk.Frame(suggest_frame)
        self.suggestions_list.pack(fill="both", expand=True)
        ttk.Button(suggest_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.answered', default="✅ This answered my question"),
                  command=self._deflection_answered).pack(side="bottom", fill="x", pady=(6, 0))

        canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        form_frame = ttk.Frame(canvas, padding="15")
        canvas_window = canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _wheel(event):
            if getattr(event, 'num', None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, 'num', None) == 5:
                canvas.yview_scroll(1, "units")
            elif event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_scroll_recursive(widget):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                widget.bind(seq, _wheel, add="+")
            for child in widget.winfo_children():
                bind_scroll_recursive(child)

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.create_support_ticket', default="🎫 Create Support Ticket"),
                 style='Title.TLabel').pack(pady=(0, 15), anchor="w")

        # Who the ticket is for (support staff may raise one for a student).
        self.requester_var = tk.StringVar()
        if _c.is_support_staff(self):
            for_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.raise_for', default="👤 Raise this ticket for"), padding="10")
            for_frame.pack(fill="x", pady=(0, 10))
            self.raise_for_var = tk.StringVar(value='self')
            ttk.Radiobutton(for_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.myself', default="Myself"),
                           variable=self.raise_for_var, value='self').grid(row=0, column=0, sticky="w")
            ttk.Radiobutton(for_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.a_student', default="A student (student number or username):"),
                           variable=self.raise_for_var, value='student').grid(row=0, column=1, sticky="w", padx=(15, 5))
            ttk.Entry(for_frame, textvariable=self.requester_var, width=24).grid(row=0, column=2, sticky="w")
            ttk.Button(for_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.find_student', default="🔍 Find…"),
                      command=self._pick_requester).grid(row=0, column=3, padx=(5, 0))
        else:
            self.raise_for_var = tk.StringVar(value='self')

        # Template selection
        template_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.templates_optional', default="📋 Templates (Optional)"), padding="10")
        template_frame.pack(fill="x", pady=(0, 10))

        self.selected_template = tk.StringVar()
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.selected_template,
                                          state="readonly", width=50)
        try:
            templates = self.support.get_ticket_templates() if self.support else []
        except Exception:
            logger.warning("Ticket templates unavailable", exc_info=True)
            templates = []
        self.template_data = {"Create from scratch": None}
        for t in templates:
            self.template_data[f"{t['name']} ({t['category']})"] = t
        self.template_combo['values'] = list(self.template_data)
        self.template_combo.set("Create from scratch")
        self.template_combo.pack(fill="x")
        self.template_combo.bind('<<ComboboxSelected>>', self.on_template_selected)

        # Title field
        title_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.title', default="📝 Title *"), padding="10")
        title_frame.pack(fill="x", pady=(0, 10))
        self.title_entry = ttk.Entry(title_frame, width=80, font=('Segoe UI', 10))
        self.title_entry.pack(fill="x")
        self.title_entry.bind('<KeyRelease>', lambda e: self._schedule_suggestions())

        # Category field: the UK categories, each routed to a team.
        category_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.category_variant_2', default="📂 Category *"), padding="10")
        category_frame.pack(fill="x", pady=(0, 10))
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(category_frame, textvariable=self.category_var,
                                          values=_c.categories(), state="readonly")
        self.category_combo.set("General")
        self.category_combo.pack(fill="x")
        self.category_team_label = ttk.Label(category_frame, foreground=self.colors['text_secondary'])
        self.category_team_label.pack(anchor="w", pady=(4, 0))
        self.confidential_hint = tk.Label(category_frame, text="🔒 " + _c.SENSITIVE_HINT, bg="#fef3c7",
                                          fg="#92400e", wraplength=700, justify="left", anchor="w",
                                          padx=8, pady=4)
        self.category_combo.bind('<<ComboboxSelected>>', lambda e: self._on_category_changed())

        # Priority field
        priority_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.priority_variant_2', default="🔥 Priority"), padding="10")
        priority_frame.pack(fill="x", pady=(0, 10))
        self.priority_var = tk.StringVar()
        self.priority_combo = ttk.Combobox(priority_frame, textvariable=self.priority_var,
                                          values=_c.priorities(), state="readonly")
        self.priority_combo.set("Medium")
        self.priority_combo.pack(fill="x")

        # Description field
        desc_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.description', default="📄 Description *"), padding="10")
        desc_frame.pack(fill="x", pady=(0, 10))
        self.description_text = scrolledtext.ScrolledText(desc_frame, height=10, wrap=tk.WORD, font=('Segoe UI', 10))
        self.description_text.pack(fill="x")
        self.description_text.bind('<KeyRelease>', lambda e: self._schedule_suggestions())

        # Extra confidentiality on request (the category may already give it).
        self.confidential_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, variable=self.confidential_var,
                        text=_t('gui.pastoral.student_support.ticket_forms.buttons.keep_confidential', default="🔒 Keep this confidential to the specialist team")).pack(anchor="w", pady=(0, 10))

        # Tags field
        tags_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.tags_comma_separated', default="🏷️ Tags (comma-separated)"), padding="10")
        tags_frame.pack(fill="x", pady=(0, 10))
        self.tags_entry = ttk.Entry(tags_frame, width=80, font=('Segoe UI', 10))
        self.tags_entry.pack(fill="x")

        # Attachments
        attachments_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.attachments', default="📎 Attachments"), padding="10")
        attachments_frame.pack(fill="x", pady=(0, 10))
        self.attachments = []
        self.attachments_listbox = tk.Listbox(attachments_frame, height=3)
        self.attachments_listbox.pack(fill="x", pady=(0, 5))
        attach_btn_frame = ttk.Frame(attachments_frame)
        attach_btn_frame.pack(fill="x")
        ttk.Button(attach_btn_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.add_file', default="➕ Add File"),
                  command=self.add_attachment).pack(side="left", padx=(0, 5))
        ttk.Button(attach_btn_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.remove', default="➖ Remove"),
                  command=self.remove_attachment).pack(side="left")

        self._deflection_visit = None
        self._deflection_shown = []
        self._suggest_job = None
        self._on_category_changed()
        form_frame.after(100, lambda: bind_scroll_recursive(form_frame))

    def _on_category_changed(self):
        category = self.category_var.get()
        team = _c.ss('routing').team_for_category(category) or 'general'
        self.category_team_label.config(text=_t('gui.pastoral.student_support.ticket_forms.labels.goes_to', default="Goes to: {team}").format(team=_c.team_label(team)))
        if _c.is_sensitive_category(category):
            self.confidential_hint.pack(fill="x", pady=(6, 0))
        else:
            self.confidential_hint.pack_forget()

    def _pick_requester(self):
        """Find a student by name, username or student number."""
        win = _c.dialog(self, _t('gui.pastoral.student_support.ticket_forms.windows.find_student', default="Find a student"), 700, 480)
        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")
        query = tk.StringVar(value=self.requester_var.get())
        entry = ttk.Entry(top, textvariable=query, width=40)
        entry.pack(side="left", fill="x", expand=True)
        buttons = ttk.Frame(win, padding=8)
        buttons.pack(side="bottom", fill="x")
        tree = _c.tree_with_scroll(win, ('student_id', 'username', 'name'),
                                   {'student_id': 'Student number', 'username': 'Username', 'name': 'Name'},
                                   {'student_id': 140, 'username': 160, 'name': 300}, height=12)

        def search(_e=None):
            tree.delete(*tree.get_children())
            text = query.get().strip()
            if len(text) < 2:
                return
            like = f"%{text}%"
            with _c.ss('store').reading() as conn:
                rows = conn.execute(
                    "SELECT username, student_id, TRIM(COALESCE(first_name, '') || ' ' || "
                    "COALESCE(last_name, '')) FROM users WHERE lower(role) = 'student' AND "
                    "(username LIKE ? OR student_id LIKE ? OR first_name || ' ' || last_name LIKE ?) "
                    "ORDER BY last_name, first_name LIMIT 100", (like, like, like)).fetchall()
            for username, student_id, name in rows:
                tree.insert('', 'end', values=(student_id or '', username, name))

        def choose(_e=None):
            sel = tree.selection()
            if not sel:
                return
            student_id, username, _name = tree.item(sel[0], 'values')
            self.requester_var.set(student_id or username)
            self.raise_for_var.set('student')
            win.destroy()

        ttk.Button(top, text=_t('gui.pastoral.student_support.ticket_forms.buttons.search', default="Search"), command=search).pack(side="left", padx=5)
        ttk.Button(buttons, text=_t('gui.pastoral.student_support.ticket_forms.buttons.choose', default="Choose"), command=choose).pack(side="left")
        ttk.Button(buttons, text=_t('gui.pastoral.student_support.ticket_forms.buttons.cancel', default="Cancel"), command=win.destroy).pack(side="left", padx=5)
        entry.bind('<Return>', search)
        tree.bind('<Double-1>', choose)
        entry.focus_set()
        search()

    # ── self-help suggestions (deflection) ───────────────────────────────

    def _schedule_suggestions(self):
        if getattr(self, '_suggest_job', None):
            try:
                self.root.after_cancel(self._suggest_job)
            except tk.TclError:
                pass
        self._suggest_job = self.root.after(600, self._update_suggestions)

    def _update_suggestions(self):
        self._suggest_job = None
        try:
            text = f"{self.title_entry.get()} {self.description_text.get(1.0, tk.END)}".strip()
        except tk.TclError:
            return  # the form has gone
        defl = _c.ss('deflection')
        try:
            found = defl.suggest(text, limit=5) if len(text) >= 8 else []
        except Exception:
            logger.warning("Self-help suggestions unavailable", exc_info=True)
            found = []
        for child in self.suggestions_list.winfo_children():
            child.destroy()
        if not found:
            return
        keys = [f['key'] for f in found]
        if self._deflection_visit is None:
            self._deflection_visit = _c.run(self.root, defl.start, _c.actor(self), text, found)
        self._deflection_shown = keys
        for item in found:
            box = ttk.Frame(self.suggestions_list, padding=(0, 4))
            box.pack(fill="x")
            ttk.Label(box, text=item['title'], font=('Segoe UI', 10, 'bold'), wraplength=330).pack(anchor="w")
            if item.get('snippet'):
                ttk.Label(box, text=item['snippet'][:160], wraplength=330,
                          foreground=self.colors['text_secondary']).pack(anchor="w")
            ttk.Button(box, text=_t('gui.pastoral.student_support.ticket_forms.buttons.read', default="📖 Read"),
                       command=lambda s=item: self._open_suggestion(s)).pack(anchor="w", pady=(2, 0))

    def _open_suggestion(self, item):
        """Show a suggested article and record that it was read."""
        defl = _c.ss('deflection')
        if self._deflection_visit:
            _c.run(self.root, defl.viewed, _c.actor(self), self._deflection_visit, item['key'])
        # The source table and its title/body columns, as the suggester uses them.
        table, key, title_col, _summary, body_col = defl._SOURCES[item['source']][:5]
        with _c.ss('store').reading() as conn:
            row = conn.execute(f"SELECT {title_col}, {body_col} FROM {table} "  # nosec B608 - names from deflection._SOURCES
                               f"WHERE {key} = ?", (item['id'],)).fetchone()
        title, body = (row[0], row[1]) if row else (item['title'], item.get('snippet') or '')
        win = _c.dialog(self, str(title or item['title']), 900, 650)
        ttk.Button(win, text=_t('gui.pastoral.student_support.ticket_forms.buttons.close', default="Close"),
                   command=win.destroy).pack(side="bottom", pady=8)
        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=('Segoe UI', 10))
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert(1.0, f"{title}\n\n{body or ''}")
        text.config(state='disabled')

    def _close_deflection_visit(self, ticket_id=None):
        """Finish the open suggestion visit (submitted / deflected / abandoned)."""
        visit = getattr(self, '_deflection_visit', None)
        self._deflection_visit = None
        if not visit:
            return None
        try:
            return _c.ss('deflection').finish(_c.actor(self), visit, ticket_id)
        except Exception:
            logger.warning("Could not close suggestion visit %s", visit, exc_info=True)
            return None

    def _deflection_answered(self):
        outcome = self._close_deflection_visit()
        messagebox.showinfo(_t('gui.pastoral.student_support.ticket_forms.dialogs.glad', default="Glad that helped"),
                            _t('gui.pastoral.student_support.ticket_forms.dialogs.no_ticket_needed', default="No ticket has been raised. You can come back here any time."))
        logger.debug("Suggestion visit closed: %s", outcome)
        self.show_dashboard()

    def on_template_selected(self, event=None):
        """Handle template selection"""
        template_name = self.selected_template.get()
        template = self.template_data.get(template_name)

        if template:
            # Fill form with template data
            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, template['subject_template'])

            category = template['category']
            self.category_var.set(_c.category_label(category) if _c.ss('routing').uk_category(category) else category)
            self.priority_var.set(template['priority'])

            self.description_text.delete(1.0, tk.END)
            self.description_text.insert(1.0, template['message_template'])
            self._on_category_changed()
            self._schedule_suggestions()

    def add_attachment(self):
        """Add file attachment"""
        file_path = filedialog.askopenfilename(
            title=_t('gui.pastoral.student_support.ticket_forms.dialogs.select_file_to_attach', default="Select File to Attach"),
            filetypes=[("All Files", "*.*")]
        )

        if file_path:
            # Check file size (10MB limit)
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_forms.dialogs.file_too_large', default="File Too Large"), _t('gui.pastoral.student_support.ticket_forms.dialogs.file_size_must_be_less_than_10mb', default="File size must be less than 10MB"))
                return

            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                import mimetypes
                attachment = {
                    'filename': os.path.basename(file_path),
                    'data': file_data,
                    'mime_type': mimetypes.guess_type(file_path)[0] or 'application/octet-stream',
                }
                self.attachments.append(attachment)
                self.attachments_listbox.insert(tk.END, attachment['filename'])
            except OSError as e:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_forms.dialogs.file_error', default="File Error"), f"Could not read file: {e}")

    def remove_attachment(self):
        """Remove selected attachment"""
        selection = self.attachments_listbox.curselection()
        if selection:
            index = selection[0]
            self.attachments.pop(index)
            self.attachments_listbox.delete(index)

    def create_ticket(self):
        """Raise the ticket through the service; show the crisis contacts at
        once when the service says the text used crisis language."""
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_forms.dialogs.validation_error', default="Validation Error"), _t('gui.pastoral.student_support.ticket_forms.dialogs.title_is_required', default="Title is required"))
            return
        description = self.description_text.get(1.0, tk.END).strip()
        if not description:
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_forms.dialogs.validation_error', default="Validation Error"), _t('gui.pastoral.student_support.ticket_forms.dialogs.description_is_required', default="Description is required"))
            return

        tags_text = self.tags_entry.get().strip()
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()] if tags_text else []
        requester = None
        if self.raise_for_var.get() == 'student':
            requester = self.requester_var.get().strip()
            if not requester:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_forms.dialogs.validation_error', default="Validation Error"),
                                     _t('gui.pastoral.student_support.ticket_forms.dialogs.say_which_student', default="Say which student the ticket is for"))
                return
        template = self.template_data.get(self.selected_template.get())

        self.update_status(_t('gui.pastoral.student_support.ticket_forms.status.creating', default="Creating ticket..."))
        result = _c.run(self.root, _c.ss('service').submit_ticket, _c.actor(self),
                        subject=title, description=description, category=self.category_var.get(),
                        priority=self.priority_var.get() or 'Medium', requester=requester,
                        attachments=list(self.attachments), tags=tags,
                        template_id=template['template_id'] if template else None,
                        confidentiality='restricted' if self.confidential_var.get() else None)
        if not result:
            self.update_status(_t('gui.pastoral.student_support.ticket_forms.status.failed', default="Ticket creation failed"))
            return
        ticket_id = result['ticket_id']
        self._close_deflection_visit(ticket_id)
        if result.get('crisis'):
            _c.show_crisis(self, result['crisis'])
        else:
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_forms.dialogs.success', default="Success"),
                                _t('gui.pastoral.student_support.ticket_forms.dialogs.created', default="Support ticket #{ticket_id} created and sent to {team}.").format(
                                    ticket_id=ticket_id, team=_c.team_label(result.get('team'))))
        self.update_status(f"Ticket #{ticket_id} created")
        self.reset_create_form()
        self.view_ticket_details(ticket_id)

    def reset_create_form(self):
        """Reset the create ticket form"""
        self._close_deflection_visit()
        self.title_entry.delete(0, tk.END)
        self.description_text.delete(1.0, tk.END)
        self.tags_entry.delete(0, tk.END)
        self.category_var.set("General")
        self.priority_var.set("Medium")
        self.selected_template.set("Create from scratch")
        self.confidential_var.set(False)
        self.requester_var.set('')
        self.raise_for_var.set('self')
        self.attachments.clear()
        self.attachments_listbox.delete(0, tk.END)
        for child in self.suggestions_list.winfo_children():
            child.destroy()
        self._on_category_changed()

    # ── lists ────────────────────────────────────────────────────────────

    _LIST_COLUMNS = ('ID', 'Title', 'Status', 'Priority', 'Category', 'Team', 'Tier', 'Created', 'Updated')

    def _status_filter_values(self):
        return ["All"] + [label for label, _value in _c.status_choices()]

    def show_my_tickets(self):
        """The tickets the signed-in person raised (anyone)."""
        self.clear_content()
        self.set_view('my_tickets')

        tickets_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.tabs.my_tickets', default="📋 My Tickets"))

        if not _c.actor(self):
            ttk.Label(tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.access_denied', default="❌ Access denied"),
                     style='Title.TLabel').pack(pady=20)
            return

        header_frame = ttk.Frame(tickets_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(header_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.my_support_tickets', default="📋 My Support Tickets"),
                 style='Title.TLabel').pack(side="left")
        ttk.Button(header_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.export_csv', default="⬇️ Export CSV"),
                  command=lambda: self._export_list('my_tickets_tree', 'my_tickets.csv')).pack(side="right", padx=(5, 0))
        ttk.Button(header_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.refresh', default="🔄 Refresh"),
                  command=self.refresh_my_tickets).pack(side="right")

        filter_frame = ttk.LabelFrame(tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.filters', default="🔍 Filters"), padding="10")
        filter_frame.pack(fill="x", pady=(0, 10))
        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill="x")

        ttk.Label(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.labels.status', default="Status:")).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.my_tickets_status_filter = ttk.Combobox(filter_grid, values=self._status_filter_values(), state="readonly", width=20)
        self.my_tickets_status_filter.set("All")
        self.my_tickets_status_filter.grid(row=0, column=1, padx=(0, 10))
        self.my_tickets_status_filter.bind('<<ComboboxSelected>>', lambda e: self.refresh_my_tickets())

        ttk.Label(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.labels.search', default="Search:")).grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.my_tickets_search = ttk.Entry(filter_grid, width=30)
        self.my_tickets_search.grid(row=0, column=3, padx=(0, 10))
        self.my_tickets_search.bind('<Return>', lambda e: self.refresh_my_tickets())

        ttk.Button(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.buttons.apply', default="Apply"),
                  command=self.refresh_my_tickets).grid(row=0, column=4)

        self.my_tickets_frame = ttk.Frame(tickets_frame)
        self.my_tickets_frame.pack(fill="both", expand=True)
        self.refresh_my_tickets()

    def _filters_from(self, status_widget, search_widget):
        filters = {}
        status = _c.status_value(status_widget.get())
        if status:
            filters['status'] = status
        search = search_widget.get().strip()
        if search:
            filters['search'] = search
        return filters

    def _ticket_row_values(self, ticket):
        title = str(ticket.get('subject') or '')
        return (
            ticket.get('ticket_id'),
            title[:60] + ('…' if len(title) > 60 else ''),
            ticket.get('status_label') or _c.status_label(ticket.get('status')),
            ticket.get('priority') or '',
            _c.category_label(ticket.get('category')),
            _c.team_label(ticket.get('team')),
            _c.tier_label(_c.tier_of(ticket)),
            str(ticket.get('created_at') or '')[:16],
            str(ticket.get('updated_at') or '')[:16],
        )

    def refresh_my_tickets(self):
        """Reload My Tickets with the chosen status and search."""
        for widget in self.my_tickets_frame.winfo_children():
            widget.destroy()
        filters = self._filters_from(self.my_tickets_status_filter, self.my_tickets_search)
        result = _c.run(self.root, _c.ss('service').list_my_tickets, _c.actor(self), filters,
                        page=1, per_page=200)
        tickets = (result or {}).get('tickets') or []
        if not tickets:
            ttk.Label(self.my_tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.no_tickets_found', default="📭 No tickets found")).pack(pady=20)
            self.my_tickets_tree = None
            return
        tree = _c.tree_with_scroll(self.my_tickets_frame, self._LIST_COLUMNS,
                                   widths={'ID': 60, 'Title': 300, 'Status': 130, 'Priority': 80,
                                           'Category': 170, 'Team': 150, 'Tier': 100,
                                           'Created': 130, 'Updated': 130}, height=20)
        for ticket in tickets:
            tree.insert('', 'end', values=self._ticket_row_values(ticket))
        tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))
        tree.bind('<Return>', lambda e: self.on_ticket_double_click(tree))
        tree.bind('<Button-3>', lambda e: self.show_ticket_context_menu(e, tree))
        self.my_tickets_tree = tree
        total = (result or {}).get('total_count', len(tickets))
        self.update_status(f"Loaded {len(tickets)} of {total} tickets")

    def show_all_tickets(self):
        """Every ticket the signed-in case worker may work (team and tier)."""
        self.clear_content()
        self.set_view('all_tickets')

        tickets_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.tabs.all_tickets', default="🎫 All Tickets"))

        if not self.is_staff():
            ttk.Label(tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.staff_access_required', default="❌ Staff access required"),
                     style='Title.TLabel').pack(pady=20)
            return

        header_frame = ttk.Frame(tickets_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(header_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.all_support_tickets', default="🎫 All Support Tickets"),
                 style='Title.TLabel').pack(side="left")
        control_frame = ttk.Frame(header_frame)
        control_frame.pack(side="right")
        ttk.Button(control_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.refresh', default="🔄 Refresh"),
                  command=self.refresh_all_tickets).pack(side="left", padx=(0, 5))
        ttk.Button(control_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.export_csv', default="⬇️ Export CSV"),
                  command=lambda: self._export_list('all_tickets_tree', 'tickets.csv')).pack(side="left", padx=(0, 5))
        if _c.is_support_staff(self):
            ttk.Button(control_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.reports', default="📊 Reports"),
                      command=self.show_reports).pack(side="left", padx=(0, 5))
            ttk.Button(control_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.bulk_ops', default="📦 Bulk Ops"),
                      command=self.show_bulk_operations).pack(side="left")

        filter_frame = ttk.LabelFrame(tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.advanced_filters', default="🔍 Advanced Filters"), padding="10")
        filter_frame.pack(fill="x", pady=(0, 10))
        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill="x")

        ttk.Label(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.labels.status', default="Status:")).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.all_tickets_status = ttk.Combobox(filter_grid, values=self._status_filter_values(), state="readonly", width=18)
        self.all_tickets_status.set("All")
        self.all_tickets_status.grid(row=0, column=1, padx=(0, 10))

        ttk.Label(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.labels.priority', default="Priority:")).grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.all_tickets_priority = ttk.Combobox(filter_grid, values=["All"] + _c.priorities(), state="readonly", width=12)
        self.all_tickets_priority.set("All")
        self.all_tickets_priority.grid(row=0, column=3, padx=(0, 10))

        ttk.Label(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.labels.category', default="Category:")).grid(row=0, column=4, sticky="w", padx=(0, 5))
        self.all_tickets_category = ttk.Combobox(filter_grid, values=["All"] + _c.categories(), state="readonly", width=24)
        self.all_tickets_category.set("All")
        self.all_tickets_category.grid(row=0, column=5, padx=(0, 10))

        ttk.Label(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.labels.team', default="Team:")).grid(row=0, column=6, sticky="w", padx=(0, 5))
        self._team_choices = {t['label']: t['key'] for t in _c.ss('routing').teams()}
        self.all_tickets_team = ttk.Combobox(filter_grid, values=["All"] + list(self._team_choices), state="readonly", width=22)
        self.all_tickets_team.set("All")
        self.all_tickets_team.grid(row=0, column=7, padx=(0, 10))

        ttk.Label(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.labels.assigned_to', default="Assigned to:")).grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.all_tickets_assigned = ttk.Entry(filter_grid, width=18)
        self.all_tickets_assigned.grid(row=1, column=1, padx=(0, 10), pady=(5, 0))

        ttk.Label(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.labels.search', default="Search:")).grid(row=1, column=2, sticky="w", padx=(0, 5), pady=(5, 0))
        self.all_tickets_search = ttk.Entry(filter_grid, width=20)
        self.all_tickets_search.grid(row=1, column=3, columnspan=3, sticky="ew", padx=(0, 10), pady=(5, 0))
        self.all_tickets_search.bind('<Return>', lambda e: self.refresh_all_tickets())

        ttk.Button(filter_grid, text=_t('gui.pastoral.student_support.ticket_forms.buttons.apply_filters', default="Apply Filters"),
                  command=self.refresh_all_tickets).grid(row=1, column=7, pady=(5, 0), sticky="w")

        quick_frame = ttk.Frame(filter_frame)
        quick_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(quick_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.high_priority', default="🔥 High Priority"),
                  command=lambda: self.apply_quick_filter('priority', 'High')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.unassigned', default="❌ Unassigned"),
                  command=lambda: self.apply_quick_filter('assigned', 'none')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.escalated', default="🚨 Escalated"),
                  command=lambda: self.apply_quick_filter('status', 'Escalated')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text=_t('gui.pastoral.student_support.ticket_forms.buttons.clear_filters', default="🔄 Clear Filters"),
                  command=self.clear_all_filters).pack(side="left", padx=(0, 5))

        # Bulk bar for the rows selected in the list (Ctrl/Shift-click).
        if _c.is_support_staff(self):
            bulk = ttk.LabelFrame(tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.selected_tickets', default="📦 Selected tickets (Ctrl/Shift-click to pick several)"), padding="8")
            bulk.pack(side="bottom", fill="x", pady=(8, 0))
            self.bulk_field_var = tk.StringVar(value='Status')
            self.bulk_value_combo = ttk.Combobox(bulk, state="readonly", width=24)
            field = ttk.Combobox(bulk, textvariable=self.bulk_field_var, state="readonly", width=12,
                                 values=['Status', 'Priority', 'Category', 'Assign to'])
            field.pack(side="left")
            field.bind('<<ComboboxSelected>>', lambda e: self._bulk_field_changed())
            self.bulk_value_combo.pack(side="left", padx=5)
            ttk.Button(bulk, text=_t('gui.pastoral.student_support.ticket_forms.buttons.apply_to_selected', default="Apply to selected"),
                       command=self.apply_bulk_to_selected).pack(side="left", padx=5)
            self.bulk_count_label = ttk.Label(bulk, text="")
            self.bulk_count_label.pack(side="left", padx=10)
            self._bulk_field_changed()

        self.all_tickets_frame = ttk.Frame(tickets_frame)
        self.all_tickets_frame.pack(fill="both", expand=True)
        self.refresh_all_tickets()

    def _bulk_field_changed(self):
        field = self.bulk_field_var.get()
        if field == 'Status':
            values = [label for label, _v in _c.status_choices()]
        elif field == 'Priority':
            values = _c.priorities()
        elif field == 'Category':
            values = _c.categories()
        else:
            with _c.ss('store').reading() as conn:
                rows = _c.ss('routing').capacity(conn)
            values = ['(unassign)'] + sorted({r['username'] for r in rows})
        self.bulk_value_combo['values'] = values
        self.bulk_value_combo.set(values[0] if values else '')

    def apply_bulk_to_selected(self):
        """service.bulk_update on the rows selected in All Tickets."""
        tree = getattr(self, 'all_tickets_tree', None)
        ids = [int(tree.item(i, 'values')[0]) for i in tree.selection()] if tree else []
        if not ids:
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_forms.dialogs.bulk', default="Bulk update"),
                                _t('gui.pastoral.student_support.ticket_forms.dialogs.select_rows', default="Select one or more tickets in the list first."))
            return
        field, value = self.bulk_field_var.get(), self.bulk_value_combo.get()
        self.perform_bulk_update(ids, field, value)
        self.refresh_all_tickets()

    def perform_bulk_update(self, ticket_ids, field, value):
        """One bulk change through ``service.bulk_update`` (confirmed first)."""
        key = {'Status': 'status', 'Priority': 'priority', 'Category': 'category',
               'Assign to': 'assigned_to'}[field]
        if key == 'status':
            value = _c.status_value(value)
        if key == 'assigned_to' and value in ('', '(unassign)'):
            value = None
        if key != 'assigned_to' and not value:
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_forms.dialogs.bulk', default="Bulk update"),
                                 _t('gui.pastoral.student_support.ticket_forms.dialogs.choose_value', default="Choose the new value first."))
            return None
        shown = _c.status_label(value) if key == 'status' else (value or 'nobody')
        if not messagebox.askyesno(_t('gui.pastoral.student_support.ticket_forms.dialogs.bulk', default="Bulk update"),
                                   _t('gui.pastoral.student_support.ticket_forms.dialogs.confirm_bulk', default="Set {field} to {value} on {count} ticket(s)?").format(
                                       field=field.lower(), value=shown, count=len(ticket_ids))):
            return None
        done = _c.run(self.root, _c.ss('service').bulk_update, _c.actor(self), ticket_ids, {key: value})
        if done is not None:
            skipped = len(ticket_ids) - done
            msg = _t('gui.pastoral.student_support.ticket_forms.dialogs.bulk_done', default="{done} ticket(s) updated.").format(done=done)
            if skipped:
                msg += " " + _t('gui.pastoral.student_support.ticket_forms.dialogs.bulk_skipped', default="{skipped} could not be changed (see the log for why).").format(skipped=skipped)
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_forms.dialogs.bulk', default="Bulk update"), msg)
        return done

    def apply_quick_filter(self, filter_type, value):
        """Apply quick filter"""
        if filter_type == 'priority':
            self.all_tickets_priority.set(value)
        elif filter_type == 'status':
            self.all_tickets_status.set(_c.status_label(value))
        elif filter_type == 'assigned':
            if value == 'none':
                self.all_tickets_assigned.delete(0, tk.END)
                self.all_tickets_assigned.insert(0, 'UNASSIGNED')
        self.refresh_all_tickets()

    def clear_all_filters(self):
        """Clear all filters"""
        self.all_tickets_status.set("All")
        self.all_tickets_priority.set("All")
        self.all_tickets_category.set("All")
        self.all_tickets_team.set("All")
        self.all_tickets_assigned.delete(0, tk.END)
        self.all_tickets_search.delete(0, tk.END)
        self.refresh_all_tickets()

    def refresh_all_tickets(self):
        """Reload All Tickets through ``service.list_tickets`` (scoped to
        the tickets this case worker may see)."""
        for widget in self.all_tickets_frame.winfo_children():
            widget.destroy()

        filters = self._filters_from(self.all_tickets_status, self.all_tickets_search)
        if self.all_tickets_priority.get() != "All":
            filters['priority'] = self.all_tickets_priority.get()
        if self.all_tickets_category.get() != "All":
            filters['category'] = self.all_tickets_category.get()
        if self.all_tickets_team.get() != "All":
            filters['team'] = self._team_choices.get(self.all_tickets_team.get())
        assigned = self.all_tickets_assigned.get().strip()
        if assigned:
            filters['assigned_to'] = None if assigned.upper() == 'UNASSIGNED' else assigned

        result = _c.run(self.root, _c.ss('service').list_tickets, _c.actor(self), filters,
                        page=1, per_page=500)
        tickets = (result or {}).get('tickets') or []
        self.all_tickets_tree = None
        if not tickets:
            ttk.Label(self.all_tickets_frame, text=_t('gui.pastoral.student_support.ticket_forms.labels.no_tickets_found_with_current_filters', default="📭 No tickets found with current filters")).pack(pady=20)
            return

        columns = ('ID', 'Title', 'Requester', 'Status', 'Priority', 'Category', 'Team', 'Tier',
                   'Assigned', 'Created', 'Updated')
        tree = _c.tree_with_scroll(self.all_tickets_frame, columns, height=22, selectmode='extended',
                                   widths={'ID': 55, 'Title': 240, 'Requester': 100, 'Status': 120,
                                           'Priority': 75, 'Category': 150, 'Team': 130,
                                           'Tier': 95, 'Assigned': 95, 'Created': 120,
                                           'Updated': 120})
        for ticket in tickets:
            base = self._ticket_row_values(ticket)
            values = base[:2] + (ticket.get('student_id') or ticket.get('requester_username') or '',) \
                + base[2:7] + (ticket.get('assigned_to') or '',) + base[7:]
            tags = []
            priority = str(ticket.get('priority') or '').lower()
            if priority in ('critical', 'urgent', 'high'):
                tags.append(priority)
            if ticket.get('sentiment') == 'frustrated':
                tags.append('frustrated')
            tree.insert('', 'end', values=values, tags=tags)
        tree.tag_configure('critical', background='#fee2e2', foreground='#dc2626')
        tree.tag_configure('urgent', background='#fed7aa', foreground='#ea580c')
        tree.tag_configure('high', background='#fef3c7', foreground='#d97706')
        tree.tag_configure('frustrated', background='#fce7f3', foreground='#be185d')

        tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))
        tree.bind('<Return>', lambda e: self.on_ticket_double_click(tree))
        tree.bind('<Button-3>', lambda e: self.show_staff_ticket_context_menu(e, tree))
        if getattr(self, 'bulk_count_label', None) is not None:
            tree.bind('<<TreeviewSelect>>', lambda e: self.bulk_count_label.config(
                text=f"{len(tree.selection())} selected"))
        self.all_tickets_tree = tree
        total = (result or {}).get('total_count', len(tickets))
        self.update_status(f"Loaded {len(tickets)} of {total} tickets")

    def _export_list(self, attr, default_name):
        tree = getattr(self, attr, None)
        if tree is None or not tree.winfo_exists():
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_forms.dialogs.export', default="Export"),
                                _t('gui.pastoral.student_support.ticket_forms.dialogs.nothing_listed', default="There is nothing in the list to export."))
            return
        _c.export_tree_csv(self, tree, default_name)

    def on_ticket_double_click(self, tree):
        """Handle double-click on ticket in tree view"""
        selection = tree.selection()
        if selection:
            item = tree.item(selection[0])
            ticket_id = item['values'][0]  # First column is ticket ID
            self.view_ticket_details(ticket_id)

    def show_ticket_context_menu(self, event, tree):
        """Show context menu for ticket"""
        context_menu = tk.Menu(self.root, tearoff=0)
        item = tree.identify_row(event.y)
        if item:
            if item not in tree.selection():
                tree.selection_set(item)
            ticket_id = tree.item(item)['values'][0]

            context_menu.add_command(label=_t('gui.pastoral.student_support.ticket_forms.menus.view_details', default="👁️ View Details"),
                                   command=lambda: self.view_ticket_details(ticket_id))
            context_menu.add_command(label=_t('gui.pastoral.student_support.ticket_forms.menus.add_response', default="💬 Add Response"),
                                   command=lambda: self.show_add_response_dialog_by_id(ticket_id))

            if self.is_staff():
                context_menu.add_separator()
                context_menu.add_command(label=_t('gui.pastoral.student_support.ticket_forms.menus.update_status', default="📊 Update Status"),
                                       command=lambda: self.show_status_update_dialog(ticket_id))
                context_menu.add_command(label=_t('gui.pastoral.student_support.ticket_forms.menus.assign_to_me', default="👨‍💼 Assign to Me"),
                                       command=lambda: self.assign_ticket_to_me(ticket_id))

            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
