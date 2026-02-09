import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from university_system.modules.shared.constants import paths

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.email.templates import load_template, render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False
    load_template = lambda *args, **kwargs: None
    render_template = lambda *args, **kwargs: (None, None)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this module when targeting the
# student_records.db database. Many functions within this GUI refer to
# str(DEFAULT_DB_PATH) without specifying a full path. Without this
# override, a new database would be created in the current working
# directory, leading to multiple database files and missing tables. The
# override redirects connections to the shared student_records.db in
# university_system/data/db_files. If a different database name/path is
# supplied, the connection falls back to the original behaviour.

_original_sqlite3_connect = sqlite3.connect  # preserve original

def _patched_sqlite_connect(database, *args, **kwargs):
    """Redirect connections targeting student_records.db to the central path."""
    try:
        # Determine basename; accept Path or str
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name == str(DEFAULT_DB_PATH):
            return _original_sqlite3_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite3_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect

# Import all functionality from student_support module (it's a single monolithic file)
try:
    # Import everything from the single student_support module
    from university_system.modules.domain.student_affairs.services.student_support import (
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
        from university_system.modules.domain.student_affairs.services.student_support import (
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

class SearchMixin:
    def show_search(self):
        """Show advanced search interface"""
        self.clear_content()
        
        search_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(search_frame, text="🔍 Advanced Search")

        # Configure frame to expand
        search_frame.rowconfigure(0, weight=1)
        search_frame.columnconfigure(0, weight=1)
        
        # Search form
        form_frame = ttk.LabelFrame(search_frame, text="Search Parameters", padding="10")
        form_frame.pack(fill="x", pady=(0, 10))
        
        # Search query
        ttk.Label(form_frame, text="Search Query:").grid(row=0, column=0, sticky="w", pady=5)
        self.search_query = ttk.Entry(form_frame, width=50)
        self.search_query.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=5)
        self.search_query.bind('<Return>', lambda e: self.perform_search())
        
        # Search type
        ttk.Label(form_frame, text="Search In:").grid(row=1, column=0, sticky="w", pady=5)
        self.search_type = ttk.Combobox(form_frame, values=[
            "Everything", "Tickets", "FAQs", "Resources", "Knowledge Base"
        ], state="readonly")
        self.search_type.set("Everything")
        self.search_type.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=5)
        
        # Search button
        search_btn_frame = ttk.Frame(form_frame)
        search_btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(search_btn_frame, text="🔍 Search", 
                  command=self.perform_search, style='Primary.TButton').pack()
        
        form_frame.columnconfigure(1, weight=1)
        
        # Results area
        self.search_results_frame = ttk.LabelFrame(search_frame, text="Search Results", padding="10")
        self.search_results_frame.pack(fill="both", expand=True)
        
        # Results notebook
        self.results_notebook = ttk.Notebook(self.search_results_frame)
        self.results_notebook.pack(fill="both", expand=True)

    def perform_search(self):
        """Perform advanced search"""
        query = self.search_query.get().strip()
        if not query:
            messagebox.showwarning("Search", "Please enter a search query")
            return
        
        if not self.support:
            messagebox.showerror("Error", "Support system not initialized")
            return
        
        # Clear previous results
        for tab in self.results_notebook.tabs():
            self.results_notebook.forget(tab)
        
        search_type_map = {
            "Everything": "global",
            "Tickets": "tickets", 
            "FAQs": "faqs",
            "Resources": "resources",
            "Knowledge Base": "kb"
        }
        
        search_type = search_type_map.get(self.search_type.get(), "global")
        
        try:
            self.update_status(f"Searching for '{query}'...")
            results = self.support.advanced_search(query, search_type)
            self.display_search_results(results)
            self.update_status(f"Search completed for '{query}'")
        except Exception as e:
            messagebox.showerror("Search Error", f"Search failed: {e}")
            self.update_status("Search failed")

    def display_search_results(self, results):
        """Display search results in tabs"""
        total_results = 0
        
        # Tickets results
        if 'tickets' in results and results['tickets'] is not None:
            ticket_data = results['tickets']
            tickets = ticket_data.get('tickets', []) if isinstance(ticket_data, dict) else []
            if tickets:
                self.create_tickets_results_tab(tickets)
                total_results += len(tickets)
        
        # FAQs results
        if 'faqs' in results:
            faqs = results['faqs']
            if faqs:
                self.create_faqs_results_tab(faqs)
                total_results += len(faqs)
        
        # Resources results
        if 'resources' in results:
            resources = results['resources']
            if resources:
                self.create_resources_results_tab(resources)
                total_results += len(resources)
        
        # Knowledge base results
        if 'kb_articles' in results:
            articles = results['kb_articles']
            if articles:
                self.create_kb_results_tab(articles)
                total_results += len(articles)
        
        # Suggestions
        if 'suggestions' in results and results['suggestions']:
            self.create_suggestions_tab(results['suggestions'])
        
        if total_results == 0:
            # No results found
            no_results_frame = ttk.Frame(self.results_notebook, padding="20")
            self.results_notebook.add(no_results_frame, text="No Results")
            
            ttk.Label(no_results_frame, text="🔍 No results found", 
                     style='Title.TLabel').pack(pady=20)
            ttk.Label(no_results_frame, text="Try different keywords or check spelling").pack()
        
        self.search_results_frame.config(text=f"Search Results ({total_results} found)")

    def create_tickets_results_tab(self, tickets):
        """Create tickets results tab"""
        tickets_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(tickets_frame, text=f"🎫 Tickets ({len(tickets)})")
        
        # Create treeview for tickets
        columns = ('ID', 'Title', 'Status', 'Priority', 'Category', 'Created')
        tree = ttk.Treeview(tickets_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        tree.heading('ID', text='ID')
        tree.heading('Title', text='Title')
        tree.heading('Status', text='Status')
        tree.heading('Priority', text='Priority')
        tree.heading('Category', text='Category')
        tree.heading('Created', text='Created')
        
        tree.column('ID', width=80)
        tree.column('Title', width=300)
        tree.column('Status', width=100)
        tree.column('Priority', width=100)
        tree.column('Category', width=120)
        tree.column('Created', width=150)
        
        # Add tickets to tree
        for ticket in tickets:
            # Skip None or invalid ticket entries
            if ticket is None or not isinstance(ticket, dict):
                continue

            ticket_id = ticket.get('ticket_id', 'N/A')
            ticket_title = ticket.get('title', 'Untitled')
            ticket_title_display = ticket_title[:50] + ('...' if len(ticket_title) > 50 else '')
            ticket_status = ticket.get('status', 'Unknown')
            ticket_priority = ticket.get('priority', 'Normal')
            ticket_category = ticket.get('category', 'General')
            ticket_created = ticket.get('created_datetime', 'N/A')

            tree.insert('', 'end', values=(
                ticket_id,
                ticket_title_display,
                ticket_status,
                ticket_priority,
                ticket_category,
                ticket_created
            ))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tickets_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Double-click to view ticket
        tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))

    def create_faqs_results_tab(self, faqs):
        """Create FAQs results tab"""
        faqs_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(faqs_frame, text=f"❓ FAQs ({len(faqs)})")
        
        # Create scrollable list
        canvas = tk.Canvas(faqs_frame)
        scrollbar = ttk.Scrollbar(faqs_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add FAQs
        for faq in faqs:
            # Skip None or invalid FAQ entries
            if faq is None or not isinstance(faq, dict):
                continue

            faq_question = faq.get('question', 'Unknown Question')
            faq_category = faq.get('category', 'General')
            faq_answer = faq.get('answer', '')

            faq_frame = ttk.LabelFrame(scrollable_frame, text=f"Q: {faq_question}", padding="10")
            faq_frame.pack(fill="x", padx=5, pady=5)

            # FAQ details
            details_text = f"Category: {faq_category} | Views: {faq.get('view_count', 0)} | Helpful: {faq.get('helpful_votes', 0)}"
            ttk.Label(faq_frame, text=details_text, font=('Segoe UI', 9),
                     foreground=self.colors['text_secondary']).pack(anchor="w")

            # Answer preview
            answer_preview = faq_answer[:200] + ('...' if len(faq_answer) > 200 else '')
            ttk.Label(faq_frame, text=answer_preview, wraplength=600).pack(anchor="w", pady=(5, 0))

            # View full answer button
            ttk.Button(faq_frame, text="View Full Answer",
                      command=lambda f=faq: self.show_faq_detail(f)).pack(anchor="w", pady=(5, 0))
        
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def create_resources_results_tab(self, resources):
        """Create resources results tab"""
        resources_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(resources_frame, text=f"📋 Resources ({len(resources)})")
        
        # Create scrollable list
        canvas = tk.Canvas(resources_frame)
        scrollbar = ttk.Scrollbar(resources_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add resources
        for resource in resources:
            # Skip None or invalid resource entries
            if resource is None or not isinstance(resource, dict):
                continue

            resource_title = resource.get('title', 'Untitled Resource')
            resource_category = resource.get('category', 'General')
            resource_description = resource.get('description', '')

            resource_frame = ttk.LabelFrame(scrollable_frame, text=f"📄 {resource_title}", padding="10")
            resource_frame.pack(fill="x", padx=5, pady=5)

            # Resource details
            details_text = f"Category: {resource_category} | Accesses: {resource.get('access_count', 0)}"
            ttk.Label(resource_frame, text=details_text, font=('Segoe UI', 9),
                     foreground=self.colors['text_secondary']).pack(anchor="w")

            # Description
            ttk.Label(resource_frame, text=resource_description, wraplength=600).pack(anchor="w", pady=(5, 0))

            # Action button - opens resource in a window
            btn_frame = ttk.Frame(resource_frame)
            btn_frame.pack(anchor="w", pady=(5, 0))

            ttk.Button(btn_frame, text="View Resource",
                      command=lambda r=resource: self.open_resource(r)).pack(side="left")
        
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def create_kb_results_tab(self, articles):
        """Create knowledge base results tab"""
        kb_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(kb_frame, text=f"📚 Knowledge Base ({len(articles)})")
        
        # Create scrollable list
        canvas = tk.Canvas(kb_frame)
        scrollbar = ttk.Scrollbar(kb_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add articles
        for article in articles:
            # Skip None or invalid article entries
            if article is None or not isinstance(article, dict):
                continue

            article_title = article.get('title', 'Untitled Article')
            article_category = article.get('category', 'General')
            article_content = article.get('content', '')
            article_summary = article.get('summary', '')

            article_frame = ttk.LabelFrame(scrollable_frame, text=f"📖 {article_title}", padding="10")
            article_frame.pack(fill="x", padx=5, pady=5)

            # Article details
            details_text = f"Category: {article_category} | Views: {article.get('view_count', 0)} | Helpful: {article.get('helpful_votes', 0)}"
            ttk.Label(article_frame, text=details_text, font=('Segoe UI', 9),
                     foreground=self.colors['text_secondary']).pack(anchor="w")

            # Summary or content preview
            if article_summary:
                ttk.Label(article_frame, text=article_summary, wraplength=600).pack(anchor="w", pady=(5, 0))
            else:
                content_preview = article_content[:200] + ('...' if len(article_content) > 200 else '')
                ttk.Label(article_frame, text=content_preview, wraplength=600).pack(anchor="w", pady=(5, 0))

            # View full article button
            ttk.Button(article_frame, text="View Full Article",
                      command=lambda a=article: self.show_article_detail(a)).pack(anchor="w", pady=(5, 0))
        
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def create_suggestions_tab(self, suggestions):
        """Create suggestions tab"""
        suggestions_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(suggestions_frame, text="💡 Suggestions")
        
        ttk.Label(suggestions_frame, text="💡 Search Suggestions", 
                 style='Heading.TLabel').pack(anchor="w", pady=(0, 10))
        
        for suggestion in suggestions:
            suggestion_frame = ttk.Frame(suggestions_frame)
            suggestion_frame.pack(fill="x", pady=2)
            
            ttk.Label(suggestion_frame, text=f"💭 {suggestion}").pack(side="left")
            ttk.Button(suggestion_frame, text="Search", 
                      command=lambda s=suggestion: self.search_suggestion(s)).pack(side="right")

    def search_suggestion(self, suggestion):
        """Search using a suggestion"""
        self.search_query.delete(0, tk.END)
        self.search_query.insert(0, suggestion)
        self.perform_search()

