
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
import json
import os
import threading
from functools import partial
import webbrowser
from education_system.systems.university.infrastructure.email.template_utils import render_template

# Import authentication - REQUIRED (no fallback for security)
from education_system.systems.university.infrastructure.auth import UserAuth, get_global_auth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import activity logger for audit trail
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk.base import HelpdeskGUI
from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk import _tickets as T

def create_new_ticket_tab(self):
    """Create new ticket tab"""
    ticket_frame = ttk.Frame(self.notebook)
    self.notebook.add(ticket_frame, text=_t('gui.pastoral.helpdesk.ticket_create.tabs.create_ticket', default="Create Ticket"))

    # Create scrollable frame
    canvas = tk.Canvas(ticket_frame)
    scrollbar = ttk.Scrollbar(ticket_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Title
    ttk.Label(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.create_new_support_ticket', default="Create New Support Ticket"),
             style='Title.TLabel').pack(pady=10)

    # Known issues: "I'm affected" adds the person to the incident instead of a new report
    from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk import (
        support_tools,
    )
    known = support_tools.known_issues_frame(scrollable_frame, self.auth)
    if known is not None:
        known.pack(fill='x', padx=10, pady=5)

    # Template selection
    template_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.use_template_optional', default="Use Template (Optional)"))
    template_frame.pack(fill='x', padx=10, pady=5)

    self.template_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_create.values.custom', default="custom"))
    ttk.Radiobutton(template_frame, text=_t('gui.pastoral.helpdesk.ticket_create.buttons.custom_ticket', default="Custom Ticket"), variable=self.template_var,
                   value="custom").pack(anchor='w', padx=5, pady=2)

    # Load available templates
    templates = self.get_ticket_templates()
    for template in templates:
        ttk.Radiobutton(template_frame, text=f"{template['name']} ({template['category']})",
                       variable=self.template_var, value=str(template['template_id']),
                       command=lambda t=template: self.load_template(t)).pack(anchor='w', padx=5, pady=2)

    # Ticket form
    form_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.ticket_details', default="Ticket Details"))
    form_frame.pack(fill='x', padx=10, pady=5)

    # Subject
    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.subject_variant_2', default="Subject:")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
    self.subject_entry = ttk.Entry(form_frame, width=60)
    self.subject_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)

    # Category
    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.category_variant_2', default="Category:")).grid(row=1, column=0, sticky='w', padx=5, pady=5)
    self.category_var = tk.StringVar()
    category_combo = ttk.Combobox(form_frame, textvariable=self.category_var,
                                 values=T.CATEGORIES, state="readonly")
    category_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=5)

    # Priority, Impact, Urgency
    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.priority_variant_2', default="Priority:")).grid(row=2, column=0, sticky='w', padx=5, pady=5)
    self.priority_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_create.values.medium', default="medium"))
    priority_combo = ttk.Combobox(form_frame, textvariable=self.priority_var,
                                 values=["low", "medium", "high"], state="readonly")
    priority_combo.grid(row=2, column=1, sticky='ew', padx=5, pady=5)

    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.impact_variant_2', default="Impact:")).grid(row=3, column=0, sticky='w', padx=5, pady=5)
    self.impact_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_create.values.low', default="low"))
    impact_combo = ttk.Combobox(form_frame, textvariable=self.impact_var,
                               values=["low", "medium", "high"], state="readonly")
    impact_combo.grid(row=3, column=1, sticky='ew', padx=5, pady=5)

    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.urgency_variant_2', default="Urgency:")).grid(row=4, column=0, sticky='w', padx=5, pady=5)
    self.urgency_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_create.values.low', default="low"))
    urgency_combo = ttk.Combobox(form_frame, textvariable=self.urgency_var,
                                values=["low", "medium", "high"], state="readonly")
    urgency_combo.grid(row=4, column=1, sticky='ew', padx=5, pady=5)

    # Configure grid weights
    form_frame.grid_columnconfigure(1, weight=1)

    # Message
    message_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.message', default="Message"))
    message_frame.pack(fill='both', expand=True, padx=10, pady=5)

    self.message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
    self.message_text.pack(fill='both', expand=True, padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(scrollable_frame)
    button_frame.pack(fill='x', padx=10, pady=10)

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_create.buttons.create_ticket', default="Create Ticket"), command=self.create_ticket,
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_create.buttons.clear_form', default="Clear Form"), command=self.clear_ticket_form).pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_create.buttons.suggest_articles', default="Suggest Help Articles"),
              command=lambda: self.suggest_articles_for_ticket(
                  self.subject_entry.get(), self.message_text.get('1.0', 'end-1c'))).pack(side='left', padx=5)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_new_ticket_tab = create_new_ticket_tab

