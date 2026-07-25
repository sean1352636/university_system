"""
Admin Tools GUI Module

Provides administrative tools interface including:
- Document workflow and approvals
- Interdepartmental request system
- Key/access card management
- Visitor management system
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
import json
import os

try:
    from education_system.systems.university.infrastructure.database.db import get_connection, transaction
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    from education_system.systems.university.infrastructure import paths
except ImportError:
    from infrastructure.database.db import get_connection, transaction
    from core.activity_logger import log_activity
    from core import paths

from education_system.systems.university.infrastructure.sql_safety import escape_like


class AdminToolsGUI:
    """Administrative tools GUI with document approvals, requests, keys, and visitors."""

    def __init__(self, root, auth, parent_notebook=None):
        """Initialize the Admin Tools GUI.

        Args:
            root: The root Tkinter window
            auth: Authentication instance
            parent_notebook: Optional parent notebook to embed in
        """
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth else None

        if parent_notebook:
            self.tab = ttk.Frame(parent_notebook)
            parent_notebook.add(self.tab, text="Admin Tools")
            self._create_content(self.tab)
        else:
            self.root.title("Administrative Tools")
            self.root.geometry("1400x800")
            self._create_content(self.root)

    def _create_content(self, parent):
        """Create the main content with tabbed interface."""
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_document_approvals_tab()
        self._create_requests_tab()
        self._create_keys_access_tab()
        self._create_visitors_tab()

    # =========================================================================
    # Document Approvals Tab
    # =========================================================================
    def _create_document_approvals_tab(self):
        """Create document approvals tab."""
        self.doc_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.doc_tab, text="Document Approvals")

        main_paned = ttk.PanedWindow(self.doc_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Document list
        list_label = ttk.LabelFrame(left_frame, text="Document Approval Requests")
        list_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter frame
        filter_frame = ttk.Frame(list_label)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT)
        self.doc_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "pending", "in_review", "approved", "rejected"
        ], state="readonly", width=15)
        self.doc_status_filter.set("pending")
        self.doc_status_filter.pack(side=tk.LEFT, padx=5)
        self.doc_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_document_approvals())

        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT, padx=(15, 0))
        self.doc_type_filter = ttk.Combobox(filter_frame, values=[
            "All", "policy", "budget", "contract", "report", "proposal", "memo", "other"
        ], state="readonly", width=15)
        self.doc_type_filter.set("All")
        self.doc_type_filter.pack(side=tk.LEFT, padx=5)
        self.doc_type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_document_approvals())

        ttk.Button(filter_frame, text="Refresh", command=self._load_document_approvals).pack(side=tk.RIGHT)

        # Treeview
        columns = ("id", "title", "type", "submitted_by", "date", "step", "status")
        self.doc_tree = ttk.Treeview(list_label, columns=columns, show="headings", height=15)

        self.doc_tree.heading("id", text="ID")
        self.doc_tree.heading("title", text="Document Title")
        self.doc_tree.heading("type", text="Type")
        self.doc_tree.heading("submitted_by", text="Submitted By")
        self.doc_tree.heading("date", text="Date")
        self.doc_tree.heading("step", text="Step")
        self.doc_tree.heading("status", text="Status")

        self.doc_tree.column("id", width=50)
        self.doc_tree.column("title", width=200)
        self.doc_tree.column("type", width=100)
        self.doc_tree.column("submitted_by", width=120)
        self.doc_tree.column("date", width=100)
        self.doc_tree.column("step", width=60)
        self.doc_tree.column("status", width=100)

        scrollbar = ttk.Scrollbar(list_label, orient=tk.VERTICAL, command=self.doc_tree.yview)
        self.doc_tree.configure(yscrollcommand=scrollbar.set)

        self.doc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.doc_tree.bind("<<TreeviewSelect>>", self._on_doc_select)

        # Tag colors
        self.doc_tree.tag_configure("pending", background="#fff3cd")
        self.doc_tree.tag_configure("in_review", background="#cfe2ff")
        self.doc_tree.tag_configure("approved", background="#d1e7dd")
        self.doc_tree.tag_configure("rejected", background="#f8d7da")

        # Button frame
        btn_frame = ttk.Frame(list_label)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Submit New Document", command=self._submit_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="View Document", command=self._view_document).pack(side=tk.LEFT, padx=2)

        # Right: Document details and approval
        detail_frame = ttk.LabelFrame(right_frame, text="Document Details")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.doc_detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=15)
        self.doc_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.doc_detail_text.config(state=tk.DISABLED)

        # Approval actions
        action_frame = ttk.LabelFrame(right_frame, text="Approval Actions")
        action_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(action_frame, text="Comments:").pack(anchor=tk.W, padx=5, pady=2)
        self.approval_comments = tk.Text(action_frame, height=4)
        self.approval_comments.pack(fill=tk.X, padx=5, pady=2)

        btn_action_frame = ttk.Frame(action_frame)
        btn_action_frame.pack(fill=tk.X, padx=5, pady=5)

        self.approve_btn = ttk.Button(btn_action_frame, text="Approve", command=lambda: self._process_approval("approved"))
        self.approve_btn.pack(side=tk.LEFT, padx=2)

        self.reject_btn = ttk.Button(btn_action_frame, text="Reject", command=lambda: self._process_approval("rejected"))
        self.reject_btn.pack(side=tk.LEFT, padx=2)

        self.forward_btn = ttk.Button(btn_action_frame, text="Forward to Next", command=self._forward_approval)
        self.forward_btn.pack(side=tk.LEFT, padx=2)

        # History
        history_frame = ttk.LabelFrame(right_frame, text="Approval History")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.history_tree = ttk.Treeview(history_frame, columns=("date", "action", "by", "comments"), show="headings", height=5)
        self.history_tree.heading("date", text="Date")
        self.history_tree.heading("action", text="Action")
        self.history_tree.heading("by", text="By")
        self.history_tree.heading("comments", text="Comments")

        self.history_tree.column("date", width=100)
        self.history_tree.column("action", width=80)
        self.history_tree.column("by", width=100)
        self.history_tree.column("comments", width=150)

        self.history_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._load_document_approvals()

    def _load_document_approvals(self):
        """Load document approvals from database."""
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)

        status_filter = self.doc_status_filter.get()
        type_filter = self.doc_type_filter.get()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM document_approvals WHERE 1=1"
                params = []

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                if type_filter != "All":
                    query += " AND document_type = ?"
                    params.append(type_filter)

                query += " ORDER BY submitted_date DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()

                for row in rows:
                    values = (
                        row[0],  # approval_id
                        row[2] or "Untitled",  # document_title
                        row[1] or "",  # document_type
                        row[4] or "",  # submitted_by
                        row[5][:10] if row[5] else "",  # submitted_date
                        f"{row[7] or 1}",  # current_step
                        row[8] or "pending"  # status
                    )
                    status = row[8] or "pending"
                    self.doc_tree.insert("", tk.END, values=values, tags=(status,))

        except Exception:
            pass  # Table may not exist yet

    def _on_doc_select(self, event):
        """Handle document selection."""
        selected = self.doc_tree.selection()
        if not selected:
            return

        item = self.doc_tree.item(selected[0])
        doc_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM document_approvals WHERE approval_id = ?", (doc_id,))
                row = cursor.fetchone()

                if row:
                    self.doc_detail_text.config(state=tk.NORMAL)
                    self.doc_detail_text.delete(1.0, tk.END)

                    details = f"""Document ID: {row[0]}
