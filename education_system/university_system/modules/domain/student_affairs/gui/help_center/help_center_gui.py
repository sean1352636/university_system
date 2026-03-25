"""Integrated Help Center (Feature 42).

Provides students with support ticket management, a searchable knowledge
base, FAQ browsing, and a feedback submission form.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class HelpCenterGUI:
    """Toplevel window for the integrated student help center."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = (
            auth.current_user.get("username", "") if auth and auth.current_user else ""
        )

        self.window = tk.Toplevel(parent)
        self.window.title("Help Center")
        self.window.geometry("950x650")
        self.window.minsize(750, 500)

        if not self.student_id:
            messagebox.showerror(
                "Error",
                "You must be logged in to access the Help Center.",
                parent=self.window,
            )
            self.window.destroy()
            return

        self._ensure_tables()
        self._build_ui()
        logger.info("HelpCenterGUI opened for student %s", self.student_id)

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        """Create tables that may not yet exist."""
        try:
            with transaction() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS knowledge_base ("
                    "article_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "title TEXT, "
                    "content TEXT, "
                    "category TEXT, "
                    "tags TEXT, "
                    "author_id INTEGER, "
                    "status TEXT DEFAULT 'published', "
                    "views INTEGER DEFAULT 0, "
                    "helpful_votes INTEGER DEFAULT 0, "
                    "unhelpful_votes INTEGER DEFAULT 0, "
                    "search_keywords TEXT, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS user_feedback ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "student_id TEXT, "
                    "rating INTEGER, "
                    "comment TEXT, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                )
        except Exception as exc:
            logger.warning("Could not ensure help-center tables: %s", exc)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Create the four-tab notebook."""
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1 - My Tickets
        self.tickets_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tickets_frame, text="My Tickets")
        self._build_tickets_tab()

        # Tab 2 - Knowledge Base
        self.kb_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.kb_frame, text="Knowledge Base")
        self._build_kb_tab()

        # Tab 3 - FAQ
        self.faq_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.faq_frame, text="FAQ")
        self._build_faq_tab()

        # Tab 4 - Feedback
        self.feedback_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.feedback_frame, text="Feedback")
        self._build_feedback_tab()

    # ------------------------------------------------------------------
    # Tab 1 - My Tickets
    # ------------------------------------------------------------------

    def _build_tickets_tab(self):
        """Build the support ticket listing and creation UI."""
        btn_frame = ttk.Frame(self.tickets_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Button(btn_frame, text="Create Ticket", command=self._open_create_ticket_dialog).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_frame, text="Refresh", command=self._load_tickets).pack(
            side=tk.LEFT, padx=(10, 0)
        )

        columns = ("ticket_id", "subject", "category", "priority", "status", "created_datetime")
        tree_frame = ttk.Frame(self.tickets_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        self.ticket_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.ticket_tree.yview)

        self.ticket_tree.heading("ticket_id", text="ID")
        self.ticket_tree.heading("subject", text="Subject")
        self.ticket_tree.heading("category", text="Category")
        self.ticket_tree.heading("priority", text="Priority")
        self.ticket_tree.heading("status", text="Status")
        self.ticket_tree.heading("created_datetime", text="Created")

        self.ticket_tree.column("ticket_id", width=50, anchor="center")
        self.ticket_tree.column("subject", width=250)
        self.ticket_tree.column("category", width=110, anchor="center")
        self.ticket_tree.column("priority", width=80, anchor="center")
        self.ticket_tree.column("status", width=90, anchor="center")
        self.ticket_tree.column("created_datetime", width=150, anchor="center")

        self.ticket_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_tickets()

    def _load_tickets(self):
        """Populate the ticket treeview from the database."""
        for item in self.ticket_tree.get_children():
            self.ticket_tree.delete(item)

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT ticket_id, subject, category, priority, status, created_datetime "
                    "FROM support_tickets "
                    "WHERE student_id = ? "
                    "ORDER BY created_datetime DESC",
                    (self.student_id,),
                ).fetchall()

            for row in rows:
                self.ticket_tree.insert(
                    "",
                    tk.END,
                    values=(
                        row[0] if row[0] else "",
                        row[1] if row[1] else "",
                        row[2] if row[2] else "",
                        row[3] if row[3] else "",
                        row[4] if row[4] else "",
                        row[5] if row[5] else "",
                    ),
                )

            if not rows:
                self.ticket_tree.insert(
                    "", tk.END, values=("", "No tickets found.", "", "", "", "")
                )

        except Exception as exc:
            logger.warning("Could not load tickets: %s", exc)
            self.ticket_tree.insert(
                "", tk.END, values=("", "Unable to load tickets.", "", "", "", "")
            )

    def _open_create_ticket_dialog(self):
        """Open a dialog for creating a new support ticket."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Support Ticket")
        dialog.geometry("500x420")
        dialog.transient(self.window)
        dialog.grab_set()

        pad = {"padx": 10, "pady": 5}

        ttk.Label(dialog, text="Subject:").pack(anchor="w", **pad)
        subject_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=subject_var, width=60).pack(fill=tk.X, **pad)

        ttk.Label(dialog, text="Category:").pack(anchor="w", **pad)
        category_var = tk.StringVar(value="General")
        ttk.Combobox(
            dialog,
            textvariable=category_var,
            values=["Technical", "Academic", "Financial", "General"],
            state="readonly",
            width=30,
        ).pack(anchor="w", **pad)

        ttk.Label(dialog, text="Priority:").pack(anchor="w", **pad)
        priority_var = tk.StringVar(value="medium")
        ttk.Combobox(
            dialog,
            textvariable=priority_var,
            values=["low", "medium", "high"],
            state="readonly",
            width=30,
        ).pack(anchor="w", **pad)

        ttk.Label(dialog, text="Description:").pack(anchor="w", **pad)
        desc_text = scrolledtext.ScrolledText(dialog, height=8, width=60)
        desc_text.pack(fill=tk.BOTH, expand=True, **pad)

        def _submit():
            subject = subject_var.get().strip()
            category = category_var.get()
            priority = priority_var.get()
            description = desc_text.get("1.0", tk.END).strip()

            if not subject:
                messagebox.showwarning("Validation", "Subject is required.", parent=dialog)
                return

            try:
                with transaction() as conn:
                    conn.execute(
                        "INSERT INTO support_tickets "
                        "(student_id, title, subject, category, priority, description, status, created_datetime) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'open', datetime('now'))",
                        (self.student_id, subject, subject, category, priority, description),
                    )
                uid = self.auth.current_user.get('id', '') if self.auth and self.auth.current_user else ''
                log_activity(
                    uid,
                    self.student_id,
                    "student",
                    "create_ticket",
                    "help_center",
                    details=f"Created ticket: {subject}",
                )
                messagebox.showinfo("Success", "Ticket created successfully.", parent=dialog)
                dialog.destroy()
                self._load_tickets()
            except Exception as exc:
                logger.error("Failed to create ticket: %s", exc)
                messagebox.showerror(
                    "Error", f"Could not create ticket: {exc}", parent=dialog
                )

        ttk.Button(dialog, text="Submit", command=_submit).pack(pady=10)

    # ------------------------------------------------------------------
    # Tab 2 - Knowledge Base
    # ------------------------------------------------------------------

    def _build_kb_tab(self):
        """Build the knowledge base search and viewer."""
        search_frame = ttk.Frame(self.kb_frame)
        search_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.kb_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.kb_search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(0, 5))
        search_entry.bind("<Return>", lambda _e: self._search_kb())
        ttk.Button(search_frame, text="Search", command=self._search_kb).pack(side=tk.LEFT)

        # Results treeview
        columns = ("title", "category", "created_at")
        tree_frame = ttk.Frame(self.kb_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        self.kb_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=8,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.kb_tree.yview)

        self.kb_tree.heading("title", text="Title")
        self.kb_tree.heading("category", text="Category")
        self.kb_tree.heading("created_at", text="Created")

        self.kb_tree.column("title", width=350)
        self.kb_tree.column("category", width=150, anchor="center")
        self.kb_tree.column("created_at", width=150, anchor="center")

        self.kb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.kb_tree.bind("<<TreeviewSelect>>", self._on_kb_select)

        # Content viewer
        self.kb_content = scrolledtext.ScrolledText(self.kb_frame, height=8, state=tk.DISABLED)
        self.kb_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Store article data for selection lookup
        self._kb_articles = {}

        # Initial load (all articles)
        self._search_kb()

    def _search_kb(self):
        """Search the knowledge base and populate results."""
        for item in self.kb_tree.get_children():
            self.kb_tree.delete(item)
        self._kb_articles.clear()

        query_text = self.kb_search_var.get().strip()
        search_pattern = f"%{escape_like(query_text)}%"

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT article_id, title, category, content, created_at "
                    "FROM knowledge_base "
                    "WHERE title LIKE ? OR content LIKE ? "
                    "ORDER BY created_at DESC",
                    (search_pattern, search_pattern),
                ).fetchall()

            for row in rows:
                article_id = row[0]
                title = row[1] if row[1] else ""
                category = row[2] if row[2] else ""
                content = row[3] if row[3] else ""
                created_at = row[4] if row[4] else ""

                iid = self.kb_tree.insert(
                    "", tk.END, values=(title, category, created_at)
                )
                self._kb_articles[iid] = content

            if not rows:
                self.kb_tree.insert("", tk.END, values=("No articles found.", "", ""))

        except Exception as exc:
            logger.warning("Knowledge base search failed: %s", exc)
            self.kb_tree.insert("", tk.END, values=("Could not load articles.", "", ""))

        # Clear content viewer
        self.kb_content.config(state=tk.NORMAL)
        self.kb_content.delete("1.0", tk.END)
        self.kb_content.config(state=tk.DISABLED)

    def _on_kb_select(self, _event=None):
        """Display the selected knowledge base article content."""
        selection = self.kb_tree.selection()
        if not selection:
            return

        iid = selection[0]
        content = self._kb_articles.get(iid, "")

        self.kb_content.config(state=tk.NORMAL)
        self.kb_content.delete("1.0", tk.END)
        self.kb_content.insert("1.0", content)
        self.kb_content.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Tab 3 - FAQ
    # ------------------------------------------------------------------

    def _build_faq_tab(self):
        """Build the FAQ tab (knowledge base articles where category = 'faq')."""
        columns = ("title", "category", "created_at")
        tree_frame = ttk.Frame(self.faq_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        self.faq_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=8,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.faq_tree.yview)

        self.faq_tree.heading("title", text="Question")
        self.faq_tree.heading("category", text="Category")
        self.faq_tree.heading("created_at", text="Created")

        self.faq_tree.column("title", width=400)
        self.faq_tree.column("category", width=150, anchor="center")
        self.faq_tree.column("created_at", width=150, anchor="center")

        self.faq_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.faq_tree.bind("<<TreeviewSelect>>", self._on_faq_select)

        # Content viewer
        self.faq_content = scrolledtext.ScrolledText(self.faq_frame, height=8, state=tk.DISABLED)
        self.faq_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._faq_articles = {}
        self._load_faq()

    def _load_faq(self):
        """Load FAQ entries from the knowledge base."""
        for item in self.faq_tree.get_children():
            self.faq_tree.delete(item)
        self._faq_articles.clear()

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT article_id, title, category, content, created_at "
                    "FROM knowledge_base "
                    "WHERE LOWER(category) = 'faq' "
                    "ORDER BY created_at DESC",
                ).fetchall()

            for row in rows:
                title = row[1] if row[1] else ""
                category = row[2] if row[2] else ""
                content = row[3] if row[3] else ""
                created_at = row[4] if row[4] else ""

                iid = self.faq_tree.insert("", tk.END, values=(title, category, created_at))
                self._faq_articles[iid] = content

            if not rows:
                self.faq_tree.insert("", tk.END, values=("No FAQs available.", "", ""))

        except Exception as exc:
            logger.warning("FAQ load failed: %s", exc)
            self.faq_tree.insert("", tk.END, values=("Could not load FAQs.", "", ""))

    def _on_faq_select(self, _event=None):
        """Display the selected FAQ content."""
        selection = self.faq_tree.selection()
        if not selection:
            return

        iid = selection[0]
        content = self._faq_articles.get(iid, "")

        self.faq_content.config(state=tk.NORMAL)
        self.faq_content.delete("1.0", tk.END)
        self.faq_content.insert("1.0", content)
        self.faq_content.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Tab 4 - Feedback
    # ------------------------------------------------------------------

    def _build_feedback_tab(self):
        """Build the feedback submission form."""
        container = ttk.Frame(self.feedback_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(
            container,
            text="How would you rate your experience?",
            font=("Helvetica", 14),
        ).pack(anchor="w", pady=(0, 10))

        # Rating radio buttons (1-5)
        self.rating_var = tk.IntVar(value=0)
        rating_frame = ttk.Frame(container)
        rating_frame.pack(anchor="w", pady=(0, 15))

        for i in range(1, 6):
            ttk.Radiobutton(
                rating_frame,
                text=f"{i} Star{'s' if i > 1 else ''}",
                variable=self.rating_var,
                value=i,
            ).pack(side=tk.LEFT, padx=(0, 15))

        # Comment
        ttk.Label(container, text="Comments:").pack(anchor="w", pady=(0, 5))
        self.feedback_text = scrolledtext.ScrolledText(container, height=10, width=70)
        self.feedback_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        ttk.Button(container, text="Submit Feedback", command=self._submit_feedback).pack(
            anchor="e"
        )

    def _submit_feedback(self):
        """Insert feedback into the database."""
        rating = self.rating_var.get()
        comment = self.feedback_text.get("1.0", tk.END).strip()

        if rating == 0:
            messagebox.showwarning(
                "Validation", "Please select a rating.", parent=self.window
            )
            return

        try:
            with transaction() as conn:
                conn.execute(
                    "INSERT INTO user_feedback (student_id, rating, comment, created_at) "
                    "VALUES (?, ?, ?, datetime('now'))",
                    (self.student_id, rating, comment),
                )
            uid = self.auth.current_user.get('id', '') if self.auth and self.auth.current_user else ''
            log_activity(
                uid,
                self.student_id,
                "student",
                "submit_feedback",
                "help_center",
                details=f"Submitted feedback with rating {rating}",
            )
            messagebox.showinfo(
                "Thank You", "Your feedback has been submitted.", parent=self.window
            )
            # Reset form
            self.rating_var.set(0)
            self.feedback_text.delete("1.0", tk.END)

        except Exception as exc:
            logger.error("Failed to submit feedback: %s", exc)
            messagebox.showerror(
                "Error", f"Could not submit feedback: {exc}", parent=self.window
            )