def get_ticket_templates(self):
    """Get available ticket templates"""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT template_id, name, category, subject_template, message_template,
               priority, default_impact, default_urgency
        FROM ticket_templates
        WHERE is_active = 1
        ORDER BY category, name
        ''')

        templates = cursor.fetchall()
        conn.close()

        return [dict(template) for template in templates]

    except Exception:
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_ticket_templates = get_ticket_templates

def load_template(self, template):
    """Load selected template into form"""
    try:
        self.subject_entry.delete(0, 'end')
        self.subject_entry.insert(0, template.get('subject_template', ''))

        self.category_var.set(template.get('category', ''))
        self.priority_var.set(template.get('priority', 'medium'))
        self.impact_var.set(template.get('default_impact', 'low'))
        self.urgency_var.set(template.get('default_urgency', 'low'))

        self.message_text.delete('1.0', 'end')
        self.message_text.insert('1.0', template.get('message_template', ''))

    except Exception as e:
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.error', default="Error"), f"Failed to load template: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_template = load_template

def clear_ticket_form(self):
    """Clear the ticket creation form"""
    self.subject_entry.delete(0, 'end')
    self.category_var.set('')
    self.priority_var.set('medium')
    self.impact_var.set('low')
    self.urgency_var.set('low')
    self.message_text.delete('1.0', 'end')
    self.template_var.set('custom')

# Attach method to HelpdeskGUI class
HelpdeskGUI.clear_ticket_form = clear_ticket_form

def create_ticket(self):
    """Create new support ticket"""
    try:
        # Validate form
        subject = self.subject_entry.get().strip()
        category = self.category_var.get()
        message = self.message_text.get('1.0', 'end-1c').strip()

        if not subject:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_create.dialogs.subject_is_required', default="Subject is required"))
            return

        if not category:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_create.dialogs.category_is_required', default="Category is required"))
            return

        if not message:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_create.dialogs.message_is_required', default="Message is required"))
            return

        # Create ticket
        ticket_data = {
            'subject': subject,
            'message': message,
            'category': category,
            'priority': self.priority_var.get(),
            'impact': self.impact_var.get(),
            'urgency': self.urgency_var.get()
        }

        ticket_id = self.create_support_ticket(ticket_data)
        if ticket_id:
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_create.dialogs.success', default="Success"),
                                _t('gui.pastoral.helpdesk.ticket_create.dialogs.ticket_number_created', default="Ticket #{ticket_id} created successfully!").format(ticket_id=ticket_id))
            self.clear_ticket_form()
            self.refresh_my_tickets()
            # Switch to My Tickets tab
            self.notebook.select(1)

    except Exception as e:
        T.show_error(e)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket = create_ticket

def create_support_ticket(self, ticket_data):
    """Raise the ticket through the Helpdesk ticket service (routing, tier,
    crisis check, SLA and notices all apply). Returns its number, or None
    after showing why it could not be raised."""
    return self.create_ticket_with_details(
        ticket_data['subject'], ticket_data['message'], ticket_data['category'],
        ticket_data.get('priority') or 'medium', ticket_data.get('impact') or 'low',
        ticket_data.get('urgency') or 'low', ticket_data.get('subcategory'))

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_support_ticket = create_support_ticket

def show_create_ticket(self):
    """Switch to create ticket tab"""
    # Find the create ticket tab and select it
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'Create Ticket':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_create_ticket = show_create_ticket

def create_ticket_enhanced(self):
    """Enhanced ticket creation with templates and validation"""
    if not self.current_user:
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_create.dialogs.you_must_be_logged_in_to_create_a_support_ticket', default="You must be logged in to create a support ticket."))
        return

    if not self.has_permission('create_ticket'):
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.helpdesk.ticket_create.dialogs.you_don_t_have_permission_to_create_support_tickets', default="You don't have permission to create support tickets."))
        return

    # Create enhanced ticket creation dialog
    dialog = tk.Toplevel(self.root)
    dialog.title(_t('gui.pastoral.helpdesk.ticket_create.windows.create_enhanced_ticket', default="Create Enhanced Ticket"))
    dialog.geometry("700x600")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main container
    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    # Title
    ttk.Label(main_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.create_new_support_ticket', default="Create New Support Ticket"),
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

    # Template selection
    template_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.template_selection', default="Template Selection"), padding="10")
    template_frame.pack(fill='x', pady=(0, 10))

    ttk.Label(template_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.select_a_template_to_auto_fill_form', default="Select a template to auto-fill form:")).pack(anchor='w')

    template_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_create.values.custom', default='custom'))
    template_combo = ttk.Combobox(template_frame, textvariable=template_var, state="readonly", width=50)
    template_combo.pack(fill='x', pady=5)

    # Load templates
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT template_id, name, description FROM ticket_templates
            WHERE is_active = 1 ORDER BY category, name
        ''')
        templates = cursor.fetchall()
        conn.close()

        template_list = ['Custom (No Template)']
        template_map = {0: None}

        for idx, (tid, name, desc) in enumerate(templates, 1):
            template_list.append(f"{name} - {desc}")
            template_map[idx] = tid

        template_combo['values'] = template_list
    except Exception as e:
        print(f"Error loading templates: {e}")
        template_combo['values'] = ['Custom (No Template)']
        template_map = {0: None}

    # Form fields
    form_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.ticket_information', default="Ticket Information"), padding="10")
    form_frame.pack(fill='both', expand=True, pady=(0, 10))

    # Subject
    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.subject', default="Subject *")).grid(row=0, column=0, sticky='w', pady=2)
    subject_entry = ttk.Entry(form_frame, width=60)
    subject_entry.grid(row=0, column=1, columnspan=2, sticky='ew', pady=2)

    # Category with subcategory
    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.category', default="Category *")).grid(row=1, column=0, sticky='w', pady=2)
    category_var = tk.StringVar()
    category_combo = ttk.Combobox(form_frame, textvariable=category_var, state="readonly", width=28)
    category_combo['values'] = T.CATEGORIES
    category_combo.grid(row=1, column=1, sticky='w', pady=2)

    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.subcategory', default="Subcategory")).grid(row=1, column=2, sticky='w', pady=2, padx=(10,0))
    subcategory_var = tk.StringVar()
    subcategory_combo = ttk.Combobox(form_frame, textvariable=subcategory_var, state="readonly", width=25)
    subcategory_combo.grid(row=1, column=3, sticky='w', pady=2)

    # Priority, Impact, Urgency
    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.priority', default="Priority *")).grid(row=2, column=0, sticky='w', pady=2)
    priority_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_create.values.medium', default='medium'))
    priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
    priority_combo['values'] = ['low', 'medium', 'high']
    priority_combo.grid(row=2, column=1, sticky='w', pady=2)

    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.impact', default="Impact *")).grid(row=3, column=0, sticky='w', pady=2)
    impact_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_create.values.low', default='low'))
    impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
    impact_combo['values'] = ['low', 'medium', 'high']
    impact_combo.grid(row=3, column=1, sticky='w', pady=2)

    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.urgency', default="Urgency *")).grid(row=4, column=0, sticky='w', pady=2)
    urgency_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_create.values.low', default='low'))
    urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
    urgency_combo['values'] = ['low', 'medium', 'high']
    urgency_combo.grid(row=4, column=1, sticky='w', pady=2)

    # Message
    ttk.Label(form_frame, text=_t('gui.pastoral.helpdesk.ticket_create.labels.description', default="Description *")).grid(row=5, column=0, sticky='nw', pady=2)
    message_text = scrolledtext.ScrolledText(form_frame, height=10, width=60)
    message_text.grid(row=5, column=1, columnspan=3, sticky='ew', pady=2)

    # Configure grid weights
    form_frame.columnconfigure(1, weight=1)

    # Update subcategory when category changes
    def update_subcategories(event=None):
        cat = category_var.get()
        subcategories_map = {
            "Technical Support": ["Login Issues", "Performance Problems", "Software Bugs", "Hardware Problems"],
            "Academic Inquiry": ["Course Information", "Grading Questions", "Academic Records", "Transcript Requests"],
            "Financial Services": ["Payment Plans", "Refunds", "Financial Aid", "Billing Inquiries"],
            "Account Access": ["Password Reset", "Account Locked", "Permission Issues", "Profile Updates"],
            "Other": ["General Inquiry", "Feedback", "Complaint", "Suggestion"]
        }
        subcategory_combo['values'] = subcategories_map.get(cat, [])
        if subcategory_combo['values']:
            subcategory_combo.current(0)

    category_combo.bind('<<ComboboxSelected>>', update_subcategories)

    # Load template when selected
    def load_template(event=None):
        idx = template_combo.current()
        if idx > 0 and idx in template_map:
            template_id = template_map[idx]
            self.create_ticket_from_template_gui(template_id, subject_entry, category_var,
                                                 priority_var, impact_var, urgency_var, message_text)

    template_combo.bind('<<ComboboxSelected>>', load_template)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(0, 5))

    def submit_ticket():
        subject = subject_entry.get().strip()
        category = category_var.get()
        subcategory = subcategory_var.get()
        message = message_text.get('1.0', 'end-1c').strip()
        priority = priority_var.get()
        impact = impact_var.get()
        urgency = urgency_var.get()

        if not subject or not category or not message:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_create.dialogs.subject_category_and_description_are_required', default="Subject, category, and description are required"))
            return

        # Create ticket using enhanced method
        ticket_id = self.create_ticket_with_details(subject, message, category, priority,
                                                   impact, urgency, subcategory)
        if ticket_id:
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_create.dialogs.success', default="Success"), f"Ticket #{ticket_id} created successfully!")
            dialog.destroy()
            self.refresh_my_tickets()
        # else: create_ticket_with_details has shown why

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_create.buttons.create_ticket', default="Create Ticket"), command=submit_ticket).pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_create.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_enhanced = create_ticket_enhanced