Type: {row[1]}
Title: {row[2]}
File Path: {row[3] or 'N/A'}

Submitted By: {row[4]}
Submitted Date: {row[5]}

Current Approver: {row[6] or 'N/A'}
Current Step: {row[7]}
Status: {row[8]}

Approval Chain: {row[9] or 'N/A'}
Comments: {row[10] or 'None'}
"""
                    self.doc_detail_text.insert(1.0, details)
                    self.doc_detail_text.config(state=tk.DISABLED)

                    # Load history
                    self._load_approval_history(doc_id)

        except Exception:
            pass

    def _load_approval_history(self, doc_id):
        """Load approval history for a document."""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT action_date, action, action_by, comments
                    FROM document_approval_history
                    WHERE approval_id = ?
                    ORDER BY action_date DESC
                """, (doc_id,))

                for row in cursor.fetchall():
                    values = (
                        row[0][:16] if row[0] else "",
                        row[1] or "",
                        row[2] or "",
                        row[3] or ""
                    )
                    self.history_tree.insert("", tk.END, values=values)
        except Exception:
            pass

    def _submit_document(self):
        """Submit a new document for approval."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Submit Document for Approval")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Document Type:").pack(anchor=tk.W, padx=10, pady=5)
        doc_type = ttk.Combobox(dialog, values=[
            "policy", "budget", "contract", "report", "proposal", "memo", "other"
        ], state="readonly")
        doc_type.pack(fill=tk.X, padx=10)
        doc_type.set("memo")

        ttk.Label(dialog, text="Document Title:").pack(anchor=tk.W, padx=10, pady=5)
        title_entry = ttk.Entry(dialog)
        title_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="File Path (optional):").pack(anchor=tk.W, padx=10, pady=5)
        file_frame = ttk.Frame(dialog)
        file_frame.pack(fill=tk.X, padx=10)
        file_entry = ttk.Entry(file_frame)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def browse_file():
            path = filedialog.askopenfilename()
            if path:
                file_entry.delete(0, tk.END)
                file_entry.insert(0, path)

        ttk.Button(file_frame, text="Browse", command=browse_file).pack(side=tk.RIGHT, padx=5)

        ttk.Label(dialog, text="Approval Chain (comma-separated user IDs):").pack(anchor=tk.W, padx=10, pady=5)
        chain_entry = ttk.Entry(dialog)
        chain_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Comments:").pack(anchor=tk.W, padx=10, pady=5)
        comments_text = tk.Text(dialog, height=5)
        comments_text.pack(fill=tk.X, padx=10, pady=5)

        def submit():
            title = title_entry.get().strip()
            if not title:
                messagebox.showerror("Error", "Document title is required")
                return

            chain = chain_entry.get().strip()
            chain_list = [c.strip() for c in chain.split(",") if c.strip()] if chain else []
            first_approver = chain_list[0] if chain_list else None

            user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO document_approvals
                        (document_type, document_title, document_path, submitted_by,
                         submitted_date, current_approver, approval_chain, current_step, status, comments)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        doc_type.get(),
                        title,
                        file_entry.get().strip() or None,
                        user_id,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        first_approver,
                        json.dumps(chain_list) if chain_list else None,
                        1,
                        "pending",
                        comments_text.get(1.0, tk.END).strip() or None
                    ))

                log_activity("create", "document_approval", user_id=user_id, details={"title": title})
                messagebox.showinfo("Success", "Document submitted for approval")
                dialog.destroy()
                self._load_document_approvals()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit document: {e}")

        ttk.Button(dialog, text="Submit", command=submit).pack(pady=10)

    def _view_document(self):
        """View the selected document file."""
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a document")
            return

        item = self.doc_tree.item(selected[0])
        doc_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT document_path FROM document_approvals WHERE approval_id = ?", (doc_id,))
                row = cursor.fetchone()

                if row and row[0]:
                    path = row[0]
                    if os.path.exists(path):
                        import subprocess
                        if os.name == 'nt':
                            os.startfile(path)
                        elif os.name == 'posix':
                            subprocess.run(['xdg-open', path], check=False)
                    else:
                        messagebox.showwarning("Warning", f"File not found: {path}")
                else:
                    messagebox.showinfo("Info", "No file attached to this document")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open document: {e}")

    def _process_approval(self, action):
        """Process approval or rejection."""
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a document")
            return

        item = self.doc_tree.item(selected[0])
        doc_id = item["values"][0]
        comments = self.approval_comments.get(1.0, tk.END).strip()

        user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

        try:
            with transaction() as conn:
                # Update document status
                conn.execute("""
                    UPDATE document_approvals
                    SET status = ?, completed_date = ?
                    WHERE approval_id = ?
                """, (action, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), doc_id))

                # Add to history
                conn.execute("""
                    INSERT INTO document_approval_history
                    (approval_id, action, action_by, action_date, comments)
                    VALUES (?, ?, ?, ?, ?)
                """, (doc_id, action, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comments))

            log_activity("update", "document_approval", approval_id=doc_id, details={"action": action})
            messagebox.showinfo("Success", f"Document {action}")
            self.approval_comments.delete(1.0, tk.END)
            self._load_document_approvals()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process approval: {e}")

    def _forward_approval(self):
        """Forward document to next approver in chain."""
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a document")
            return

        item = self.doc_tree.item(selected[0])
        doc_id = item["values"][0]
        comments = self.approval_comments.get(1.0, tk.END).strip()

        user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT approval_chain, current_step FROM document_approvals WHERE approval_id = ?", (doc_id,))
                row = cursor.fetchone()

                if row:
                    chain = json.loads(row[0]) if row[0] else []
                    current_step = row[1] or 1

                    if current_step < len(chain):
                        new_step = current_step + 1
                        next_approver = chain[new_step - 1] if new_step <= len(chain) else None

                        with transaction() as conn2:
                            conn2.execute("""
                                UPDATE document_approvals
                                SET current_step = ?, current_approver = ?, status = 'in_review'
                                WHERE approval_id = ?
                            """, (new_step, next_approver, doc_id))

                            conn2.execute("""
                                INSERT INTO document_approval_history
                                (approval_id, action, action_by, action_date, comments)
                                VALUES (?, ?, ?, ?, ?)
                            """, (doc_id, "forwarded", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comments))

                        log_activity("update", "document_approval", approval_id=doc_id, details={"action": "forwarded"})
                        messagebox.showinfo("Success", f"Document forwarded to step {new_step}")
                        self.approval_comments.delete(1.0, tk.END)
                        self._load_document_approvals()
                    else:
                        messagebox.showinfo("Info", "This is the final approval step. Use Approve or Reject.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to forward: {e}")

    # =========================================================================
    # Interdepartmental Requests Tab
    # =========================================================================
    def _create_requests_tab(self):
        """Create interdepartmental requests tab."""
        self.req_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.req_tab, text="Requests")

        main_paned = ttk.PanedWindow(self.req_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Request list
        list_frame = ttk.LabelFrame(left_frame, text="Interdepartmental Requests")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT)
        self.req_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "pending", "in_progress", "completed", "cancelled"
        ], state="readonly", width=15)
        self.req_status_filter.set("All")
        self.req_status_filter.pack(side=tk.LEFT, padx=5)
        self.req_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_requests())

        ttk.Label(filter_frame, text="Priority:").pack(side=tk.LEFT, padx=(15, 0))
        self.req_priority_filter = ttk.Combobox(filter_frame, values=[
            "All", "urgent", "high", "normal", "low"
        ], state="readonly", width=12)
        self.req_priority_filter.set("All")
        self.req_priority_filter.pack(side=tk.LEFT, padx=5)
        self.req_priority_filter.bind("<<ComboboxSelected>>", lambda e: self._load_requests())

        ttk.Button(filter_frame, text="Refresh", command=self._load_requests).pack(side=tk.RIGHT)

        # Treeview
        columns = ("id", "type", "title", "from_dept", "to_dept", "priority", "status", "due")
        self.req_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.req_tree.heading("id", text="ID")
        self.req_tree.heading("type", text="Type")
        self.req_tree.heading("title", text="Title")
        self.req_tree.heading("from_dept", text="From")
        self.req_tree.heading("to_dept", text="To")
        self.req_tree.heading("priority", text="Priority")
        self.req_tree.heading("status", text="Status")
        self.req_tree.heading("due", text="Due Date")

        self.req_tree.column("id", width=50)
        self.req_tree.column("type", width=100)
        self.req_tree.column("title", width=180)
        self.req_tree.column("from_dept", width=100)
        self.req_tree.column("to_dept", width=100)
        self.req_tree.column("priority", width=80)
        self.req_tree.column("status", width=90)
        self.req_tree.column("due", width=90)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.req_tree.yview)
        self.req_tree.configure(yscrollcommand=scrollbar.set)

        self.req_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.req_tree.bind("<<TreeviewSelect>>", self._on_request_select)

        # Tag colors
        self.req_tree.tag_configure("urgent", background="#f8d7da")
        self.req_tree.tag_configure("high", background="#fff3cd")
        self.req_tree.tag_configure("normal", background="#ffffff")
        self.req_tree.tag_configure("low", background="#e7f1ff")

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="New Request", command=self._new_request).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._edit_request).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Cancel Request", command=self._cancel_request).pack(side=tk.LEFT, padx=2)

        # Right: Request details
        detail_frame = ttk.LabelFrame(right_frame, text="Request Details")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.req_detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=15)
        self.req_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.req_detail_text.config(state=tk.DISABLED)

        # Response section
        response_frame = ttk.LabelFrame(right_frame, text="Response")
        response_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(response_frame, text="Response:").pack(anchor=tk.W, padx=5, pady=2)
        self.req_response = tk.Text(response_frame, height=4)
        self.req_response.pack(fill=tk.X, padx=5, pady=2)

        resp_btn_frame = ttk.Frame(response_frame)
        resp_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(resp_btn_frame, text="Accept", command=lambda: self._respond_request("in_progress")).pack(side=tk.LEFT, padx=2)
        ttk.Button(resp_btn_frame, text="Complete", command=lambda: self._respond_request("completed")).pack(side=tk.LEFT, padx=2)

        self._load_requests()

    def _load_requests(self):
        """Load interdepartmental requests."""
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)

        status_filter = self.req_status_filter.get()
        priority_filter = self.req_priority_filter.get()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM interdepartmental_requests WHERE 1=1"
                params = []

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                if priority_filter != "All":
                    query += " AND priority = ?"
                    params.append(priority_filter)

                query += " ORDER BY created_at DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    values = (
                        row[0],  # request_id
                        row[1] or "",  # request_type
                        row[5] or "Untitled",  # request_title
                        row[2] or "",  # from_department
                        row[3] or "",  # to_department
                        row[7] or "normal",  # priority
                        row[8] or "pending",  # status
                        row[10] or ""  # due_date
                    )
                    priority = row[7] or "normal"
                    self.req_tree.insert("", tk.END, values=values, tags=(priority,))

        except Exception:
            pass

    def _on_request_select(self, event):
        """Handle request selection."""
        selected = self.req_tree.selection()
        if not selected:
            return

        item = self.req_tree.item(selected[0])
        req_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM interdepartmental_requests WHERE request_id = ?", (req_id,))
                row = cursor.fetchone()

                if row:
                    self.req_detail_text.config(state=tk.NORMAL)
                    self.req_detail_text.delete(1.0, tk.END)

                    details = f"""Request ID: {row[0]}
