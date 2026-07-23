import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
from tkinter.font import Font
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
import json
import os
import threading
from functools import partial
import webbrowser
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

# Import authentication - REQUIRED (no fallback for security)
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import (
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
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import all the original functions from helpdesk.py
# This ensures backwards compatibility
try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk import (
        backup_database, bulk_assign_tickets, check_data_integrity,
        create_kb_article, display_helpdesk_menu, escalate_ticket,
        escalate_ticket_manual, export_tickets_csv, export_users_csv,
        init_default_data, init_helpdesk_db, search_kb_articles,
        setup_enhanced_helpdesk_permissions
    )
except ImportError:
    # If helpdesk.py is not available, we'll define minimal stubs
    print("Warning: helpdesk.py not found. Running in standalone mode.")

    def init_helpdesk_db():
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Create support_tickets table with enhanced fields
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                assigned_to INTEGER,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'medium',
                impact TEXT DEFAULT 'low',
                urgency TEXT DEFAULT 'low',
                source TEXT DEFAULT 'web',
                resolution TEXT,
                satisfaction_rating INTEGER,
                satisfaction_feedback TEXT,
                estimated_hours REAL,
                actual_hours REAL,
                due_date TEXT,
                resolved_at TEXT,
                first_response_at TEXT,
                last_activity_at TEXT,
                escalation_level INTEGER DEFAULT 0,
                tags TEXT,
                department TEXT,
                organization_id INTEGER,
                parent_ticket_id INTEGER,
                knowledge_base_articles TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (assigned_to) REFERENCES users (id),
                FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
            )
            ''')

            # Add subject column if it doesn't exist (migration)
            try:
                # Check if subject column exists using PRAGMA
                cursor.execute("PRAGMA table_info(support_tickets)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'subject' not in columns:
                    cursor.execute("ALTER TABLE support_tickets ADD COLUMN subject TEXT DEFAULT 'No Subject'")
                    conn.commit()
            except Exception as e:
                print(f"Warning: Could not add subject column: {e}")

            # Create ticket_replies table with enhanced fields
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_replies (
                reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                message TEXT NOT NULL,
                is_internal BOOLEAN DEFAULT 0,
                reply_type TEXT DEFAULT 'comment',
                time_spent REAL DEFAULT 0,
                created_at TEXT,
                edited_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Create ticket_attachments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_attachments (
                attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                reply_id INTEGER,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                file_hash TEXT,
                uploaded_by INTEGER,
                file_path TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (reply_id) REFERENCES ticket_replies (reply_id),
                FOREIGN KEY (uploaded_by) REFERENCES users (id)
            )
            ''')

            # Create ticket_assignments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                assigned_from INTEGER,
                assigned_to INTEGER,
                assignment_reason TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (assigned_from) REFERENCES users (id),
                FOREIGN KEY (assigned_to) REFERENCES users (id)
            )
            ''')

            # Create ticket_templates table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                subject_template TEXT,
                message_template TEXT,
                priority TEXT,
                default_impact TEXT,
                default_urgency TEXT,
                form_fields TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Create sla_policies table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sla_policies (
                sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                priority TEXT,
                impact TEXT,
                urgency TEXT,
                first_response_hours INTEGER,
                resolution_hours INTEGER,
                escalation_hours INTEGER,
                business_hours_only BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            ''')

            # Create ticket_workflows table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_workflows (
                workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                trigger_type TEXT NOT NULL,
                trigger_conditions TEXT,
                actions TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Create ticket_time_tracking table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_time_tracking (
                time_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                duration_minutes INTEGER,
                description TEXT,
                billable BOOLEAN DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Create ticket_escalations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_escalations (
                escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                escalation_level INTEGER,
                escalated_to INTEGER,
                escalated_by INTEGER,
                escalation_reason TEXT,
                resolved BOOLEAN DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (escalated_to) REFERENCES users (id),
                FOREIGN KEY (escalated_by) REFERENCES users (id)
            )
            ''')

            # Create ticket_links table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_links (
                link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                linked_ticket_id INTEGER,
                link_type TEXT,
                created_by INTEGER,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Create ticket_audit_log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                action TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Create knowledge_base table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_base (
                article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT,
                tags TEXT,
                author_id INTEGER,
                status TEXT DEFAULT 'draft',
                views INTEGER DEFAULT 0,
                helpful_votes INTEGER DEFAULT 0,
                unhelpful_votes INTEGER DEFAULT 0,
                search_keywords TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (author_id) REFERENCES users (id)
            )
            ''')

            # Create departments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                manager_id INTEGER,
                email TEXT,
                sla_policy_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (manager_id) REFERENCES users (id),
                FOREIGN KEY (sla_policy_id) REFERENCES sla_policies (sla_id)
            )
            ''')

            # Create organizations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                org_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT,
                contact_email TEXT,
                phone TEXT,
                address TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            ''')

            # Create saved_searches table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                search_criteria TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            conn.commit()
            conn.close()
            print("Enhanced helpdesk database initialized successfully!")

            # Initialize default data
            init_default_data()

        except sqlite3.Error as e:
            print(f"An error occurred while initializing the helpdesk database: {e}")

    def setup_enhanced_helpdesk_permissions():
        """
        Setup enhanced helpdesk permissions

        Creates and configures helpdesk-specific permissions in the
        authentication system. This includes permissions for:
        - Creating and managing tickets
        - Knowledge base management
        - SLA and workflow configuration
        - Analytics and reporting
        - Department and organization management

        Permissions are automatically assigned to appropriate roles
        (Student, Staff, Admin) based on typical helpdesk workflows.

        Note: This is a wrapper that calls the actual implementation
        from the services layer. It's provided here for backwards
        compatibility and convenience.
        """
        try:
            # Try to import and call the actual implementation
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk import (
                setup_enhanced_helpdesk_permissions as service_setup_permissions
            )
            service_setup_permissions()
        except ImportError:
            # If service layer is not available, do basic setup
            print("Warning: Helpdesk service layer not available. Setting up basic permissions...")
            try:
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Check if permissions table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permissions'")
                if not cursor.fetchone():
                    print("Permissions table not found. Authentication system must be initialized first.")
                    conn.close()
                    return

                # Add basic helpdesk permissions
                basic_permissions = [
                    ('create_ticket', 'Can create support tickets'),
                    ('view_own_tickets', 'Can view own support tickets'),
                    ('view_all_tickets', 'Can view all support tickets'),
                    ('manage_tickets', 'Can manage ticket status and priority')
                ]

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for perm_name, perm_desc in basic_permissions:
                    cursor.execute(
                        "SELECT COUNT(*) FROM permissions WHERE permission_name = ?",
                        (perm_name,)
                    )
                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)",
                            (perm_name, perm_desc, timestamp)
                        )

                conn.commit()
                conn.close()
                print("Basic helpdesk permissions setup completed")

            except Exception as e:
                print(f"Error setting up basic helpdesk permissions: {e}")
        except Exception as e:
            print(f"Error setting up enhanced helpdesk permissions: {e}")