def create_ticket_from_template_gui(self, template_id, subject_entry, category_var,
                                    priority_var, impact_var, urgency_var, message_text):
    """Load template data into form fields"""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM ticket_templates WHERE template_id = ?', (template_id,))
        template = cursor.fetchone()
        conn.close()

        if not template:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_create.dialogs.template_not_found', default="Template not found"))
            return

        # Unpack template data (adjust indices based on schema)
        # Assuming: template_id, name, description, category, subject_template, message_template,
        #           default_priority, default_impact, default_urgency, form_fields
        _, name, desc, category, subj_tpl, msg_tpl, pri, imp, urg, form_fields = template[:10]

        # Fill in form fields
        if subj_tpl:
            subject_entry.delete(0, 'end')
            subject_entry.insert(0, subj_tpl)

        if category:
            category_var.set(category)

        if pri:
            priority_var.set(pri)
        if imp:
            impact_var.set(imp)
        if urg:
            urgency_var.set(urg)

        if msg_tpl:
            message_text.delete('1.0', 'end')
            message_text.insert('1.0', msg_tpl)

    except Exception as e:
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_create.dialogs.error', default="Error"), f"Failed to load template: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_from_template_gui = create_ticket_from_template_gui

def create_custom_ticket_gui(self):
    """Create ticket with custom form fields (wrapper for create_ticket_enhanced)"""
    # This is essentially the same as create_ticket_enhanced but can be extended
    # with dynamic custom fields from database
    self.create_ticket_enhanced()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_custom_ticket_gui = create_custom_ticket_gui