Type: {row[1]}
From Department: {row[2]}
To Department: {row[3]}
Requested By: {row[4]}

Title: {row[5]}
Description:
{row[6] or 'No description'}

Priority: {row[7]}
Status: {row[8]}
Assigned To: {row[9] or 'Unassigned'}
Due Date: {row[10] or 'Not set'}

Response: {row[12] or 'No response yet'}
Created: {row[13]}
"""
                    self.req_detail_text.insert(1.0, details)
                    self.req_detail_text.config(state=tk.DISABLED)

        except Exception:
            pass

    def _new_request(self):
        """Create a new interdepartmental request."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Interdepartmental Request")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Request Type:").pack(anchor=tk.W, padx=10, pady=5)
        type_combo = ttk.Combobox(dialog, values=[
            "information", "support", "resource", "approval", "collaboration", "other"
        ], state="readonly")
        type_combo.pack(fill=tk.X, padx=10)
        type_combo.set("information")

        ttk.Label(dialog, text="From Department:").pack(anchor=tk.W, padx=10, pady=5)
        from_dept = ttk.Combobox(dialog, values=self._get_departments())
        from_dept.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="To Department:").pack(anchor=tk.W, padx=10, pady=5)
        to_dept = ttk.Combobox(dialog, values=self._get_departments())
        to_dept.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Title:").pack(anchor=tk.W, padx=10, pady=5)
        title_entry = ttk.Entry(dialog)
        title_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Description:").pack(anchor=tk.W, padx=10, pady=5)
        desc_text = tk.Text(dialog, height=5)
        desc_text.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Priority:").pack(anchor=tk.W, padx=10, pady=5)
        priority = ttk.Combobox(dialog, values=["low", "normal", "high", "urgent"], state="readonly")
        priority.pack(fill=tk.X, padx=10)
        priority.set("normal")

        ttk.Label(dialog, text="Due Date (YYYY-MM-DD):").pack(anchor=tk.W, padx=10, pady=5)
        due_entry = ttk.Entry(dialog)
        due_entry.pack(fill=tk.X, padx=10)

        def submit():
            title = title_entry.get().strip()
            if not title:
                messagebox.showerror("Error", "Title is required")
                return

            user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO interdepartmental_requests
                        (request_type, from_department, to_department, requested_by,
                         request_title, request_description, priority, status, due_date, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        type_combo.get(),
                        from_dept.get(),
                        to_dept.get(),
                        user_id,
                        title,
                        desc_text.get(1.0, tk.END).strip(),
                        priority.get(),
                        "pending",
                        due_entry.get().strip() or None,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                log_activity("create", "interdepartmental_request", user_id=user_id, details={"title": title})
                messagebox.showinfo("Success", "Request submitted")
                dialog.destroy()
                self._load_requests()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create request: {e}")

        ttk.Button(dialog, text="Submit", command=submit).pack(pady=10)

    def _edit_request(self):
        """Edit selected request."""
        selected = self.req_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a request")
            return

        item = self.req_tree.item(selected[0])
        req_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM interdepartmental_requests WHERE request_id = ?", (req_id,))
                row = cursor.fetchone()

                if row:
                    dialog = tk.Toplevel(self.root)
                    dialog.title("Edit Request")
                    dialog.geometry("500x400")
                    dialog.transient(self.root)
                    dialog.grab_set()

                    ttk.Label(dialog, text="Title:").pack(anchor=tk.W, padx=10, pady=5)
                    title_entry = ttk.Entry(dialog)
                    title_entry.pack(fill=tk.X, padx=10)
                    title_entry.insert(0, row[5] or "")

                    ttk.Label(dialog, text="Description:").pack(anchor=tk.W, padx=10, pady=5)
                    desc_text = tk.Text(dialog, height=5)
                    desc_text.pack(fill=tk.X, padx=10)
                    desc_text.insert(1.0, row[6] or "")

                    ttk.Label(dialog, text="Priority:").pack(anchor=tk.W, padx=10, pady=5)
                    priority = ttk.Combobox(dialog, values=["low", "normal", "high", "urgent"], state="readonly")
                    priority.pack(fill=tk.X, padx=10)
                    priority.set(row[7] or "normal")

                    ttk.Label(dialog, text="Status:").pack(anchor=tk.W, padx=10, pady=5)
                    status = ttk.Combobox(dialog, values=["pending", "in_progress", "completed", "cancelled"], state="readonly")
                    status.pack(fill=tk.X, padx=10)
                    status.set(row[8] or "pending")

                    ttk.Label(dialog, text="Due Date (YYYY-MM-DD):").pack(anchor=tk.W, padx=10, pady=5)
                    due_entry = ttk.Entry(dialog)
                    due_entry.pack(fill=tk.X, padx=10)
                    due_entry.insert(0, row[10] or "")

                    def save():
                        try:
                            with transaction() as conn2:
                                conn2.execute("""
                                    UPDATE interdepartmental_requests
                                    SET request_title = ?, request_description = ?,
                                        priority = ?, status = ?, due_date = ?
                                    WHERE request_id = ?
                                """, (
                                    title_entry.get().strip(),
                                    desc_text.get(1.0, tk.END).strip(),
                                    priority.get(),
                                    status.get(),
                                    due_entry.get().strip() or None,
                                    req_id
                                ))

                            log_activity("update", "interdepartmental_request", details={"request_id": req_id})
                            messagebox.showinfo("Success", "Request updated")
                            dialog.destroy()
                            self._load_requests()

                        except Exception as e:
                            messagebox.showerror("Error", f"Failed to update: {e}")

                    ttk.Button(dialog, text="Save", command=save).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load request: {e}")

    def _cancel_request(self):
        """Cancel selected request."""
        selected = self.req_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a request")
            return

        if not messagebox.askyesno("Confirm", "Cancel this request?"):
            return

        item = self.req_tree.item(selected[0])
        req_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE interdepartmental_requests SET status = 'cancelled' WHERE request_id = ?", (req_id,))

            log_activity("update", "interdepartmental_request", details={"action": "cancelled", "request_id": req_id})
            messagebox.showinfo("Success", "Request cancelled")
            self._load_requests()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to cancel: {e}")

    def _respond_request(self, new_status):
        """Respond to a request."""
        selected = self.req_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a request")
            return

        item = self.req_tree.item(selected[0])
        req_id = item["values"][0]
        response = self.req_response.get(1.0, tk.END).strip()

        user_id = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

        try:
            with transaction() as conn:
                completed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == "completed" else None
                conn.execute("""
                    UPDATE interdepartmental_requests
                    SET status = ?, assigned_to = ?, response = ?, completed_date = ?
                    WHERE request_id = ?
                """, (new_status, user_id, response, completed_date, req_id))

            log_activity("update", "interdepartmental_request", details={"status": new_status, "request_id": req_id})
            messagebox.showinfo("Success", f"Request marked as {new_status}")
            self.req_response.delete(1.0, tk.END)
            self._load_requests()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update request: {e}")

    def _get_departments(self):
        """Get list of departments."""
        try:
            from education_system.systems.university.infrastructure.database.schemas.staff_hr_schemas_all import get_departments
            return get_departments()
        except ImportError:
            return [
                "Computer Science", "Mathematics", "Physics", "Chemistry", "Biology",
                "Engineering", "Business", "Economics", "Psychology", "Sociology",
                "History", "English", "Philosophy", "Art", "Music", "IT Services",
                "Human Resources", "Finance", "Facilities", "Library", "Admissions"
            ]

    # =========================================================================
    # Keys & Access Tab
    # =========================================================================
    def _create_keys_access_tab(self):
        """Create keys and access cards management tab."""
        self.keys_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.keys_tab, text="Keys & Access")

        sub_notebook = ttk.Notebook(self.keys_tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Access Cards sub-tab
        self._create_access_cards_subtab(sub_notebook)

        # Key Assignments sub-tab
        self._create_key_assignments_subtab(sub_notebook)

    def _create_access_cards_subtab(self, parent):
        """Create access cards management sub-tab."""
        cards_tab = ttk.Frame(parent)
        parent.add(cards_tab, text="Access Cards")

        main_paned = ttk.PanedWindow(cards_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Card list
        list_frame = ttk.LabelFrame(left_frame, text="Access Cards")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT)
        self.card_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "active", "inactive", "lost", "expired"
        ], state="readonly", width=12)
        self.card_status_filter.set("active")
        self.card_status_filter.pack(side=tk.LEFT, padx=5)
        self.card_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_access_cards())

        ttk.Label(filter_frame, text="Search:").pack(side=tk.LEFT, padx=(15, 0))
        self.card_search = ttk.Entry(filter_frame, width=20)
        self.card_search.pack(side=tk.LEFT, padx=5)
        self.card_search.bind("<Return>", lambda e: self._load_access_cards())

        ttk.Button(filter_frame, text="Search", command=self._load_access_cards).pack(side=tk.LEFT, padx=2)

        # Treeview
        columns = ("id", "card_number", "user_id", "type", "access_level", "issue_date", "expiry", "status")
        self.cards_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.cards_tree.heading("id", text="ID")
        self.cards_tree.heading("card_number", text="Card #")
        self.cards_tree.heading("user_id", text="User")
        self.cards_tree.heading("type", text="Type")
        self.cards_tree.heading("access_level", text="Access Level")
        self.cards_tree.heading("issue_date", text="Issued")
        self.cards_tree.heading("expiry", text="Expires")
        self.cards_tree.heading("status", text="Status")

        self.cards_tree.column("id", width=50)
        self.cards_tree.column("card_number", width=100)
        self.cards_tree.column("user_id", width=100)
        self.cards_tree.column("type", width=80)
        self.cards_tree.column("access_level", width=100)
        self.cards_tree.column("issue_date", width=90)
        self.cards_tree.column("expiry", width=90)
        self.cards_tree.column("status", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.cards_tree.yview)
        self.cards_tree.configure(yscrollcommand=scrollbar.set)

        self.cards_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.cards_tree.bind("<<TreeviewSelect>>", self._on_card_select)

        # Tag colors
        self.cards_tree.tag_configure("active", background="#d1e7dd")
        self.cards_tree.tag_configure("inactive", background="#e7e8e9")
        self.cards_tree.tag_configure("lost", background="#f8d7da")
        self.cards_tree.tag_configure("expired", background="#fff3cd")

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Issue New Card", command=self._issue_card).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Deactivate", command=self._deactivate_card).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Report Lost", command=self._report_card_lost).pack(side=tk.LEFT, padx=2)

        # Right: Card details
        detail_frame = ttk.LabelFrame(right_frame, text="Card Details")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.card_detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=15)
        self.card_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.card_detail_text.config(state=tk.DISABLED)

        # Edit card access
        edit_frame = ttk.LabelFrame(right_frame, text="Modify Access")
        edit_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(edit_frame, text="Access Level:").pack(anchor=tk.W, padx=5, pady=2)
        self.new_access_level = ttk.Combobox(edit_frame, values=[
            "basic", "standard", "elevated", "full", "restricted"
        ], state="readonly")
        self.new_access_level.pack(fill=tk.X, padx=5, pady=2)
        self.new_access_level.set("standard")

        ttk.Label(edit_frame, text="Buildings Access (comma-separated):").pack(anchor=tk.W, padx=5, pady=2)
        self.buildings_entry = ttk.Entry(edit_frame)
        self.buildings_entry.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(edit_frame, text="Update Access", command=self._update_card_access).pack(pady=5)

        self._load_access_cards()

    def _load_access_cards(self):
        """Load access cards from database."""
        for item in self.cards_tree.get_children():
            self.cards_tree.delete(item)

        status_filter = self.card_status_filter.get()
        search_term = self.card_search.get().strip()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM access_cards WHERE 1=1"
                params = []

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                if search_term:
                    query += " AND (card_number LIKE ? OR user_id LIKE ?)"
                    params.extend([f"%{escape_like(search_term)}%", f"%{escape_like(search_term)}%"])

                query += " ORDER BY created_at DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    values = (
                        row[0],  # card_id
                        row[1] or "",  # card_number
                        row[2] or "",  # user_id
                        row[3] or "",  # card_type
                        row[4] or "",  # access_level
                        row[6] or "",  # issue_date
                        row[7] or "",  # expiry_date
                        row[8] or "active"  # status
                    )
                    status = row[8] or "active"
                    self.cards_tree.insert("", tk.END, values=values, tags=(status,))

        except Exception:
            pass

    def _on_card_select(self, event):
        """Handle card selection."""
        selected = self.cards_tree.selection()
        if not selected:
            return

        item = self.cards_tree.item(selected[0])
        card_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM access_cards WHERE card_id = ?", (card_id,))
                row = cursor.fetchone()

                if row:
                    buildings = row[5]
                    if buildings:
                        try:
                            buildings = ", ".join(json.loads(buildings))
                        except (ValueError, json.JSONDecodeError):
                            pass

                    self.card_detail_text.config(state=tk.NORMAL)
                    self.card_detail_text.delete(1.0, tk.END)

                    details = f"""Card ID: {row[0]}
Card Number: {row[1]}
User ID: {row[2]}
Card Type: {row[3]}
Access Level: {row[4]}

Buildings Access: {buildings or 'All'}

Issue Date: {row[6]}
Expiry Date: {row[7]}
Status: {row[8]}

Issued By: {row[9]}
Notes: {row[10] or 'None'}
Created: {row[11]}
"""
                    self.card_detail_text.insert(1.0, details)
                    self.card_detail_text.config(state=tk.DISABLED)

                    # Update edit fields
                    self.new_access_level.set(row[4] or "standard")
                    self.buildings_entry.delete(0, tk.END)
                    if buildings:
                        self.buildings_entry.insert(0, buildings)

        except Exception:
            pass

    def _issue_card(self):
        """Issue a new access card."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Issue New Access Card")
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Card Number:").pack(anchor=tk.W, padx=10, pady=5)
        card_num = ttk.Entry(dialog)
        card_num.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="User ID:").pack(anchor=tk.W, padx=10, pady=5)
        user_id = ttk.Entry(dialog)
        user_id.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Card Type:").pack(anchor=tk.W, padx=10, pady=5)
        card_type = ttk.Combobox(dialog, values=["staff", "contractor", "visitor", "temporary"], state="readonly")
        card_type.pack(fill=tk.X, padx=10)
        card_type.set("staff")

        ttk.Label(dialog, text="Access Level:").pack(anchor=tk.W, padx=10, pady=5)
        access_level = ttk.Combobox(dialog, values=["basic", "standard", "elevated", "full", "restricted"], state="readonly")
        access_level.pack(fill=tk.X, padx=10)
        access_level.set("standard")

        ttk.Label(dialog, text="Buildings Access (comma-separated):").pack(anchor=tk.W, padx=10, pady=5)
        buildings = ttk.Entry(dialog)
        buildings.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Expiry Date (YYYY-MM-DD):").pack(anchor=tk.W, padx=10, pady=5)
        expiry = ttk.Entry(dialog)
        expiry.pack(fill=tk.X, padx=10)
        # Default to 1 year from now
        default_expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        expiry.insert(0, default_expiry)

        ttk.Label(dialog, text="Notes:").pack(anchor=tk.W, padx=10, pady=5)
        notes = tk.Text(dialog, height=4)
        notes.pack(fill=tk.X, padx=10)

        def issue():
            card_number = card_num.get().strip()
            if not card_number:
                messagebox.showerror("Error", "Card number is required")
                return

            issuer = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"
            buildings_list = [b.strip() for b in buildings.get().split(",") if b.strip()]

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO access_cards
                        (card_number, user_id, card_type, access_level, buildings_access,
                         issue_date, expiry_date, status, issued_by, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        card_number,
                        user_id.get().strip(),
                        card_type.get(),
                        access_level.get(),
                        json.dumps(buildings_list) if buildings_list else None,
                        datetime.now().strftime("%Y-%m-%d"),
                        expiry.get().strip() or None,
                        "active",
                        issuer,
                        notes.get(1.0, tk.END).strip() or None,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                log_activity("create", "access_card", user_id=issuer, details={"card_number": card_number})
                messagebox.showinfo("Success", "Access card issued")
                dialog.destroy()
                self._load_access_cards()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to issue card: {e}")

        ttk.Button(dialog, text="Issue Card", command=issue).pack(pady=10)

    def _deactivate_card(self):
        """Deactivate selected card."""
        selected = self.cards_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a card")
            return

        if not messagebox.askyesno("Confirm", "Deactivate this card?"):
            return

        item = self.cards_tree.item(selected[0])
        card_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE access_cards SET status = 'inactive' WHERE card_id = ?", (card_id,))

            log_activity("update", "access_card", card_id=card_id, details={"action": "deactivated"})
            messagebox.showinfo("Success", "Card deactivated")
            self._load_access_cards()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to deactivate: {e}")

    def _report_card_lost(self):
        """Report card as lost."""
        selected = self.cards_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a card")
            return

        if not messagebox.askyesno("Confirm", "Report this card as lost? It will be deactivated."):
            return

        item = self.cards_tree.item(selected[0])
        card_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE access_cards SET status = 'lost' WHERE card_id = ?", (card_id,))

            log_activity("update", "access_card", card_id=card_id, details={"action": "reported_lost"})
            messagebox.showinfo("Success", "Card reported as lost and deactivated")
            self._load_access_cards()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update: {e}")

    def _update_card_access(self):
        """Update card access level and buildings."""
        selected = self.cards_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a card")
            return

        item = self.cards_tree.item(selected[0])
        card_id = item["values"][0]

        buildings_list = [b.strip() for b in self.buildings_entry.get().split(",") if b.strip()]

        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE access_cards
                    SET access_level = ?, buildings_access = ?
                    WHERE card_id = ?
                """, (
                    self.new_access_level.get(),
                    json.dumps(buildings_list) if buildings_list else None,
                    card_id
                ))

            log_activity("update", "access_card", card_id=card_id, details={"access_level": self.new_access_level.get()})
            messagebox.showinfo("Success", "Card access updated")
            self._load_access_cards()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update: {e}")

    def _create_key_assignments_subtab(self, parent):
        """Create key assignments sub-tab."""
        keys_tab = ttk.Frame(parent)
        parent.add(keys_tab, text="Key Assignments")

        main_paned = ttk.PanedWindow(keys_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Key list
        list_frame = ttk.LabelFrame(left_frame, text="Key Assignments")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT)
        self.key_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "assigned", "returned", "lost"
        ], state="readonly", width=12)
        self.key_status_filter.set("assigned")
        self.key_status_filter.pack(side=tk.LEFT, padx=5)
        self.key_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_keys())

        ttk.Button(filter_frame, text="Refresh", command=self._load_keys).pack(side=tk.RIGHT)

        # Treeview
        columns = ("id", "key_number", "type", "room", "assigned_to", "assigned_date", "status")
        self.keys_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.keys_tree.heading("id", text="ID")
        self.keys_tree.heading("key_number", text="Key #")
        self.keys_tree.heading("type", text="Type")
        self.keys_tree.heading("room", text="Room/Location")
        self.keys_tree.heading("assigned_to", text="Assigned To")
        self.keys_tree.heading("assigned_date", text="Assigned")
        self.keys_tree.heading("status", text="Status")

        self.keys_tree.column("id", width=50)
        self.keys_tree.column("key_number", width=100)
        self.keys_tree.column("type", width=80)
        self.keys_tree.column("room", width=120)
        self.keys_tree.column("assigned_to", width=120)
        self.keys_tree.column("assigned_date", width=100)
        self.keys_tree.column("status", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.keys_tree.yview)
        self.keys_tree.configure(yscrollcommand=scrollbar.set)

        self.keys_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.keys_tree.bind("<<TreeviewSelect>>", self._on_key_select)

        # Tag colors
        self.keys_tree.tag_configure("assigned", background="#cfe2ff")
        self.keys_tree.tag_configure("returned", background="#d1e7dd")
        self.keys_tree.tag_configure("lost", background="#f8d7da")

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Assign Key", command=self._assign_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Return Key", command=self._return_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Report Lost", command=self._report_key_lost).pack(side=tk.LEFT, padx=2)

        # Right: Key details
        detail_frame = ttk.LabelFrame(right_frame, text="Key Details")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.key_detail_text = tk.Text(detail_frame, wrap=tk.WORD)
        self.key_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.key_detail_text.config(state=tk.DISABLED)

        self._load_keys()

    def _load_keys(self):
        """Load key assignments from database."""
        for item in self.keys_tree.get_children():
            self.keys_tree.delete(item)

        status_filter = self.key_status_filter.get()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM key_assignments WHERE 1=1"
                params = []

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                query += " ORDER BY created_at DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    values = (
                        row[0],  # assignment_id
                        row[1] or "",  # key_number
                        row[2] or "",  # key_type
                        row[3] or "",  # room_location
                        row[4] or "",  # assigned_to
                        row[5] or "",  # assigned_date
                        row[7] or "assigned"  # status
                    )
                    status = row[7] or "assigned"
                    self.keys_tree.insert("", tk.END, values=values, tags=(status,))

        except Exception:
            pass

    def _on_key_select(self, event):
        """Handle key selection."""
        selected = self.keys_tree.selection()
        if not selected:
            return

        item = self.keys_tree.item(selected[0])
        key_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM key_assignments WHERE assignment_id = ?", (key_id,))
                row = cursor.fetchone()

                if row:
                    self.key_detail_text.config(state=tk.NORMAL)
                    self.key_detail_text.delete(1.0, tk.END)

                    details = f"""Assignment ID: {row[0]}
Key Number: {row[1]}
Key Type: {row[2]}
Room/Location: {row[3]}

Assigned To: {row[4]}
Assigned Date: {row[5]}
Return Date: {row[6] or 'Not returned'}
Status: {row[7]}

Issued By: {row[8]}
Notes: {row[9] or 'None'}
Created: {row[10]}
"""
                    self.key_detail_text.insert(1.0, details)
                    self.key_detail_text.config(state=tk.DISABLED)

        except Exception:
            pass

    def _assign_key(self):
        """Assign a new key."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Assign Key")
        dialog.geometry("400x400")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Key Number:").pack(anchor=tk.W, padx=10, pady=5)
        key_num = ttk.Entry(dialog)
        key_num.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Key Type:").pack(anchor=tk.W, padx=10, pady=5)
        key_type = ttk.Combobox(dialog, values=["master", "room", "cabinet", "building", "parking"], state="readonly")
        key_type.pack(fill=tk.X, padx=10)
        key_type.set("room")

        ttk.Label(dialog, text="Room/Location:").pack(anchor=tk.W, padx=10, pady=5)
        room = ttk.Entry(dialog)
        room.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Assign To (User ID):").pack(anchor=tk.W, padx=10, pady=5)
        assign_to = ttk.Entry(dialog)
        assign_to.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Notes:").pack(anchor=tk.W, padx=10, pady=5)
        notes = tk.Text(dialog, height=4)
        notes.pack(fill=tk.X, padx=10)

        def assign():
            key_number = key_num.get().strip()
            if not key_number:
                messagebox.showerror("Error", "Key number is required")
                return

            assigned_to = assign_to.get().strip()
            if not assigned_to:
                messagebox.showerror("Error", "User ID is required")
                return

            issuer = self.current_user.get("user_id", "unknown") if self.current_user else "unknown"

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO key_assignments
                        (key_number, key_type, room_location, assigned_to, assigned_date,
                         status, issued_by, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        key_number,
                        key_type.get(),
                        room.get().strip(),
                        assigned_to,
                        datetime.now().strftime("%Y-%m-%d"),
                        "assigned",
                        issuer,
                        notes.get(1.0, tk.END).strip() or None,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                log_activity("create", "key_assignment", user_id=issuer, details={"key_number": key_number, "assigned_to": assigned_to})
                messagebox.showinfo("Success", "Key assigned")
                dialog.destroy()
                self._load_keys()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to assign key: {e}")

        ttk.Button(dialog, text="Assign", command=assign).pack(pady=10)

    def _return_key(self):
        """Mark key as returned."""
        selected = self.keys_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a key")
            return

        if not messagebox.askyesno("Confirm", "Mark this key as returned?"):
            return

        item = self.keys_tree.item(selected[0])
        key_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE key_assignments
                    SET status = 'returned', return_date = ?
                    WHERE assignment_id = ?
                """, (datetime.now().strftime("%Y-%m-%d"), key_id))

            log_activity("update", "key_assignment", assignment_id=key_id, details={"action": "returned"})
            messagebox.showinfo("Success", "Key marked as returned")
            self._load_keys()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update: {e}")

    def _report_key_lost(self):
        """Report key as lost."""
        selected = self.keys_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a key")
            return

        if not messagebox.askyesno("Confirm", "Report this key as lost?"):
            return

        item = self.keys_tree.item(selected[0])
        key_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE key_assignments SET status = 'lost' WHERE assignment_id = ?", (key_id,))

            log_activity("update", "key_assignment", assignment_id=key_id, details={"action": "reported_lost"})
            messagebox.showinfo("Success", "Key reported as lost")
            self._load_keys()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update: {e}")

    # =========================================================================
    # Visitors Tab
    # =========================================================================
    def _create_visitors_tab(self):
        """Create visitor management tab."""
        self.visitors_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.visitors_tab, text="Visitors")

        main_paned = ttk.PanedWindow(self.visitors_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Visitor list
        list_frame = ttk.LabelFrame(left_frame, text="Visitor Registrations")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="Date:").pack(side=tk.LEFT)
        self.visitor_date = ttk.Entry(filter_frame, width=12)
        self.visitor_date.pack(side=tk.LEFT, padx=5)
        self.visitor_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=(15, 0))
        self.visitor_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "scheduled", "checked_in", "checked_out", "cancelled"
        ], state="readonly", width=12)
        self.visitor_status_filter.set("All")
        self.visitor_status_filter.pack(side=tk.LEFT, padx=5)
        self.visitor_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_visitors())

        ttk.Button(filter_frame, text="Search", command=self._load_visitors).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Today", command=self._show_today_visitors).pack(side=tk.RIGHT)

        # Treeview
        columns = ("id", "name", "company", "host", "purpose", "time", "status")
        self.visitors_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.visitors_tree.heading("id", text="ID")
        self.visitors_tree.heading("name", text="Visitor Name")
        self.visitors_tree.heading("company", text="Company")
        self.visitors_tree.heading("host", text="Host")
        self.visitors_tree.heading("purpose", text="Purpose")
        self.visitors_tree.heading("time", text="Time")
        self.visitors_tree.heading("status", text="Status")

        self.visitors_tree.column("id", width=50)
        self.visitors_tree.column("name", width=150)
        self.visitors_tree.column("company", width=120)
        self.visitors_tree.column("host", width=100)
        self.visitors_tree.column("purpose", width=150)
        self.visitors_tree.column("time", width=80)
        self.visitors_tree.column("status", width=90)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.visitors_tree.yview)
        self.visitors_tree.configure(yscrollcommand=scrollbar.set)

        self.visitors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.visitors_tree.bind("<<TreeviewSelect>>", self._on_visitor_select)

        # Tag colors
        self.visitors_tree.tag_configure("scheduled", background="#cfe2ff")
        self.visitors_tree.tag_configure("checked_in", background="#d1e7dd")
        self.visitors_tree.tag_configure("checked_out", background="#e7e8e9")
        self.visitors_tree.tag_configure("cancelled", background="#f8d7da")

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Register Visitor", command=self._register_visitor).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Check In", command=self._check_in_visitor).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Check Out", command=self._check_out_visitor).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Cancel", command=self._cancel_visitor).pack(side=tk.LEFT, padx=2)

        # Right: Visitor details
        detail_frame = ttk.LabelFrame(right_frame, text="Visitor Details")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.visitor_detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=15)
        self.visitor_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.visitor_detail_text.config(state=tk.DISABLED)

        # Quick check-in
        checkin_frame = ttk.LabelFrame(right_frame, text="Quick Check-In")
        checkin_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(checkin_frame, text="Badge Number:").pack(anchor=tk.W, padx=5, pady=2)
        self.badge_entry = ttk.Entry(checkin_frame)
        self.badge_entry.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(checkin_frame, text="Vehicle Registration (optional):").pack(anchor=tk.W, padx=5, pady=2)
        self.vehicle_entry = ttk.Entry(checkin_frame)
        self.vehicle_entry.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(checkin_frame, text="Check In with Badge", command=self._quick_check_in).pack(pady=5)

        # Stats
        stats_frame = ttk.LabelFrame(right_frame, text="Today's Stats")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        self.stats_label = ttk.Label(stats_frame, text="Loading...")
        self.stats_label.pack(padx=5, pady=5)

        self._load_visitors()
        self._update_visitor_stats()

    def _load_visitors(self):
        """Load visitor registrations."""
        for item in self.visitors_tree.get_children():
            self.visitors_tree.delete(item)

        date_filter = self.visitor_date.get().strip()
        status_filter = self.visitor_status_filter.get()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM visitor_registrations WHERE 1=1"
                params = []

                if date_filter:
                    query += " AND scheduled_date = ?"
                    params.append(date_filter)

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                query += " ORDER BY scheduled_time ASC, created_at DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    values = (
                        row[0],  # visitor_id
                        row[1] or "",  # visitor_name
                        row[4] or "",  # visitor_company
                        row[5] or "",  # host_id
                        row[6] or "",  # visit_purpose
                        row[8] or "",  # scheduled_time
                        row[11] or "scheduled"  # status
                    )
                    status = row[11] or "scheduled"
                    self.visitors_tree.insert("", tk.END, values=values, tags=(status,))

        except Exception:
            pass

        self._update_visitor_stats()

    def _show_today_visitors(self):
        """Show today's visitors."""
        self.visitor_date.delete(0, tk.END)
        self.visitor_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._load_visitors()

    def _on_visitor_select(self, event):
        """Handle visitor selection."""
        selected = self.visitors_tree.selection()
        if not selected:
            return

        item = self.visitors_tree.item(selected[0])
        visitor_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM visitor_registrations WHERE visitor_id = ?", (visitor_id,))
                row = cursor.fetchone()

                if row:
                    self.visitor_detail_text.config(state=tk.NORMAL)
                    self.visitor_detail_text.delete(1.0, tk.END)

                    details = f"""Visitor ID: {row[0]}
Name: {row[1]}
Email: {row[2] or 'N/A'}
Phone: {row[3] or 'N/A'}
Company: {row[4] or 'N/A'}

Host: {row[5]}
Purpose: {row[6]}

Scheduled Date: {row[7]}
Scheduled Time: {row[8]}

Check-in Time: {row[9] or 'Not checked in'}
Check-out Time: {row[10] or 'Not checked out'}
Status: {row[11]}

Badge Number: {row[12] or 'N/A'}
Vehicle: {row[13] or 'N/A'}
Notes: {row[14] or 'None'}
"""
                    self.visitor_detail_text.insert(1.0, details)
                    self.visitor_detail_text.config(state=tk.DISABLED)

        except Exception:
            pass

    def _register_visitor(self):
        """Register a new visitor."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Register Visitor")
        dialog.geometry("450x550")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Visitor Name:").pack(anchor=tk.W, padx=10, pady=5)
        name_entry = ttk.Entry(dialog)
        name_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Email:").pack(anchor=tk.W, padx=10, pady=5)
        email_entry = ttk.Entry(dialog)
        email_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Phone:").pack(anchor=tk.W, padx=10, pady=5)
        phone_entry = ttk.Entry(dialog)
        phone_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Company/Organization:").pack(anchor=tk.W, padx=10, pady=5)
        company_entry = ttk.Entry(dialog)
        company_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Host (User ID):").pack(anchor=tk.W, padx=10, pady=5)
        host_entry = ttk.Entry(dialog)
        host_entry.pack(fill=tk.X, padx=10)
        if self.current_user:
            host_entry.insert(0, self.current_user.get("user_id", ""))

        ttk.Label(dialog, text="Purpose of Visit:").pack(anchor=tk.W, padx=10, pady=5)
        purpose_entry = ttk.Entry(dialog)
        purpose_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Scheduled Date (YYYY-MM-DD):").pack(anchor=tk.W, padx=10, pady=5)
        date_entry = ttk.Entry(dialog)
        date_entry.pack(fill=tk.X, padx=10)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        ttk.Label(dialog, text="Scheduled Time (HH:MM):").pack(anchor=tk.W, padx=10, pady=5)
        time_entry = ttk.Entry(dialog)
        time_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Notes:").pack(anchor=tk.W, padx=10, pady=5)
        notes_text = tk.Text(dialog, height=3)
        notes_text.pack(fill=tk.X, padx=10)

        def register():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Visitor name is required")
                return

            host = host_entry.get().strip()
            if not host:
                messagebox.showerror("Error", "Host is required")
                return

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO visitor_registrations
                        (visitor_name, visitor_email, visitor_phone, visitor_company,
                         host_id, visit_purpose, scheduled_date, scheduled_time,
                         status, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name,
                        email_entry.get().strip() or None,
                        phone_entry.get().strip() or None,
                        company_entry.get().strip() or None,
                        host,
                        purpose_entry.get().strip(),
                        date_entry.get().strip(),
                        time_entry.get().strip() or None,
                        "scheduled",
                        notes_text.get(1.0, tk.END).strip() or None,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                log_activity("create", "visitor_registration", user_id=host, details={"visitor_name": name})
                messagebox.showinfo("Success", "Visitor registered")
                dialog.destroy()
                self._load_visitors()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to register visitor: {e}")

        ttk.Button(dialog, text="Register", command=register).pack(pady=10)

    def _check_in_visitor(self):
        """Check in selected visitor."""
        selected = self.visitors_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a visitor")
            return

        item = self.visitors_tree.item(selected[0])
        visitor_id = item["values"][0]
        current_status = item["values"][6]

        if current_status == "checked_in":
            messagebox.showinfo("Info", "Visitor is already checked in")
            return

        badge = self.badge_entry.get().strip()
        vehicle = self.vehicle_entry.get().strip()

        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE visitor_registrations
                    SET status = 'checked_in', check_in_time = ?,
                        badge_number = ?, vehicle_registration = ?
                    WHERE visitor_id = ?
                """, (
                    datetime.now().strftime("%H:%M:%S"),
                    badge or None,
                    vehicle or None,
                    visitor_id
                ))

            log_activity("update", "visitor_registration", visitor_id=visitor_id, details={"action": "checked_in"})
            messagebox.showinfo("Success", "Visitor checked in")
            self.badge_entry.delete(0, tk.END)
            self.vehicle_entry.delete(0, tk.END)
            self._load_visitors()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check in: {e}")

    def _quick_check_in(self):
        """Quick check-in with badge for selected visitor."""
        self._check_in_visitor()

    def _check_out_visitor(self):
        """Check out selected visitor."""
        selected = self.visitors_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a visitor")
            return

        item = self.visitors_tree.item(selected[0])
        visitor_id = item["values"][0]
        current_status = item["values"][6]

        if current_status != "checked_in":
            messagebox.showinfo("Info", "Visitor is not checked in")
            return

        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE visitor_registrations
                    SET status = 'checked_out', check_out_time = ?
                    WHERE visitor_id = ?
                """, (datetime.now().strftime("%H:%M:%S"), visitor_id))

            log_activity("update", "visitor_registration", visitor_id=visitor_id, details={"action": "checked_out"})
            messagebox.showinfo("Success", "Visitor checked out")
            self._load_visitors()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check out: {e}")

    def _cancel_visitor(self):
        """Cancel visitor registration."""
        selected = self.visitors_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a visitor")
            return

        if not messagebox.askyesno("Confirm", "Cancel this visitor registration?"):
            return

        item = self.visitors_tree.item(selected[0])
        visitor_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE visitor_registrations SET status = 'cancelled' WHERE visitor_id = ?", (visitor_id,))

            log_activity("update", "visitor_registration", visitor_id=visitor_id, details={"action": "cancelled"})
            messagebox.showinfo("Success", "Visitor registration cancelled")
            self._load_visitors()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to cancel: {e}")

    def _update_visitor_stats(self):
        """Update today's visitor statistics."""
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Total scheduled today
                cursor.execute("SELECT COUNT(*) FROM visitor_registrations WHERE scheduled_date = ?", (today,))
                total = cursor.fetchone()[0]

                # Checked in
                cursor.execute("SELECT COUNT(*) FROM visitor_registrations WHERE scheduled_date = ? AND status = 'checked_in'", (today,))
                checked_in = cursor.fetchone()[0]

                # Checked out
                cursor.execute("SELECT COUNT(*) FROM visitor_registrations WHERE scheduled_date = ? AND status = 'checked_out'", (today,))
                checked_out = cursor.fetchone()[0]

                # Pending
                cursor.execute("SELECT COUNT(*) FROM visitor_registrations WHERE scheduled_date = ? AND status = 'scheduled'", (today,))
                pending = cursor.fetchone()[0]

                self.stats_label.config(text=f"Total: {total} | Checked In: {checked_in} | Checked Out: {checked_out} | Pending: {pending}")

        except Exception:
            self.stats_label.config(text="Stats unavailable")


def main():
    """Main function for standalone execution."""
    root = tk.Tk()
    app = AdminToolsGUI(root, None)
    root.mainloop()


if __name__ == "__main__":
    main()
