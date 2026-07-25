import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.interfaces.gui.academics.plagiarism_main_gui.config import GuiConfig
from education_system.systems.university.interfaces.gui.academics.plagiarism_main_gui.common import logger


class PlagiarismCheckDialog:
    """Dialog for checking documents for plagiarism"""

    def __init__(self, parent, checker, auth, task_queue, threshold):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        self.task_queue = task_queue
        self.threshold = threshold

        self.dialog = None
        self.selected_doc_id = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab

        # Create interface and load documents
        self.create_check_form()
        self.load_documents()

    def create_check_form(self):
        """Create the check form"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.check_document_for_plagiarism"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.search_documents"), padding=GuiConfig.PADDING_SMALL)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)

        search_btn = ttk.Button(search_frame, text="Search", command=self.search_documents)
        search_btn.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)

        refresh_btn = ttk.Button(search_frame, text="Refresh", command=self.load_documents)
        refresh_btn.pack(side=tk.LEFT)

        # Documents list
        list_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.select_document_to_check"), padding=GuiConfig.PADDING_SMALL)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Treeview for documents
        columns = ('Title', 'Author', 'Module', 'Date')
        self.doc_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.doc_tree.heading(col, text=col)
            self.doc_tree.column(col, width=150)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.doc_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.doc_tree.xview)

        self.doc_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack treeview and scrollbars
        self.doc_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.check_settings"), padding=GuiConfig.PADDING_SMALL)
        settings_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(settings_frame, text=_t("plagiarism.similarity_threshold")).pack(side=tk.LEFT)
        self.threshold_var = tk.DoubleVar(value=self.threshold)
        threshold_scale = ttk.Scale(
            settings_frame,
            from_=0.1,
            to=0.9,
            variable=self.threshold_var,
            orient=tk.HORIZONTAL,
            length=200
        )
        threshold_scale.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)

        self.threshold_label = ttk.Label(settings_frame, text=f"{int(self.threshold * 100)}%")
        self.threshold_label.pack(side=tk.LEFT)

        def update_threshold_label(*args):
            self.threshold_label.config(text=f"{int(self.threshold_var.get() * 100)}%")

        self.threshold_var.trace('w', update_threshold_label)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT)

        check_btn = ttk.Button(button_frame, text=_t("plagiarism.check_for_plagiarism"), command=self.start_check)
        check_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

    def load_documents(self):
        """Load documents into the tree"""
        # Clear existing items
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)

        def load_task():
            try:
                # Query documents from database
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT d.id, d.title, u.username as author, d.module_code, d.submission_date
                        FROM document_repository d
                        LEFT JOIN users u ON d.author_id = u.id
                        ORDER BY d.submission_date DESC
                    ''')
                    rows = cursor.fetchall()
                    documents = [dict(row) for row in rows]

                # Update tree in main thread
                self.dialog.after(0, lambda: self.populate_tree(documents))

            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Failed to load documents: {err}"))

        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()

    def search_documents(self):
        """Search documents"""
        search_term = self.search_var.get().strip()

        # Clear existing items
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)

        def search_task():
            try:
                # Search documents in database
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT d.id, d.title, u.username as author, d.module_code, d.submission_date
                        FROM document_repository d
                        LEFT JOIN users u ON d.author_id = u.id
                        WHERE d.title LIKE ? OR u.username LIKE ? OR d.module_code LIKE ?
                        ORDER BY d.submission_date DESC
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                    rows = cursor.fetchall()
                    documents = [dict(row) for row in rows]

                # Update tree in main thread
                self.dialog.after(0, lambda: self.populate_tree(documents))

            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Search failed: {err}"))

        thread = threading.Thread(target=search_task, daemon=True)
        thread.start()

    def populate_tree(self, documents):
        """Populate the tree with documents"""
        for doc in documents:
            try:
                self.doc_tree.insert('', tk.END, values=(
                    doc['title'],
                    doc['author'],
                    doc['module_code'] or 'N/A',
                    doc['submission_date']
                ), tags=(str(doc['id']),))

            except Exception as e:
                logger.error(f"Error adding document {doc['id']} to tree: {e}")

    def start_check(self):
        """Start plagiarism check"""
        selection = self.doc_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a document to check")
            return

        # Get document ID from tags
        item = selection[0]
        doc_id = int(self.doc_tree.item(item, 'tags')[0])

        def check_task():
            try:
                # Perform actual plagiarism check using the checker
                checker_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
                threshold = self.threshold_var.get()

                # Call the plagiarism checker
                result = self.checker.check_plagiarism(doc_id, checker_id=checker_id, threshold=threshold)

                self.task_queue.put(('check_complete', result))

                # Close dialog in main thread
                self.dialog.after(0, self.dialog.destroy)

            except Exception as e:
                self.task_queue.put(('check_error', str(e)))

        thread = threading.Thread(target=check_task, daemon=True)
        thread.start()