from education_system.post_18.university_system.modules.domain.student_affairs.gui.helpdesk.base import HelpdeskGUI

def create_knowledge_base_tab(self):
    """Create knowledge base tab"""
    kb_frame = ttk.Frame(self.notebook)
    self.notebook.add(kb_frame, text="Knowledge Base")

    # Toolbar
    toolbar = ttk.Frame(kb_frame)
    toolbar.pack(fill='x', padx=10, pady=5)

    ttk.Button(toolbar, text="Refresh", command=self.refresh_knowledge_base).pack(side='left', padx=5)
    if self.has_permission('manage_tickets'):
        ttk.Button(toolbar, text="Create Article", command=self.show_create_article).pack(side='left', padx=5)

    # Search frame
    search_frame = ttk.Frame(kb_frame)
    search_frame.pack(fill='x', padx=10, pady=5)

    ttk.Label(search_frame, text="Search:").pack(side='left')
    self.kb_search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=self.kb_search_var, width=30)
    search_entry.pack(side='left', padx=5)
    search_entry.bind('<Return>', lambda e: self.search_knowledge_base())
    ttk.Button(search_frame, text="Search", command=self.search_knowledge_base).pack(side='left', padx=5)

    # Category filter
    ttk.Label(search_frame, text="Category:").pack(side='left', padx=(20, 0))
    self.kb_category_var = tk.StringVar(value="all")
    category_combo = ttk.Combobox(search_frame, textvariable=self.kb_category_var,
                                 values=["all"], state="readonly", width=15)
    category_combo.pack(side='left', padx=5)
    category_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_knowledge_base())

    # Articles list
    self.kb_list_frame = ttk.Frame(kb_frame)
    self.kb_list_frame.pack(fill='both', expand=True, padx=10, pady=5)

    self.create_knowledge_base_list()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_knowledge_base_tab = create_knowledge_base_tab

def create_knowledge_base_list(self):
    """Create knowledge base articles list"""
    # Clear existing widgets
    for widget in self.kb_list_frame.winfo_children():
        widget.destroy()

    # Create treeview
    columns = ('ID', 'Title', 'Category', 'Views', 'Rating', 'Updated')
    self.kb_tree = ttk.Treeview(self.kb_list_frame, columns=columns, show='headings')

    # Configure columns
    column_widths = {'ID': 50, 'Title': 300, 'Category': 120, 'Views': 80,
                    'Rating': 100, 'Updated': 120}

    for col in columns:
        self.kb_tree.heading(col, text=col)
        self.kb_tree.column(col, width=column_widths.get(col, 100))

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(self.kb_list_frame, orient='vertical', command=self.kb_tree.yview)
    h_scrollbar = ttk.Scrollbar(self.kb_list_frame, orient='horizontal', command=self.kb_tree.xview)

    self.kb_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack widgets
    self.kb_tree.grid(row=0, column=0, sticky='nsew')
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')

    self.kb_list_frame.grid_rowconfigure(0, weight=1)
    self.kb_list_frame.grid_columnconfigure(0, weight=1)

    # Bind double-click to view article
    self.kb_tree.bind('<Double-1>', self.on_kb_article_double_click)

    # Load data
    self.refresh_knowledge_base()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_knowledge_base_list = create_knowledge_base_list

