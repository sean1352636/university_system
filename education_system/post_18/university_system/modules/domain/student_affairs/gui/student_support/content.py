from education_system.post_18.university_system.core.sql_safety import escape_like
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from education_system.post_18.university_system.core import paths

# Import i18n for language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
    from education_system.post_18.university_system.infrastructure.email.templates import load_template, render_template
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
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import (
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
        from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import (
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

class ContentMixin:
    def show_faqs(self):
        """Show FAQs interface"""
        self.clear_content()

        faqs_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(faqs_frame, text="❓ FAQs")

        # Configure frame to expand
        faqs_frame.rowconfigure(0, weight=1)
        faqs_frame.columnconfigure(0, weight=1)

        # Title and search
        header_frame = ttk.Frame(faqs_frame)
        header_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(header_frame, text="❓ Frequently Asked Questions",
                 style='Title.TLabel').pack(side="left")

        search_frame = ttk.Frame(header_frame)
        search_frame.pack(side="right")

        self.faq_search = ttk.Entry(search_frame, width=30, font=('Segoe UI', 10))
        self.faq_search.pack(side="left", padx=(0, 5))
        self.faq_search.bind('<Return>', lambda e: self.search_faqs())

        ttk.Button(search_frame, text="🔍 Search", command=self.search_faqs).pack(side="left")

        # Categories
        categories_frame = ttk.LabelFrame(faqs_frame, text="📂 Browse by Category", padding="10")
        categories_frame.pack(fill="x", pady=(0, 15))

        self.faq_categories_frame = ttk.Frame(categories_frame)
        self.faq_categories_frame.pack(fill="x")

        # FAQs display area
        self.faqs_display_frame = ttk.Frame(faqs_frame)
        self.faqs_display_frame.pack(fill="both", expand=True)

        # Load FAQs
        self.load_faqs()

    def load_faqs(self):
        """Load and display FAQs"""
        try:
            # Get FAQ categories
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if FAQs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faqs'")
            if not cursor.fetchone():
                ttk.Label(self.faqs_display_frame, text="📭 No FAQs available").pack(pady=20)
                conn.close()
                return

            cursor.execute('SELECT DISTINCT category FROM faqs ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            conn.close()

            # Clear existing category buttons
            for widget in self.faq_categories_frame.winfo_children():
                widget.destroy()

            # Create category buttons
            ttk.Button(self.faq_categories_frame, text="📋 All Categories",
                      command=lambda: self.show_faqs_by_category(None)).pack(side="left", padx=(0, 5))

            for category in categories:
                ttk.Button(self.faq_categories_frame, text=f"📂 {category}",
                          command=lambda c=category: self.show_faqs_by_category(c)).pack(side="left", padx=5)

            # Show all FAQs by default
            self.show_faqs_by_category(None)

        except Exception as e:
            ttk.Label(self.faqs_display_frame, text=f"❌ Error loading FAQs: {e}").pack(pady=20)

    def show_faqs_by_category(self, category):
        """Show FAQs filtered by category"""
        self._faq_last_mode = 'category'
        self._faq_last_category = category
        self._faq_last_query = None

        if hasattr(self, 'faq_search'):
            self.faq_search.delete(0, tk.END)

        # Clear display area
        for widget in self.faqs_display_frame.winfo_children():
            widget.destroy()

        try:
            # Get FAQs
            if self.support:
                filters = {'category': category} if category else None
                faqs = self.support._search_faqs('', filters)
            else:
                faqs = []

            if not faqs:
                ttk.Label(self.faqs_display_frame, text="📭 No FAQs found").pack(pady=20)
                return

            # Create scrollable FAQ list
            canvas, scrollbar, scrollable_frame = self._create_scrollable_frame(self.faqs_display_frame)

            # Add FAQs
            for faq in faqs:
                self.create_faq_item(scrollable_frame, faq)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except Exception as e:
            ttk.Label(self.faqs_display_frame, text=f"❌ Error loading FAQs: {e}").pack(pady=20)

    def create_faq_item(self, parent, faq):
        """Create a single FAQ item"""
        faq_frame = ttk.LabelFrame(parent, text=f"❓ {faq['question']}", padding="10")
        faq_frame.pack(fill="x", padx=5, pady=5)

        # FAQ stats
        stats_text = f"📂 {faq['category']} | 👁️ {faq.get('view_count', 0)} views | 👍 {faq.get('helpful_votes', 0)} helpful"
        ttk.Label(faq_frame, text=stats_text, font=('Segoe UI', 9),
                 foreground=self.colors['text_secondary']).pack(anchor="w")

        # Answer (collapsed by default)
        answer_frame = ttk.Frame(faq_frame)

        # Toggle button
        toggle_frame = ttk.Frame(faq_frame)
        toggle_frame.pack(fill="x", pady=(10, 0))

        def toggle_answer():
            if answer_frame.winfo_viewable():
                answer_frame.pack_forget()
                toggle_btn.config(text="▶️ Show Answer")
            else:
                answer_frame.pack(fill="x", pady=(10, 0), before=toggle_frame)
                toggle_btn.config(text="🔽 Hide Answer")

        toggle_btn = ttk.Button(toggle_frame, text="▶️ Show Answer", command=toggle_answer)
        toggle_btn.pack(side="left")

        # Helpful button
        ttk.Button(toggle_frame, text="👍 Helpful",
                  command=lambda: self.mark_faq_helpful(faq['faq_id'])).pack(side="right")

        # Answer content (initially hidden)
        answer_text = scrolledtext.ScrolledText(answer_frame, height=6, wrap=tk.WORD, state='disabled')
        answer_text.pack(fill="x")

        answer_text.config(state='normal')
        answer_text.insert(1.0, faq['answer'])
        answer_text.config(state='disabled')

    def search_faqs(self):
        """Search FAQs"""
        query = self.faq_search.get().strip()
        if not query:
            self.show_faqs_by_category(None)
            return

        self._faq_last_mode = 'search'
        self._faq_last_query = query
        self._faq_last_category = None

        # Clear display area
        for widget in self.faqs_display_frame.winfo_children():
            widget.destroy()

        try:
            if self.support:
                faqs = self.support._search_faqs(query, None)
            else:
                faqs = []

            if not faqs:
                ttk.Label(self.faqs_display_frame, text=f"🔍 No FAQs found for '{query}'").pack(pady=20)
                return

            # Show search results
            results_label = ttk.Label(self.faqs_display_frame,
                                    text=f"🔍 Search Results for '{query}' ({len(faqs)} found)",
                                    style='Heading.TLabel')
            results_label.pack(anchor="w", pady=(0, 10))

            # Create scrollable results
            canvas, scrollbar, scrollable_frame = self._create_scrollable_frame(self.faqs_display_frame)

            # Add search results
            for faq in faqs:
                self.create_faq_item(scrollable_frame, faq)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except Exception as e:
            ttk.Label(self.faqs_display_frame, text=f"❌ Error searching FAQs: {e}").pack(pady=20)

    def download_attachment(self, attachment):
        """Download ticket attachment"""
        # Handle None or invalid attachment
        if attachment is None or not isinstance(attachment, dict):
            messagebox.showerror("Error", "Invalid attachment data")
            return

        try:
            attachment_id = attachment.get('attachment_id')
            if not attachment_id:
                messagebox.showerror("Error", "No attachment ID found")
                return

            file_info = self.support.download_attachment(attachment_id)

            if not file_info or not isinstance(file_info, dict):
                messagebox.showerror("Error", "Could not retrieve attachment data")
                return

            file_name = file_info.get('filename', 'download')

            # Save file dialog
            filename = filedialog.asksaveasfilename(
                title="Save Attachment",
                initialfile=file_name,
                defaultextension=os.path.splitext(file_name)[1]
            )

            if filename:
                with open(filename, 'wb') as f:
                    f.write(file_info.get('data', b''))

                messagebox.showinfo("Success", f"File saved as {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Could not download attachment: {e}")

    def open_url(self, url):
        """Open URL in web browser"""
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open URL: {e}")

    def open_file(self, file_path):
        """Open file with default application"""
        try:
            if os.path.exists(file_path):
                os.startfile(file_path)  # Windows
            else:
                messagebox.showerror("Error", "File not found")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")

    def open_resource(self, resource):
        """Open support resource in a window"""
        # Try to load content from JSON resource files
        resource_content = self._load_resource_content(resource)
        if resource_content:
            self.show_resource_detail(resource, resource_content)
        else:
            # Fallback: show basic resource info in a detail window
            self.show_resource_detail(resource, None)

    def _load_resource_content(self, resource):
        """Load resource content from JSON files in templates/resources"""
        try:
            resources_dir = Path(__file__).parent.parent.parent.parent.parent / "templates" / "resources"
            if not resources_dir.exists():
                return None

            resource_title = resource.get('title', '').lower()
            resource_id = resource.get('resource_id') or resource.get('id')

            # Search through all JSON files in the resources directory
            for json_file in resources_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    resources_list = data.get('resources', [])
                    for res in resources_list:
                        # Match by title or ID
                        if (res.get('title', '').lower() == resource_title or
                            res.get('id') == resource_id or
                            resource_title in res.get('title', '').lower() or
                            res.get('title', '').lower() in resource_title):
                            return res
                except (json.JSONDecodeError, IOError):
                    continue

            return None
        except Exception as e:
            logging.error(f"Error loading resource content: {e}")
            return None

    def show_resource_detail(self, resource, content_data=None):
        """Show resource detail in a popup window"""
        detail_window = tk.Toplevel(self.root)
        title = resource.get('title', 'Resource')
        detail_window.title(f"📄 {title}")
        detail_window.geometry("900x700")
        detail_window.transient(self.root)

        # Make window resizable
        detail_window.rowconfigure(0, weight=1)
        detail_window.columnconfigure(0, weight=1)

        # Main content frame with padding
        main_frame = ttk.Frame(detail_window, padding="20")
        main_frame.pack(fill="both", expand=True)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Header section
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 15))
        header_frame.columnconfigure(0, weight=1)

        # Title
        ttk.Label(header_frame, text=title, style='Heading.TLabel',
                  font=('Segoe UI', 14, 'bold')).pack(anchor="w")

        # Metadata
        category = resource.get('category', content_data.get('type', 'General') if content_data else 'General')
        access_count = resource.get('access_count', 0)
        last_updated = content_data.get('last_updated', '') if content_data else ''

        meta_parts = [f"📂 {category}"]
        if access_count:
            meta_parts.append(f"👁️ {access_count} views")
        if last_updated:
            meta_parts.append(f"📅 Updated: {last_updated}")

        meta_text = " | ".join(meta_parts)
        ttk.Label(header_frame, text=meta_text, font=('Segoe UI', 9),
                  foreground=self.colors.get('text_secondary', '#666666')).pack(anchor="w", pady=(5, 0))

        # Tags if available
        tags = content_data.get('tags', []) if content_data else resource.get('tags', [])
        if tags:
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = [tags]
            tags_text = "🏷️ " + ", ".join(tags)
            ttk.Label(header_frame, text=tags_text, font=('Segoe UI', 9),
                      foreground=self.colors.get('text_secondary', '#666666')).pack(anchor="w", pady=(3, 0))

        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        # Content area with scrollbar
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True)
        content_frame.rowconfigure(0, weight=1)
        content_frame.columnconfigure(0, weight=1)

        # Create scrollable text widget
        content_text = scrolledtext.ScrolledText(
            content_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            state='disabled',
            padx=10,
            pady=10
        )
        content_text.pack(fill="both", expand=True)

        # Build and insert content
        content_text.config(state='normal')

        if content_data and content_data.get('content'):
            content = content_data['content']

            # Handle structured content with introduction and sections
            if isinstance(content, dict):
                # Introduction
                if content.get('introduction'):
                    content_text.insert(tk.END, content['introduction'] + "\n\n")

                # Sections
                sections = content.get('sections', [])
                for section in sections:
                    section_title = section.get('title', '')
                    section_content = section.get('content', '')

                    if section_title:
                        content_text.insert(tk.END, f"━━━ {section_title} ━━━\n\n", 'section_header')
                    if section_content:
                        content_text.insert(tk.END, section_content + "\n\n")

                # Conclusion
                if content.get('conclusion'):
                    content_text.insert(tk.END, "━━━ Summary ━━━\n\n", 'section_header')
                    content_text.insert(tk.END, content['conclusion'] + "\n")
            else:
                # Plain text content
                content_text.insert(tk.END, str(content))
        else:
            # Fallback to resource description
            description = resource.get('description', 'No detailed content available for this resource.')
            content_text.insert(tk.END, description)

        # Configure text tags for styling
        content_text.tag_configure('section_header', font=('Segoe UI', 11, 'bold'), foreground='#2196F3')

        content_text.config(state='disabled')

        # Button frame at bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(15, 0))

        # Copy content button
        def copy_content():
            content_text.config(state='normal')
            text = content_text.get(1.0, tk.END)
            content_text.config(state='disabled')
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.update_status("Content copied to clipboard")

        ttk.Button(button_frame, text="📋 Copy Content", command=copy_content).pack(side="left", padx=(0, 10))

        # Close button
        ttk.Button(button_frame, text="❌ Close", command=detail_window.destroy).pack(side="right")

        # Update access count if possible
        self._increment_resource_access(resource)

    def _increment_resource_access(self, resource):
        """Increment the access count for a resource in the database"""
        try:
            resource_id = resource.get('resource_id') or resource.get('id')
            if not resource_id:
                return

            def update(conn):
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE support_resources
                    SET access_count = COALESCE(access_count, 0) + 1
                    WHERE resource_id = ?
                ''', (resource_id,))
                conn.commit()

            self._safe_db_call(update)
        except Exception as e:
            logging.debug(f"Could not increment resource access count: {e}")

    def show_faq_detail(self, faq):
        """Show FAQ detail in popup"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"❓ {faq['question']}")
        detail_window.geometry("1400x850")
        detail_window.transient(self.root)

        # Content
        content_frame = ttk.Frame(detail_window, padding="20")
        content_frame.pack(fill="both", expand=True)

        # Question
        ttk.Label(content_frame, text=faq['question'], style='Heading.TLabel').pack(anchor="w", pady=(0, 10))

        # Metadata
        meta_text = f"📂 {faq['category']} | 👁️ {faq.get('view_count', 0)} views | 👍 {faq.get('helpful_votes', 0)} helpful"
        ttk.Label(content_frame, text=meta_text, font=('Segoe UI', 9),
                 foreground=self.colors['text_secondary']).pack(anchor="w", pady=(0, 15))

        # Answer
        ttk.Label(content_frame, text="Answer:", font=('Segoe UI', 10, 'bold')).pack(anchor="w")

        answer_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, state='disabled')
        answer_text.pack(fill="both", expand=True, pady=(5, 15))

        answer_text.config(state='normal')
        answer_text.insert(1.0, faq['answer'])
        answer_text.config(state='disabled')

        # Feedback
        feedback_frame = ttk.Frame(content_frame)
        feedback_frame.pack(fill="x")

        ttk.Button(feedback_frame, text="👍 Helpful",
                  command=lambda: self.mark_faq_helpful(faq['faq_id'])).pack(side="left", padx=(0, 10))
        ttk.Button(feedback_frame, text="❌ Close", command=detail_window.destroy).pack(side="right")

    def mark_faq_helpful(self, faq_id):
        """Mark FAQ as helpful"""
        try:
            def update(conn):
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE faqs
                    SET helpful_votes = COALESCE(helpful_votes, 0) + 1
                    WHERE faq_id = ?
                    ''',
                    (faq_id,)
                )
                return cursor.rowcount

            updated = self._safe_db_call(update)
            if updated:
                messagebox.showinfo("Thank You", "Thank you for your feedback!")
                self.update_status("Marked FAQ as helpful")
                self.load_dashboard()
                self._refresh_faq_view()
            else:
                messagebox.showwarning("Notice", "FAQ entry not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not record feedback: {e}")

    def _refresh_faq_view(self):
        """Refresh the FAQ view based on the last interaction."""
        try:
            if getattr(self, '_faq_last_mode', 'category') == 'search' and self._faq_last_query:
                if hasattr(self, 'faq_search'):
                    self.faq_search.delete(0, tk.END)
                    self.faq_search.insert(0, self._faq_last_query)
                self.search_faqs()
            else:
                self.show_faqs_by_category(getattr(self, '_faq_last_category', None))
        except Exception:
            self.load_faqs()

    def show_knowledge_base(self):
        """Show knowledge base interface"""
        self.clear_content()

        kb_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(kb_frame, text="📚 Knowledge Base")

        # Configure frame to expand
        kb_frame.rowconfigure(0, weight=1)
        kb_frame.columnconfigure(0, weight=1)

        # Title and controls
        header_frame = ttk.Frame(kb_frame)
        header_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(header_frame, text="📚 Knowledge Base",
                 style='Title.TLabel').pack(side="left")

        # Search
        search_frame = ttk.Frame(header_frame)
        search_frame.pack(side="right")

        self.kb_search = ttk.Entry(search_frame, width=30, font=('Segoe UI', 10))
        self.kb_search.pack(side="left", padx=(0, 5))
        self.kb_search.bind('<Return>', lambda e: self.search_knowledge_base())

        ttk.Button(search_frame, text="🔍 Search", command=self.search_knowledge_base).pack(side="left")

        # Categories and filters
        filter_frame = ttk.LabelFrame(kb_frame, text="📂 Browse Articles", padding="10")
        filter_frame.pack(fill="x", pady=(0, 15))

        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill="x")

        ttk.Label(filter_grid, text="Category:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.kb_category_filter = ttk.Combobox(filter_grid, values=[
            "All", "Technical", "Academic", "Financial Aid", "Housing", "General"
        ], state="readonly")
        self.kb_category_filter.set("All")
        self.kb_category_filter.grid(row=0, column=1, padx=(0, 10))
        self.kb_category_filter.bind('<<ComboboxSelected>>', lambda e: self.load_knowledge_base())

        ttk.Label(filter_grid, text="Sort by:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.kb_sort_filter = ttk.Combobox(filter_grid, values=[
            "Most Recent", "Most Viewed", "Most Helpful", "Alphabetical"
        ], state="readonly")
        self.kb_sort_filter.set("Most Recent")
        self.kb_sort_filter.grid(row=0, column=3, padx=(0, 10))
        self.kb_sort_filter.bind('<<ComboboxSelected>>', lambda e: self.load_knowledge_base())

        ttk.Button(filter_grid, text="🔄 Refresh",
                  command=self.load_knowledge_base).grid(row=0, column=4)

        # Articles display area
        self.kb_display_frame = ttk.Frame(kb_frame)
        self.kb_display_frame.pack(fill="both", expand=True)

        # Load articles
        self.load_knowledge_base()

    def load_knowledge_base(self):
        """Load knowledge base articles"""
        self._kb_last_mode = 'list'
        self._kb_last_search = ''
        # Clear display area
        for widget in self.kb_display_frame.winfo_children():
            widget.destroy()

        try:
            if not self.support:
                ttk.Label(self.kb_display_frame, text="❌ Support system not available").pack(pady=20)
                return

            # Get filter values
            category = self.kb_category_filter.get()
            category_filter = None if category == "All" else category

            articles = self.support.get_kb_articles(category=category_filter, published_only=True)

            # Sort articles
            sort_by = self.kb_sort_filter.get()
            if sort_by == "Most Viewed":
                articles.sort(key=lambda x: x.get('view_count', 0), reverse=True)
            elif sort_by == "Most Helpful":
                articles.sort(key=lambda x: x.get('helpful_votes', 0), reverse=True)
            elif sort_by == "Alphabetical":
                articles.sort(key=lambda x: x['title'])
            else:  # Most Recent
                articles.sort(key=lambda x: x.get('published_datetime', ''), reverse=True)

            if not articles:
                ttk.Label(self.kb_display_frame, text="📭 No articles found").pack(pady=20)
                return

            # Create scrollable articles list
            canvas, scrollbar, scrollable_frame = self._create_scrollable_frame(self.kb_display_frame)

            # Add articles
            for article in articles:
                self.create_kb_article_item(scrollable_frame, article)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except Exception as e:
            ttk.Label(self.kb_display_frame, text=f"❌ Error loading articles: {e}").pack(pady=20)

    def create_kb_article_item(self, parent, article):
        """Create a knowledge base article item"""
        article_frame = ttk.LabelFrame(parent, text=f"📖 {article['title']}", padding="10")
        article_frame.pack(fill="x", padx=5, pady=5)

        # Article metadata
        meta_frame = ttk.Frame(article_frame)
        meta_frame.pack(fill="x", pady=(0, 10))

        # Left side - category and stats
        left_meta = ttk.Frame(meta_frame)
        left_meta.pack(side="left")

        meta_text = f"📂 {article['category']} | 👁️ {article.get('view_count', 0)} views | 👍 {article.get('helpful_votes', 0)} helpful"
        ttk.Label(left_meta, text=meta_text, font=('Segoe UI', 9),
                 foreground=self.colors['text_secondary']).pack(anchor="w")

        # Right side - published date
        if article.get('published_datetime'):
            ttk.Label(meta_frame, text=f"📅 Published: {article['published_datetime'][:10]}",
                     font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(side="right")

        # Summary or content preview
        if article.get('summary'):
            summary_text = article['summary']
        else:
            summary_text = article['content'][:200] + ('...' if len(article['content']) > 200 else '')

        ttk.Label(article_frame, text=summary_text, wraplength=800).pack(anchor="w", pady=(0, 10))

        # Tags
        if article.get('tags'):
            tags = article['tags'] if isinstance(article['tags'], list) else json.loads(article.get('tags', '[]'))
            if tags:
                tags_frame = ttk.Frame(article_frame)
                tags_frame.pack(fill="x", pady=(0, 10))

                ttk.Label(tags_frame, text="🏷️ Tags:", font=('Segoe UI', 9, 'bold')).pack(side="left")
                for tag in tags[:5]:  # Show max 5 tags
                    tag_label = tk.Label(tags_frame, text=tag, bg="#e5e7eb", fg="#374151",
                                       padx=6, pady=2, relief="solid", borderwidth=1,
                                       font=('Segoe UI', 8))
                    tag_label.pack(side="left", padx=(5, 0))

        # Action buttons
        btn_frame = ttk.Frame(article_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="📖 Read Full Article",
                  command=lambda: self.show_article_detail(article)).pack(side="left", padx=(0, 5))

        ttk.Button(btn_frame, text="👍 Helpful",
                  command=lambda: self.mark_article_helpful(article['article_id'])).pack(side="left")

    def search_knowledge_base(self):
        """Search knowledge base articles"""
        query = self.kb_search.get().strip()
        if not query:
            self.load_knowledge_base()
            return

        self._kb_last_mode = 'search'
        self._kb_last_search = query

        # Clear display area
        for widget in self.kb_display_frame.winfo_children():
            widget.destroy()

        try:
            if self.support:
                articles = self.support._search_knowledge_base(query, None)
            else:
                articles = []

            if not articles:
                ttk.Label(self.kb_display_frame, text=f"🔍 No articles found for '{query}'").pack(pady=20)
                return

            # Show search results
            results_label = ttk.Label(self.kb_display_frame,
                                    text=f"🔍 Search Results for '{query}' ({len(articles)} found)",
                                    style='Heading.TLabel')
            results_label.pack(anchor="w", pady=(0, 10))

            # Create scrollable results
            canvas, scrollbar, scrollable_frame = self._create_scrollable_frame(self.kb_display_frame)

            # Add search results
            for article in articles:
                self.create_kb_article_item(scrollable_frame, article)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except Exception as e:
            ttk.Label(self.kb_display_frame, text=f"❌ Error searching articles: {e}").pack(pady=20)

    def show_article_detail(self, article):
        """Show full article in a new window"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"📖 {article['title']}")
        detail_window.geometry("1500x900")
        detail_window.transient(self.root)

        # Create scrollable content
        canvas = tk.Canvas(detail_window)
        scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Article header
        header_frame = ttk.Frame(content_frame, padding="20")
        header_frame.pack(fill="x")

        ttk.Label(header_frame, text=article['title'], style='Title.TLabel').pack(anchor="w")

        # Metadata
        meta_text = f"📂 {article['category']} | ✍️ {article['author_id']} | 📅 {article.get('published_datetime', 'Not published')}"
        ttk.Label(header_frame, text=meta_text, font=('Segoe UI', 10),
                 foreground=self.colors['text_secondary']).pack(anchor="w", pady=(5, 0))

        stats_text = f"👁️ {article.get('view_count', 0)} views | 👍 {article.get('helpful_votes', 0)} helpful | 👎 {article.get('not_helpful_votes', 0)} not helpful"
        ttk.Label(header_frame, text=stats_text, font=('Segoe UI', 9),
                 foreground=self.colors['text_secondary']).pack(anchor="w", pady=(2, 0))

        # Content
        content_text_frame = ttk.Frame(content_frame, padding="20")
        content_text_frame.pack(fill="both", expand=True)

        content_text = scrolledtext.ScrolledText(content_text_frame, wrap=tk.WORD, state='disabled')
        content_text.pack(fill="both", expand=True)

        content_text.config(state='normal')
        content_text.insert(1.0, article['content'])
        content_text.config(state='disabled')

        # Feedback buttons
        feedback_frame = ttk.Frame(content_frame, padding="20")
        feedback_frame.pack(fill="x")

        ttk.Label(feedback_frame, text="Was this article helpful?", font=('Segoe UI', 10, 'bold')).pack(anchor="w")

        btn_frame = ttk.Frame(feedback_frame)
        btn_frame.pack(anchor="w", pady=(5, 0))

        ttk.Button(btn_frame, text="👍 Yes, helpful",
                  command=lambda: self.mark_article_helpful(article['article_id'])).pack(side="left", padx=(0, 10))

        ttk.Button(btn_frame, text="👎 Not helpful",
                  command=lambda: self.mark_article_not_helpful(article['article_id'])).pack(side="left")

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def mark_article_helpful(self, article_id):
        """Mark article as helpful"""
        try:
            def update(conn):
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE kb_articles
                    SET helpful_votes = COALESCE(helpful_votes, 0) + 1
                    WHERE article_id = ?
                    ''',
                    (article_id,)
                )
                return cursor.rowcount

            updated = self._safe_db_call(update)
            if updated:
                messagebox.showinfo("Thank You", "Thank you for your feedback!")
                self.update_status("Marked article as helpful")
                self.load_dashboard()
                self._refresh_kb_view()
            else:
                messagebox.showwarning("Notice", "Article not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not record feedback: {e}")

    def mark_article_not_helpful(self, article_id):
        """Mark article as not helpful"""
        try:
            def update(conn):
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE kb_articles
                    SET not_helpful_votes = COALESCE(not_helpful_votes, 0) + 1
                    WHERE article_id = ?
                    ''',
                    (article_id,)
                )
                return cursor.rowcount

            updated = self._safe_db_call(update)
            if updated:
                messagebox.showinfo("Thank You", "Thank you for your feedback!")
                self.update_status("Recorded article feedback")
                self.load_dashboard()
                self._refresh_kb_view()
            else:
                messagebox.showwarning("Notice", "Article not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not record feedback: {e}")

    def _refresh_kb_view(self):
        """Refresh knowledge base view respecting the last interaction."""
        try:
            if getattr(self, '_kb_last_mode', 'list') == 'search' and self._kb_last_search:
                if hasattr(self, 'kb_search'):
                    self.kb_search.delete(0, tk.END)
                    self.kb_search.insert(0, self._kb_last_search)
                self.search_knowledge_base()
            else:
                self.load_knowledge_base()
        except Exception:
            self.load_knowledge_base()

    def show_resources(self):
        """Show support resources interface"""
        self.clear_content()

        resources_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(resources_frame, text="📋 Resources")

        # Configure frame to expand
        resources_frame.rowconfigure(0, weight=1)
        resources_frame.columnconfigure(0, weight=1)

        # Create scrollable container for the entire page
        canvas, scrollbar, scrollable_frame = self._create_scrollable_frame(resources_frame)

        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(header_frame, text="📋 Support Resources",
                  style='Title.TLabel').pack(side="left")

        controls_frame = ttk.Frame(header_frame)
        controls_frame.pack(side="right")

        self.resource_search_var = tk.StringVar()
        search_entry = ttk.Entry(controls_frame, width=30,
                                 textvariable=self.resource_search_var,
                                 font=('Segoe UI', 10))
        search_entry.pack(side="left", padx=(0, 5))
        search_entry.bind('<Return>', lambda _: self._load_resources())

        ttk.Button(controls_frame, text="🔍 Search",
                   command=self._load_resources).pack(side="left")

        ttk.Button(controls_frame, text="🔄 Refresh",
                   command=self._refresh_resource_filters).pack(side="left", padx=(5, 0))

        filter_frame = ttk.LabelFrame(scrollable_frame, text="Filters", padding=10)
        filter_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(filter_frame, text="Category:").grid(row=0, column=0, sticky="w")
        self.resource_category_var = tk.StringVar(value="All")
        self.resource_category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.resource_category_var,
            state="readonly",
            width=25
        )
        self.resource_category_combo.grid(row=0, column=1, padx=(5, 15))
        self.resource_category_combo.bind(
            '<<ComboboxSelected>>',
            lambda _: self._load_resources()
        )

        ttk.Label(filter_frame, text="Type:").grid(row=0, column=2, sticky="w")
        self.resource_type_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.resource_type_var,
            values=["All", "Article", "Document", "Video", "Link"],
            state="readonly",
            width=20
        )
        type_combo.grid(row=0, column=3, padx=(5, 0))
        type_combo.bind('<<ComboboxSelected>>', lambda _: self._load_resources())

        ttk.Button(filter_frame, text="Clear Filters",
                   command=lambda: self._reset_resource_filters()).grid(row=0, column=4, padx=(15, 0))

        content_frame = ttk.Frame(scrollable_frame)
        content_frame.pack(fill="both", expand=True)

        columns = ("Title", "Category", "Type", "Accesses", "Updated")
        self.resources_tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=16)
        for col in columns:
            width = 220 if col == "Title" else 140
            self.resources_tree.heading(col, text=col)
            self.resources_tree.column(col, width=width, anchor="w")

        self.resources_tree.pack(side="left", fill="both", expand=True)
        self.resources_tree.bind('<<TreeviewSelect>>', self._on_resource_select)
        self.resources_tree.bind('<Double-1>', lambda _: self._open_selected_resource())

        tree_scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=self.resources_tree.yview)
        tree_scrollbar.pack(side="right", fill="y")
        self.resources_tree.configure(yscrollcommand=tree_scrollbar.set)

        detail_frame = ttk.LabelFrame(scrollable_frame, text="Resource Details", padding=10)
        detail_frame.pack(fill="x", pady=(15, 0))

        self.resource_detail_text = scrolledtext.ScrolledText(detail_frame, height=6, wrap=tk.WORD, state='disabled')
        self.resource_detail_text.pack(fill="x", expand=True, pady=(0, 10))

        action_frame = ttk.Frame(detail_frame)
        action_frame.pack(fill="x")

        self.resource_link_button = ttk.Button(action_frame, text="View Resource",
                                               command=self._open_selected_resource,
                                               state='disabled')
        self.resource_link_button.pack(side="left")

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._load_resource_categories()
        self._load_resources()

    def _load_resource_categories(self):
        """Load resource categories into the category combobox."""
        try:
            def fetch(conn):
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT category FROM support_resources ORDER BY category')
                return [row[0] for row in cursor.fetchall()]

            categories = self._safe_db_call(fetch)
            values = ["All"] + categories if categories else ["All"]
            self.resource_category_combo['values'] = values
            if self.resource_category_var.get() not in values:
                self.resource_category_var.set("All")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load resource categories: {exc}")
            self.resource_category_combo['values'] = ["All"]
            self.resource_category_var.set("All")

    def _refresh_resource_filters(self):
        self._load_resource_categories()
        self._load_resources()

    def _reset_resource_filters(self):
        self.resource_search_var.set("")
        self.resource_category_var.set("All")
        self.resource_type_var.set("All")
        self._refresh_resource_filters()

    def _load_resources(self):
        """Fetch and display support resources."""
        try:
            category = self.resource_category_var.get()
            resource_type = self.resource_type_var.get()
            search = self.resource_search_var.get().strip()

            def fetch(conn):
                cursor = conn.cursor()
                query = '''
                    SELECT resource_id, title, category, content_type, access_count,
                           COALESCE(updated_datetime, created_datetime) as updated_at,
                           description, url, file_path, requires_auth, tags
                    FROM support_resources
                '''
                conditions = []
                params = []

                if category and category != "All":
                    conditions.append("category = ?")
                    params.append(category)

                if resource_type and resource_type != "All":
                    conditions.append("LOWER(content_type) = ?")
                    params.append(resource_type.lower())

                if search:
                    conditions.append("""
                        (LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tags) LIKE ?)
                    """)
                    like_term = f"%{escape_like(search.lower())}%"
                    params.extend([like_term, like_term, like_term])

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY updated_at DESC"

                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

            resources = self._safe_db_call(fetch) or []
            self.resource_records = {res['resource_id']: res for res in resources}

            for item in self.resources_tree.get_children():
                self.resources_tree.delete(item)

            for res in resources:
                content_type = (res.get('content_type') or 'Unknown').title()
                updated = res.get('updated_at') or ''
                self.resources_tree.insert(
                    '',
                    tk.END,
                    iid=str(res['resource_id']),
                    values=(
                        res['title'],
                        res['category'],
                        content_type,
                        res.get('access_count', 0),
                        updated[:16] if updated else '—'
                    )
                )

            if not resources:
                self.resource_detail_text.config(state='normal')
                self.resource_detail_text.delete(1.0, tk.END)
                self.resource_detail_text.insert(1.0, "No resources found matching the current filters.")
                self.resource_detail_text.config(state='disabled')
                self.resource_link_button.config(state='disabled')
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load resources: {exc}")

    def _on_resource_select(self, event=None):
        """Display details for the selected resource."""
        selection = self.resources_tree.selection()
        if not selection:
            self.resource_link_button.config(state='disabled')
            return

        resource_id = int(selection[0])
        resource = self.resource_records.get(resource_id)
        if not resource:
            self.resource_link_button.config(state='disabled')
            return

        details = [
            f"Title: {resource['title']}",
            f"Category: {resource['category']}",
            f"Type: {resource.get('content_type', 'Unknown')}",
            f"Accesses: {resource.get('access_count', 0)}",
            f"Updated: {resource.get('updated_at', '—')}",
        ]
        if resource.get('requires_auth'):
            details.append("Access: 🔒 Login required")
        if resource.get('description'):
            details.append(f"\nDescription:\n{resource['description']}")
        if resource.get('tags'):
            tags = resource['tags']
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = [tags]
            if tags:
                details.append(f"\nTags: {', '.join(tags)}")

        self.resource_detail_text.config(state='normal')
        self.resource_detail_text.delete(1.0, tk.END)
        self.resource_detail_text.insert(1.0, "\n".join(details))
        self.resource_detail_text.config(state='disabled')

        # Enable the view button for all resources (content displayed in window)
        self.resource_link_button.config(state='normal')

    def _open_selected_resource(self):
        """Open the selected resource in a detail window."""
        selection = self.resources_tree.selection()
        if not selection:
            return

        resource = self.resource_records.get(int(selection[0]))
        if not resource:
            return

        if resource.get('requires_auth') and not self.auth.current_user:
            messagebox.showwarning("Restricted", "Please sign in to access this resource.")
            return

        # Open resource in a window instead of browser/external app
        self.open_resource(resource)
        self.update_status(f"Opened resource: {resource.get('title', 'Unknown')}")

    def _copy_resource_link(self):
        """Copy the selected resource URL to the clipboard."""
        selection = self.resources_tree.selection()
        if not selection:
            messagebox.showwarning("Copy Link", "Select a resource first.")
            return

        resource = self.resource_records.get(int(selection[0]))
        if resource and resource.get('url'):
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(resource['url'])
                self.update_status("Resource link copied to clipboard")
            except Exception as exc:
                messagebox.showerror("Error", f"Could not copy link: {exc}")
        else:
            messagebox.showwarning("Copy Link", "The selected resource does not have a URL.")