def create_ticket_with_details(self, subject, message, category, priority, impact, urgency, subcategory=None):
    """Raise a Helpdesk ticket through the ticket service: the category's
    team and department, the least-loaded free team member, the SLA, the
    confidentiality tier and the crisis check all come from the service.
    Crisis contacts are shown at once. Returns the ticket number, or None
    after showing why it could not be raised."""
    try:
        result = T.hd.submit_helpdesk_ticket(
            T.actor(self), subject=subject, description=message, category=category,
            priority=priority or 'medium', impact=impact or 'low', urgency=urgency or 'low',
            subcategory=subcategory or None, channel='web')
    except Exception as e:
        T.show_error(e)
        return None
    T.show_crisis(result.get('crisis'))
    visit = getattr(self, '_deflection_visit', None)
    if visit:
        self._deflection_visit = None
        try:
            T.deflection().finish(T.actor(self), visit, result['ticket_id'])
        except Exception:
            T.logger.debug("Could not close the suggestion visit", exc_info=True)
    return result['ticket_id']

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_with_details = create_ticket_with_details


def suggest_articles_for_ticket(self, subject, message):
    """Self-help before raising a ticket: matches from both knowledge bases
    (Student Support's and the Helpdesk's) for what has been typed so far.
    The visit is recorded, so the deflection figures count it."""
    text = f"{subject or ''} {message or ''}".strip()
    if not text:
        messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_create.dialogs.info', default="Info"),
                            _t('gui.pastoral.helpdesk.ticket_create.dialogs.type_first', default="Type a subject or message first."))
        return
    defl = T.deflection()
    try:
        found = defl.suggest(text, limit=8)
    except Exception as e:
        T.show_error(e)
        return
    if not found:
        messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_create.dialogs.no_articles', default="No Articles"),
                            _t('gui.pastoral.helpdesk.ticket_create.dialogs.no_matching_articles', default="No help articles match yet; please raise your ticket."))
        return
    try:
        self._deflection_visit = defl.start(T.actor(self), text, found)
    except Exception:
        self._deflection_visit = None
        T.logger.debug("Could not record the suggestion visit", exc_info=True)

    win = tk.Toplevel(self.root)
    win.title(_t('gui.pastoral.helpdesk.ticket_create.windows.suggested_articles', default="Suggested Help Articles"))
    win.geometry("700x500")
    win.transient(self.root)
    bar = ttk.Frame(win)
    bar.pack(side='bottom', fill='x', padx=10, pady=10)
    listbox = tk.Listbox(win, height=8)
    listbox.pack(fill='x', padx=10, pady=(10, 5))
    for item in found:
        listbox.insert('end', item['title'])
    body = scrolledtext.ScrolledText(win, height=12, wrap='word', state='disabled')
    body.pack(fill='both', expand=True, padx=10, pady=5)

    def show(_event=None):
        sel = listbox.curselection()
        if not sel:
            return
        item = found[sel[0]]
        body.config(state='normal')
        body.delete('1.0', 'end')
        body.insert('1.0', f"{item['title']}\n\n{item['snippet']}")
        body.config(state='disabled')
        if self._deflection_visit:
            try:
                defl.viewed(T.actor(self), self._deflection_visit, item['key'])
            except Exception:
                T.logger.debug("Could not record the article view", exc_info=True)

    def solved():
        visit, self._deflection_visit = self._deflection_visit, None
        if visit:
            try:
                defl.finish(T.actor(self), visit)
            except Exception:
                T.logger.debug("Could not close the suggestion visit", exc_info=True)
        win.destroy()

    listbox.bind('<<ListboxSelect>>', show)
    ttk.Button(bar, text=_t('gui.pastoral.helpdesk.ticket_create.buttons.this_solved_it', default="This solved my problem"),
               command=solved).pack(side='left', padx=5)
    ttk.Button(bar, text=_t('gui.pastoral.helpdesk.ticket_create.buttons.still_need_help', default="I still need help"),
               command=win.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.suggest_articles_for_ticket = suggest_articles_for_ticket