def refresh_knowledge_base(self):
    """Refresh knowledge base list"""
    try:
        # Clear existing items
        for item in self.kb_tree.get_children():
            self.kb_tree.delete(item)

        # Get articles from database
        articles = self.get_knowledge_base_articles()

        # Update category filter
        categories = ["all"] + list(set(article.get('category', 'Uncategorized') for article in articles))
        # Update combobox values (find the combobox widget)
        for widget in self.kb_list_frame.master.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Combobox) and child.cget('textvariable') == str(self.kb_category_var):
                        child['values'] = categories
                        break

        # Filter articles
        category_filter = self.kb_category_var.get()
        if category_filter != "all":
            articles = [a for a in articles if a.get('category') == category_filter]

        # Populate treeview
        for article in articles:
            # Calculate rating
            helpful = article.get('helpful_votes', 0)
            unhelpful = article.get('unhelpful_votes', 0)
            total_votes = helpful + unhelpful
            rating = f"{helpful}/{total_votes}" if total_votes > 0 else "No votes"

            # Format date
            updated = article.get('updated_at', '')[:16] if article.get('updated_at') else ''

            self.kb_tree.insert('', 'end', values=(
                article.get('article_id', ''),
                article.get('title', '')[:50],
                article.get('category', 'Uncategorized'),
                article.get('views', 0),
                rating,
                updated
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load knowledge base: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.refresh_knowledge_base = refresh_knowledge_base

def get_knowledge_base_articles(self):
    """Get knowledge base articles from database"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT article_id, title, category, views, helpful_votes, unhelpful_votes, updated_at
        FROM knowledge_base
        WHERE status = 'published'
        ORDER BY helpful_votes DESC, views DESC
        ''')

        articles = cursor.fetchall()
        conn.close()

        return [dict(article) for article in articles]

    except Exception:
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_knowledge_base_articles = get_knowledge_base_articles

def search_knowledge_base(self):
    """Search knowledge base articles"""
    search_term = self.kb_search_var.get().strip()
    if not search_term:
        self.refresh_knowledge_base()
        return

    try:
        # Clear existing items
        for item in self.kb_tree.get_children():
            self.kb_tree.delete(item)

        # Search articles
        articles = self.search_kb_articles(search_term)

        # Populate treeview
        for article in articles:
            helpful = article.get('helpful_votes', 0)
            unhelpful = article.get('unhelpful_votes', 0)
            total_votes = helpful + unhelpful
            rating = f"{helpful}/{total_votes}" if total_votes > 0 else "No votes"

            updated = article.get('updated_at', '')[:16] if article.get('updated_at') else ''

            self.kb_tree.insert('', 'end', values=(
                article.get('article_id', ''),
                article.get('title', '')[:50],
                article.get('category', 'Uncategorized'),
                article.get('views', 0),
                rating,
                updated
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Search failed: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.search_knowledge_base = search_knowledge_base

def search_kb_articles(self, search_term):
    """Search knowledge base articles"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT article_id, title, category, views, helpful_votes, unhelpful_votes, updated_at
        FROM knowledge_base
        WHERE status = 'published'
        AND (title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)
        ORDER BY helpful_votes DESC, views DESC
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

        articles = cursor.fetchall()
        conn.close()

        return [dict(article) for article in articles]

    except Exception:
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.search_kb_articles = search_kb_articles

def on_kb_article_double_click(self, event):
    """Handle double-click on knowledge base article"""
    selection = self.kb_tree.selection()
    if not selection:
        return

    item = self.kb_tree.item(selection[0])
    article_id = item['values'][0]

    self.show_kb_article_details(article_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.on_kb_article_double_click = on_kb_article_double_click

def show_kb_article_details(self, article_id):
    """Show knowledge base article details"""
    details_window = tk.Toplevel(self.root)
    details_window.title(f"Knowledge Base Article #{article_id}")
    details_window.geometry("800x600")
    details_window.transient(self.root)

    # Get article data
    article_data = self.get_kb_article_details(article_id)
    if not article_data:
        messagebox.showerror("Error", "Article not found")
        details_window.destroy()
        return

    # Create scrollable frame
    canvas = tk.Canvas(details_window)
    scrollbar = ttk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Article header
    header_frame = ttk.Frame(scrollable_frame)
    header_frame.pack(fill='x', padx=10, pady=10)

    ttk.Label(header_frame, text=article_data.get('title', ''),
             style='Title.TLabel').pack(anchor='w')

    # Article info
    info_frame = ttk.Frame(scrollable_frame)
    info_frame.pack(fill='x', padx=10, pady=5)

    info_text = f"Category: {article_data.get('category', 'Uncategorized')} | "
    info_text += f"Views: {article_data.get('views', 0)} | "
    info_text += f"Updated: {article_data.get('updated_at', '')}"

    ttk.Label(info_frame, text=info_text).pack(anchor='w')

    # Article content
    content_frame = ttk.LabelFrame(scrollable_frame, text="Content")
    content_frame.pack(fill='both', expand=True, padx=10, pady=10)

    content_text = scrolledtext.ScrolledText(content_frame, wrap='word', state='disabled')
    content_text.pack(fill='both', expand=True, padx=5, pady=5)
    content_text.config(state='normal')
    content_text.insert('1.0', article_data.get('content', ''))
    content_text.config(state='disabled')

    # Rating frame
    rating_frame = ttk.LabelFrame(scrollable_frame, text="Rate This Article")
    rating_frame.pack(fill='x', padx=10, pady=10)

    helpful = article_data.get('helpful_votes', 0)
    unhelpful = article_data.get('unhelpful_votes', 0)
    total = helpful + unhelpful

    current_rating = f"Current rating: {helpful} helpful, {unhelpful} not helpful"
    if total > 0:
        current_rating += f" ({helpful/total*100:.1f}% helpful)"

    ttk.Label(rating_frame, text=current_rating).pack(pady=5)

    button_frame = ttk.Frame(rating_frame)
    button_frame.pack(pady=5)

    ttk.Button(button_frame, text="👍 Helpful",
              command=lambda: self.rate_article(article_id, True, details_window)).pack(side='left', padx=5)
    ttk.Button(button_frame, text="👎 Not Helpful",
              command=lambda: self.rate_article(article_id, False, details_window)).pack(side='left', padx=5)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Update view count
    self.update_article_views(article_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_kb_article_details = show_kb_article_details

def get_kb_article_details(self, article_id):
    """Get detailed knowledge base article"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM knowledge_base WHERE article_id = ?
        ''', (article_id,))

        article = cursor.fetchone()
        conn.close()

        return dict(article) if article else None

    except Exception:
        return None

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_kb_article_details = get_kb_article_details

def update_article_views(self, article_id):
    """Update article view count"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE knowledge_base SET views = views + 1 WHERE article_id = ?
        ''', (article_id,))

        conn.commit()
        conn.close()

    except Exception:
        pass

# Attach method to HelpdeskGUI class
HelpdeskGUI.update_article_views = update_article_views

def rate_article(self, article_id, is_helpful, window):
    """Rate knowledge base article"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        if is_helpful:
            cursor.execute('''
            UPDATE knowledge_base SET helpful_votes = helpful_votes + 1 WHERE article_id = ?
            ''', (article_id,))
        else:
            cursor.execute('''
            UPDATE knowledge_base SET unhelpful_votes = unhelpful_votes + 1 WHERE article_id = ?
            ''', (article_id,))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", "Thank you for your feedback!")
        window.destroy()
        self.refresh_knowledge_base()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to rate article: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.rate_article = rate_article

def show_create_article(self):
    """Show create article dialog"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Error", "You don't have permission to create articles")
        return

    create_window = tk.Toplevel(self.root)
    create_window.title("Create Knowledge Base Article")
    create_window.geometry("800x600")
    create_window.transient(self.root)
    create_window.grab_set()

    # Create scrollable frame
    canvas = tk.Canvas(create_window)
    scrollbar = ttk.Scrollbar(create_window, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Title
    ttk.Label(scrollable_frame, text="Create Knowledge Base Article",
             style='Title.TLabel').pack(pady=10)

    # Form
    form_frame = ttk.LabelFrame(scrollable_frame, text="Article Details")
    form_frame.pack(fill='x', padx=10, pady=10)

    # Article title
    ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    title_entry = ttk.Entry(form_frame, width=60)
    title_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)

    # Category
    ttk.Label(form_frame, text="Category:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    category_entry = ttk.Entry(form_frame, width=30)
    category_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=5)

    # Tags
    ttk.Label(form_frame, text="Tags:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
    tags_entry = ttk.Entry(form_frame, width=40)
    tags_entry.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
    ttk.Label(form_frame, text="(comma-separated)").grid(row=2, column=2, sticky='w', padx=5, pady=5)

    form_frame.grid_columnconfigure(1, weight=1)

    # Content
    content_frame = ttk.LabelFrame(scrollable_frame, text="Article Content")
    content_frame.pack(fill='both', expand=True, padx=10, pady=10)

    content_text = scrolledtext.ScrolledText(content_frame, height=15, wrap='word')
    content_text.pack(fill='both', expand=True, padx=5, pady=5)

    # Status
    status_frame = ttk.LabelFrame(scrollable_frame, text="Publication Status")
    status_frame.pack(fill='x', padx=10, pady=10)

    status_var = tk.StringVar(value="draft")
    ttk.Radiobutton(status_frame, text="Save as Draft", variable=status_var,
                   value="draft").pack(anchor='w', padx=5, pady=2)
    ttk.Radiobutton(status_frame, text="Publish Immediately", variable=status_var,
                   value="published").pack(anchor='w', padx=5, pady=2)

    # Buttons
    button_frame = ttk.Frame(scrollable_frame)
    button_frame.pack(fill='x', padx=10, pady=10)

    def create_article():
        title = title_entry.get().strip()
        category = category_entry.get().strip()
        tags = tags_entry.get().strip()
        content = content_text.get('1.0', 'end-1c').strip()
        status = status_var.get()

        if not title or not content:
            messagebox.showerror("Error", "Title and content are required")
            return

        article_data = {
            'title': title,
            'category': category,
            'tags': tags,
            'content': content,
            'status': status
        }

        if self.create_kb_article(article_data):
            messagebox.showinfo("Success", "Article created successfully!")
            create_window.destroy()
            self.refresh_knowledge_base()
        else:
            messagebox.showerror("Error", "Failed to create article")

    ttk.Button(button_frame, text="Create Article", command=create_article,
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=create_window.destroy).pack(side='right')

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_create_article = show_create_article

def create_kb_article(self, article_data):
    """Create knowledge base article"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO knowledge_base
        (title, content, category, tags, author_id, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            article_data['title'],
            article_data['content'],
            article_data['category'],
            article_data['tags'],
            self.current_user.get('id', 0),
            article_data['status'],
            now, now
        ))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        messagebox.showerror("Error", f"Database error: {str(e)}")
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_kb_article = create_kb_article

def show_knowledge_base(self):
    """Switch to knowledge base tab"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'Knowledge Base':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_knowledge_base = show_knowledge_base

def manage_knowledge_base_gui(self):
    """Knowledge base management interface"""
    kb_window = tk.Toplevel(self.root)
    kb_window.title("Knowledge Base Management")
    kb_window.geometry("900x600")

    # Main frame
    main_frame = ttk.Frame(kb_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Toolbar
    toolbar = ttk.Frame(main_frame)
    toolbar.pack(fill=tk.X, pady=5)

    ttk.Button(toolbar, text="View Articles",
              command=lambda: self.view_kb_articles_gui()).pack(side=tk.LEFT, padx=2)

    if self.auth.has_permission('manage_tickets'):
        ttk.Button(toolbar, text="Create Article",
                  command=lambda: self.create_kb_article_gui()).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Article",
                  command=lambda: self.edit_kb_article_gui()).pack(side=tk.LEFT, padx=2)

    if self.auth.has_permission('view_all_tickets'):
        ttk.Button(toolbar, text="Statistics",
                  command=lambda: self.kb_statistics_gui()).pack(side=tk.LEFT, padx=2)

    ttk.Button(toolbar, text="Refresh",
              command=lambda: self.refresh_kb_list(tree)).pack(side=tk.LEFT, padx=2)
    ttk.Button(toolbar, text="Close",
              command=kb_window.destroy).pack(side=tk.RIGHT, padx=2)

    # Articles list
    list_frame = ttk.LabelFrame(main_frame, text="Knowledge Base Articles", padding="10")
    list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

    columns = ('id', 'title', 'category', 'views', 'helpful', 'unhelpful', 'updated')
    tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

    tree.heading('id', text='ID')
    tree.heading('title', text='Title')
    tree.heading('category', text='Category')
    tree.heading('views', text='Views')
    tree.heading('helpful', text='Helpful')
    tree.heading('unhelpful', text='Unhelpful')
    tree.heading('updated', text='Updated')

    tree.column('id', width=40)
    tree.column('title', width=300)
    tree.column('category', width=120)
    tree.column('views', width=60)
    tree.column('helpful', width=60)
    tree.column('unhelpful', width=60)
    tree.column('updated', width=140)

    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Double-click to view details
    tree.bind('<Double-1>', lambda e: self.view_kb_article_detail_gui_from_tree(tree))

    # Initial load
    self.refresh_kb_list(tree)

# Attach method to HelpdeskGUI class
HelpdeskGUI.manage_knowledge_base_gui = manage_knowledge_base_gui

def refresh_kb_list(self, tree):
    """Refresh knowledge base articles list"""
    # Clear existing items
    for item in tree.get_children():
        tree.delete(item)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT article_id, title, category, views, helpful_votes, unhelpful_votes, updated_at
            FROM knowledge_base
            WHERE status = 'published'
            ORDER BY helpful_votes DESC, views DESC
        ''')

        articles = cursor.fetchall()
        conn.close()

        for article in articles:
            tree.insert('', tk.END, values=article)

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load articles: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.refresh_kb_list = refresh_kb_list

def view_kb_articles_gui(self):
    """View knowledge base articles with category filter"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Knowledge Base Articles")
    dialog.geometry("800x600")

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Category filter
    filter_frame = ttk.Frame(main_frame)
    filter_frame.pack(fill=tk.X, pady=5)

    ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=5)

    # Get categories
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT category FROM knowledge_base
            WHERE status = 'published' AND category IS NOT NULL
            ORDER BY category
        ''')
        categories = ['All Categories'] + [row[0] for row in cursor.fetchall()]
        conn.close()

    except sqlite3.Error:
        categories = ['All Categories']

    category_var = tk.StringVar(value='All Categories')
    category_combo = ttk.Combobox(filter_frame, textvariable=category_var,
                                  values=categories, width=30)
    category_combo.pack(side=tk.LEFT, padx=5)

    # Articles list
    columns = ('id', 'title', 'category', 'views', 'rating')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

    tree.heading('id', text='ID')
    tree.heading('title', text='Title')
    tree.heading('category', text='Category')
    tree.heading('views', text='Views')
    tree.heading('rating', text='Rating')

    tree.column('id', width=40)
    tree.column('title', width=400)
    tree.column('category', width=120)
    tree.column('views', width=60)
    tree.column('rating', width=100)

    scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

    def load_articles():
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            where_clause = "WHERE status = 'published'"
            params = []

            if category_var.get() != 'All Categories':
                where_clause += " AND category = ?"
                params.append(category_var.get())

            cursor.execute('''
                SELECT article_id, title, category, views, helpful_votes, unhelpful_votes
                FROM knowledge_base
                ''' + where_clause + '''
                ORDER BY helpful_votes DESC, views DESC
            ''', params)

            articles = cursor.fetchall()
            conn.close()

            for article in articles:
                article_id, title, category, views, helpful, unhelpful = article
                total_votes = helpful + unhelpful
                rating = f"{helpful}/{total_votes}" if total_votes > 0 else "No votes"

                tree.insert('', tk.END, values=(article_id, title, category, views, rating))

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load articles: {e}")

    # Filter button
    ttk.Button(filter_frame, text="Filter", command=load_articles).pack(side=tk.LEFT, padx=5)

    # View detail button
    ttk.Button(main_frame, text="View Details",
              command=lambda: self.view_kb_article_detail_gui_from_tree(tree)).pack(pady=5)
    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=5)

    # Double-click to view
    tree.bind('<Double-1>', lambda e: self.view_kb_article_detail_gui_from_tree(tree))

    # Initial load
    load_articles()

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_kb_articles_gui = view_kb_articles_gui

def view_kb_article_detail_gui_from_tree(self, tree):
    """View KB article detail from tree selection"""
    selection = tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select an article to view.")
        return

    item = tree.item(selection[0])
    article_id = item['values'][0]
    self.view_kb_article_detail_gui(article_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_kb_article_detail_gui_from_tree = view_kb_article_detail_gui_from_tree

def view_kb_article_detail_gui(self, article_id):
    """View detailed knowledge base article"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT kb.*, u.username as author
            FROM knowledge_base kb
            LEFT JOIN users u ON kb.author_id = u.id
            WHERE kb.article_id = ?
        ''', (article_id,))

        article = cursor.fetchone()

        if not article:
            messagebox.showerror("Not Found", "Article not found.")
            conn.close()
            return

        # Update view count
        cursor.execute('''
            UPDATE knowledge_base SET views = views + 1 WHERE article_id = ?
        ''', (article_id,))
        conn.commit()
        conn.close()

        # Create detail window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Article #{article[0]}: {article[1]}")
        detail_window.geometry("700x600")

        main_frame = ttk.Frame(detail_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header info
        info_frame = ttk.LabelFrame(main_frame, text="Article Information", padding="10")
        info_frame.pack(fill=tk.X, pady=5)

        ttk.Label(info_frame, text=f"Title: {article[1]}", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Category: {article[3] or 'Uncategorized'}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Author: {article[-1] or 'Unknown'}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Status: {article[6]}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Views: {article[7]}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Helpful votes: {article[8]} | Unhelpful votes: {article[9]}").pack(anchor=tk.W)

        if article[4]:  # tags
            ttk.Label(info_frame, text=f"Tags: {article[4]}").pack(anchor=tk.W)

        ttk.Label(info_frame, text=f"Created: {article[11]}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Updated: {article[12]}").pack(anchor=tk.W)

        # Content
        content_frame = ttk.LabelFrame(main_frame, text="Content", padding="10")
        content_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, height=20)
        content_text.pack(fill=tk.BOTH, expand=True)
        content_text.insert('1.0', article[2])  # content
        content_text.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=detail_window.destroy).pack(pady=5)

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load article: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_kb_article_detail_gui = view_kb_article_detail_gui

def create_kb_article_gui(self):
    """Create a new knowledge base article"""
    if not self.auth.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to create articles.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("Create Knowledge Base Article")
    dialog.geometry("700x600")

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(main_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
    title_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=title_var, width=60).grid(row=0, column=1, pady=5, padx=5)

    # Category
    ttk.Label(main_frame, text="Category:").grid(row=1, column=0, sticky=tk.W, pady=5)
    category_var = tk.StringVar()
    categories = ["Technical Support", "Academic Inquiry", "Financial Services", "Account Access", "Other"]
    ttk.Combobox(main_frame, textvariable=category_var, values=categories, width=57).grid(row=1, column=1, pady=5, padx=5)

    # Tags
    ttk.Label(main_frame, text="Tags (comma-separated):").grid(row=2, column=0, sticky=tk.W, pady=5)
    tags_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=tags_var, width=60).grid(row=2, column=1, pady=5, padx=5)

    # Content
    ttk.Label(main_frame, text="Content:").grid(row=3, column=0, sticky=tk.NW, pady=5)
    content_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=60, height=20)
    content_text.grid(row=3, column=1, pady=5, padx=5)

    def save_article():
        title = title_var.get().strip()
        category = category_var.get().strip()
        tags = tags_var.get().strip()
        content = content_text.get('1.0', tk.END).strip()

        if not title or not content:
            messagebox.showerror("Validation Error", "Title and content are required.")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            author_id = self.auth.current_user['id']

            cursor.execute('''
                INSERT INTO knowledge_base
                (title, content, category, tags, author_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'published', ?, ?)
            ''', (title, content, category, tags, author_id, now, now))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Knowledge base article created successfully!")
            dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to create article: {e}")

    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.grid(row=4, column=0, columnspan=2, pady=10)

    ttk.Button(btn_frame, text="Save", command=save_article).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_kb_article_gui = create_kb_article_gui

def edit_kb_article_gui(self):
    """Edit an existing knowledge base article"""
    if not self.auth.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to edit articles.")
        return

    # Ask for article ID
    article_id = simpledialog.askinteger("Edit Article", "Enter article ID to edit:")
    if not article_id:
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM knowledge_base WHERE article_id = ?', (article_id,))
        article = cursor.fetchone()

        if not article:
            messagebox.showerror("Not Found", "Article not found.")
            conn.close()
            return

        # Check permissions
        if article[5] != self.auth.current_user['id'] and not self.auth.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to edit this article.")
            conn.close()
            return

        conn.close()

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Article #{article_id}")
        dialog.geometry("700x600")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
        title_var = tk.StringVar(value=article[1])
        ttk.Entry(main_frame, textvariable=title_var, width=60).grid(row=0, column=1, pady=5, padx=5)

        # Category
        ttk.Label(main_frame, text="Category:").grid(row=1, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar(value=article[3] or '')
        categories = ["Technical Support", "Academic Inquiry", "Financial Services", "Account Access", "Other"]
        ttk.Combobox(main_frame, textvariable=category_var, values=categories, width=57).grid(row=1, column=1, pady=5, padx=5)

        # Tags
        ttk.Label(main_frame, text="Tags:").grid(row=2, column=0, sticky=tk.W, pady=5)
        tags_var = tk.StringVar(value=article[4] or '')
        ttk.Entry(main_frame, textvariable=tags_var, width=60).grid(row=2, column=1, pady=5, padx=5)

        # Content
        ttk.Label(main_frame, text="Content:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        content_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=60, height=20)
        content_text.grid(row=3, column=1, pady=5, padx=5)
        content_text.insert('1.0', article[2])

        def save_changes():
            new_title = title_var.get().strip()
            new_category = category_var.get().strip()
            new_tags = tags_var.get().strip()
            new_content = content_text.get('1.0', tk.END).strip()

            if not new_title or not new_content:
                messagebox.showerror("Validation Error", "Title and content are required.")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    UPDATE knowledge_base
                    SET title = ?, content = ?, category = ?, tags = ?, updated_at = ?
                    WHERE article_id = ?
                ''', (new_title, new_content, new_category, new_tags, now, article_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Article updated successfully!")
                dialog.destroy()

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to update article: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="Save", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load article: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_kb_article_gui = edit_kb_article_gui

def kb_statistics_gui(self):
    """Display knowledge base statistics"""
    if not self.auth.has_permission('view_all_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to view statistics.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get statistics
        cursor.execute('SELECT COUNT(*) FROM knowledge_base WHERE status = "published"')
        total_articles = cursor.fetchone()[0]

        cursor.execute('''
            SELECT title, views FROM knowledge_base
            WHERE status = 'published'
            ORDER BY views DESC
            LIMIT 5
        ''')
        top_viewed = cursor.fetchall()

        cursor.execute('''
            SELECT title, helpful_votes, unhelpful_votes
            FROM knowledge_base
            WHERE status = 'published' AND (helpful_votes + unhelpful_votes) > 0
            ORDER BY (helpful_votes * 1.0 / (helpful_votes + unhelpful_votes)) DESC
            LIMIT 5
        ''')
        top_helpful = cursor.fetchall()

        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM knowledge_base
            WHERE status = 'published'
            GROUP BY category
            ORDER BY count DESC
        ''')
        categories = cursor.fetchall()

        conn.close()

        # Create statistics window
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Knowledge Base Statistics")
        stats_window.geometry("600x500")

        main_frame = ttk.Frame(stats_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Total articles
        ttk.Label(main_frame, text=f"Total Published Articles: {total_articles}",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=10)

        # Most viewed
        viewed_frame = ttk.LabelFrame(main_frame, text="Most Viewed Articles", padding="10")
        viewed_frame.pack(fill=tk.X, pady=5)

        for title, views in top_viewed:
            ttk.Label(viewed_frame, text=f"{title[:50]}: {views} views").pack(anchor=tk.W)

        # Most helpful
        helpful_frame = ttk.LabelFrame(main_frame, text="Most Helpful Articles", padding="10")
        helpful_frame.pack(fill=tk.X, pady=5)

        for title, helpful, unhelpful in top_helpful:
            total_votes = helpful + unhelpful
            helpfulness = (helpful / total_votes * 100) if total_votes > 0 else 0
            ttk.Label(helpful_frame, text=f"{title[:50]}: {helpfulness:.1f}% helpful ({total_votes} votes)").pack(anchor=tk.W)

        # Categories
        cat_frame = ttk.LabelFrame(main_frame, text="Articles by Category", padding="10")
        cat_frame.pack(fill=tk.X, pady=5)

        for category, count in categories:
            ttk.Label(cat_frame, text=f"{category or 'Uncategorized'}: {count}").pack(anchor=tk.W)

        ttk.Button(main_frame, text="Close", command=stats_window.destroy).pack(pady=10)

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load statistics: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.kb_statistics_gui = kb_statistics_gui

def display_kb_suggestions_gui(self, ticket):
    """Display knowledge base article suggestions for a ticket"""
    if not ticket or not ticket.get('knowledge_base_articles'):
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        article_ids = ticket['knowledge_base_articles'].split(',')
        placeholders = ','.join(['?' for _ in article_ids])

        cursor.execute('''
            SELECT article_id, title, category, helpful_votes, unhelpful_votes
            FROM knowledge_base
            WHERE article_id IN (''' + placeholders + ''') AND status = 'published'
        ''', article_ids)

        articles = cursor.fetchall()
        conn.close()

        if not articles:
            return

        # Create suggestions window
        suggest_window = tk.Toplevel(self.root)
        suggest_window.title("Suggested Knowledge Base Articles")
        suggest_window.geometry("600x400")

        main_frame = ttk.Frame(suggest_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Suggested Articles That Might Help:",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=10)

        # Article list
        for article in articles:
            article_id, title, category, helpful, unhelpful = article
            total_votes = helpful + unhelpful
            helpful_ratio = (helpful / total_votes * 100) if total_votes > 0 else 0

            article_frame = ttk.Frame(main_frame)
            article_frame.pack(fill=tk.X, pady=5)

            ttk.Label(article_frame, text=f"• {title}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
            ttk.Label(article_frame, text=f"  Category: {category} - {helpful_ratio:.0f}% helpful").pack(anchor=tk.W)

            ttk.Button(article_frame, text="View Article",
                      command=lambda aid=article_id: self.view_kb_article_detail_gui(aid)).pack(anchor=tk.W, padx=20)

        ttk.Button(main_frame, text="Close", command=suggest_window.destroy).pack(pady=10)

    except sqlite3.Error as e:
        print(f"Error loading KB suggestions: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_kb_suggestions_gui = display_kb_suggestions_gui

def suggest_knowledge_base_articles_gui(self, ticket_id, content):
    """Suggest relevant knowledge base articles based on ticket content"""
    try:
        # Extract keywords
        keywords = self.extract_keywords_gui(content.lower())

        if not keywords:
            return

        conn = get_connection()
        cursor = conn.cursor()

        # Search for articles with matching keywords
        keyword_conditions = []
        params = []

        for keyword in keywords[:5]:  # Limit to top 5 keywords
            keyword_conditions.append("(title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)")
            params.extend([f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%"])

        if keyword_conditions:
            query = f'''
                SELECT article_id, title, category
                FROM knowledge_base
                WHERE status = 'published' AND ({" OR ".join(keyword_conditions)})
                ORDER BY helpful_votes DESC, views DESC
                LIMIT 3
            '''

            cursor.execute(query, params)
            articles = cursor.fetchall()

            if articles:
                # Store suggestions in ticket
                article_ids = [str(a[0]) for a in articles]
                cursor.execute('''
                    UPDATE support_tickets
                    SET knowledge_base_articles = ?
                    WHERE ticket_id = ?
                ''', (','.join(article_ids), ticket_id))

                conn.commit()

        conn.close()

    except sqlite3.Error as e:
        print(f"Error suggesting KB articles: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.suggest_knowledge_base_articles_gui = suggest_knowledge_base_articles_gui

def extract_keywords_gui(self, text):
    """Extract relevant keywords from text"""
    # Remove common words and extract meaningful terms
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
                  'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                  'may', 'might', 'can', 'cant', 'cannot', 'i', 'you', 'he', 'she', 'it',
                  'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his',
                  'her', 'its', 'our', 'their'}

    # Simple word extraction
    import re
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    keywords = [word for word in words if word.lower() not in stop_words]

    # Return most frequent keywords
    from collections import Counter
    word_counts = Counter(keywords)
    return [word for word, count in word_counts.most_common(10)]

# Attach method to HelpdeskGUI class
HelpdeskGUI.extract_keywords_gui = extract_keywords_gui

