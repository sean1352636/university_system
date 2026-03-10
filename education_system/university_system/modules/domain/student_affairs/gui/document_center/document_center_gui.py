"""Personal Document Center (Feature 43).

Allows students to view their documents, request official documents,
upload personal files, and track document request statuses.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class DocumentCenterGUI:
    """Toplevel window for the personal document center."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = (
            auth.current_user.get("username", "") if auth and auth.current_user else ""
        )

        self.window = tk.Toplevel(parent)
        self.window.title("My Documents")
        self.window.geometry("900x600")
        self.window.minsize(700, 450)

        if not self.student_id:
            messagebox.showerror(
                "Error",
                "You must be logged in to access the Document Center.",
                parent=self.window,
            )
            self.window.destroy()
            return

        self._ensure_tables()
        self._build_ui()
        logger.info("DocumentCenterGUI opened for student %s", self.student_id)

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def _get_user_int_id(self):
        """Return the integer user ID from auth.current_user, or None."""
        if self.auth and self.auth.current_user:
            uid = self.auth.current_user.get('id')
            if uid is not None:
                try:
                    return int(uid)
                except (ValueError, TypeError):
                    pass
        # Fallback: look up from the users table
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ?",
                    (self.student_id,),
                ).fetchone()
                if row:
                    return int(row[0])
        except Exception:
            pass
        return None

    def _ensure_tables(self):
        """Create tables that may not yet exist."""
        try:
            with transaction() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS document_requests ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "student_id TEXT, "
                    "document_type TEXT, "
                    "status TEXT DEFAULT 'pending', "
                    "requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                )
        except Exception as exc:
            logger.warning("Could not ensure document-center tables: %s", exc)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Assemble the main layout."""
        # Header
        ttk.Label(
            self.window,
            text="My Documents",
            font=("Helvetica", 16, "bold"),
        ).pack(anchor="w", padx=15, pady=(15, 5))

        # Documents treeview ---------------------------------------------
        doc_frame = ttk.Frame(self.window)
        doc_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        columns = ("title", "file_type", "module_code", "submission_date")
        scrollbar = ttk.Scrollbar(doc_frame, orient=tk.VERTICAL)
        self.doc_tree = ttk.Treeview(
            doc_frame,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.doc_tree.yview)

        self.doc_tree.heading("title", text="Title")
        self.doc_tree.heading("file_type", text="Type")
        self.doc_tree.heading("module_code", text="Module")
        self.doc_tree.heading("submission_date", text="Submitted")

        self.doc_tree.column("title", width=300)
        self.doc_tree.column("file_type", width=140, anchor="center")
        self.doc_tree.column("module_code", width=120, anchor="center")
        self.doc_tree.column("submission_date", width=160, anchor="center")

        self.doc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Internal mapping: treeview iid -> document content
        self._doc_contents = {}

        # Button row -----------------------------------------------------
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Button(btn_frame, text="Request Document", command=self._open_request_dialog).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(btn_frame, text="View Content", command=self._view_selected_document).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_all).pack(side=tk.LEFT)

        # Document Requests section --------------------------------------
        ttk.Label(
            self.window,
            text="Document Requests",
            font=("Helvetica", 12, "bold"),
        ).pack(anchor="w", padx=15, pady=(10, 2))

        req_frame = ttk.Frame(self.window)
        req_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        req_columns = ("document_type", "status", "requested_at")
        req_scrollbar = ttk.Scrollbar(req_frame, orient=tk.VERTICAL)
        self.req_tree = ttk.Treeview(
            req_frame,
            columns=req_columns,
            show="headings",
            height=5,
            yscrollcommand=req_scrollbar.set,
        )
        req_scrollbar.config(command=self.req_tree.yview)

        self.req_tree.heading("document_type", text="Document Type")
        self.req_tree.heading("status", text="Status")
        self.req_tree.heading("requested_at", text="Requested")

        self.req_tree.column("document_type", width=250)
        self.req_tree.column("status", width=120, anchor="center")
        self.req_tree.column("requested_at", width=180, anchor="center")

        self.req_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        req_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load data
        self._load_documents()
        self._load_requests()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_documents(self):
        """Populate the documents treeview."""
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)
        self._doc_contents.clear()

        author_int_id = self._get_user_int_id()
        if author_int_id is None:
            self.doc_tree.insert(
                "", tk.END, values=("Could not determine user ID.", "", "", "")
            )
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, title, file_type, module_code, submission_date, content "
                    "FROM document_repository "
                    "WHERE author_id = ? "
                    "ORDER BY submission_date DESC",
                    (author_int_id,),
                ).fetchall()

            for row in rows:
                title = row[1] if row[1] else ""
                file_type = row[2] if row[2] else ""
                module_code = row[3] if row[3] else ""
                submission_date = row[4] if row[4] else ""
                content = row[5] if row[5] else ""

                iid = self.doc_tree.insert(
                    "", tk.END, values=(title, file_type, module_code, submission_date)
                )
                self._doc_contents[iid] = content

            if not rows:
                self.doc_tree.insert(
                    "", tk.END, values=("No documents found.", "", "", "")
                )

        except Exception as exc:
            logger.warning("Could not load documents: %s", exc)
            self.doc_tree.insert(
                "", tk.END, values=("Unable to load documents.", "", "", "")
            )

    def _load_requests(self):
        """Populate the document requests treeview."""
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT document_type, status, requested_at "
                    "FROM document_requests "
                    "WHERE student_id = ? "
                    "ORDER BY requested_at DESC",
                    (self.student_id,),
                ).fetchall()

            for row in rows:
                doc_type = row[0] if row[0] else ""
                status = row[1] if row[1] else ""
                requested_at = row[2] if row[2] else ""
                self.req_tree.insert("", tk.END, values=(doc_type, status, requested_at))

            if not rows:
                self.req_tree.insert(
                    "", tk.END, values=("No requests submitted.", "", "")
                )

        except Exception as exc:
            logger.warning("Could not load document requests: %s", exc)
            self.req_tree.insert(
                "", tk.END, values=("Unable to load requests.", "", "")
            )

    def _refresh_all(self):
        """Reload both document trees."""
        self._load_documents()
        self._load_requests()

    # ------------------------------------------------------------------
    # Request Document
    # ------------------------------------------------------------------

    def _open_request_dialog(self):
        """Open a dialog to request an official document."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Request Document")
        dialog.geometry("400x200")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text="Document Type:").pack(anchor="w", padx=15, pady=(15, 5))
        type_var = tk.StringVar(value="Enrollment Confirmation")
        ttk.Combobox(
            dialog,
            textvariable=type_var,
            values=[
                "Enrollment Confirmation",
                "Transcript",
                "Financial Statement",
                "Attendance Record",
            ],
            state="readonly",
            width=35,
        ).pack(anchor="w", padx=15)

        def _submit():
            doc_type = type_var.get()
            try:
                with transaction() as conn:
                    conn.execute(
                        "INSERT INTO document_requests "
                        "(student_id, document_type, status, requested_at) "
                        "VALUES (?, ?, 'pending', datetime('now'))",
                        (self.student_id, doc_type),
                    )
                uid = self.auth.current_user.get('id', '') if self.auth and self.auth.current_user else ''
                log_activity(
                    uid,
                    self.student_id,
                    "student",
                    "request_document",
                    "document_center",
                    details=f"Requested document: {doc_type}",
                )
                messagebox.showinfo(
                    "Success",
                    f"Your request for '{doc_type}' has been submitted.",
                    parent=dialog,
                )
                dialog.destroy()
                self._load_requests()
            except Exception as exc:
                logger.error("Failed to request document: %s", exc)
                messagebox.showerror(
                    "Error", f"Could not submit request: {exc}", parent=dialog
                )

        ttk.Button(dialog, text="Submit Request", command=_submit).pack(pady=20)

    # ------------------------------------------------------------------
    # View Document
    # ------------------------------------------------------------------

    def _view_selected_document(self):
        """Show the selected document content in a viewer window."""
        selection = self.doc_tree.selection()
        if not selection:
            messagebox.showinfo(
                "Info", "Please select a document to view.", parent=self.window
            )
            return

        iid = selection[0]
        content = self._doc_contents.get(iid, "")
        title = self.doc_tree.item(iid, "values")[0] if self.doc_tree.item(iid, "values") else "Document"

        if not content:
            messagebox.showinfo(
                "Info", "No content available for this document.", parent=self.window
            )
            return

        viewer = tk.Toplevel(self.window)
        viewer.title(f"Document: {title}")
        viewer.geometry("700x500")
        viewer.transient(self.window)

        from tkinter import scrolledtext as st
        text_widget = st.ScrolledText(viewer, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert("1.0", content)
        text_widget.config(state=tk.DISABLED)

        ttk.Button(viewer, text="Close", command=viewer.destroy).pack(pady=(0, 10))
