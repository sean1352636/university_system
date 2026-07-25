import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.interfaces.gui.academics.plagiarism_main_gui.config import GuiConfig
from education_system.systems.university.interfaces.gui.academics.plagiarism_main_gui.common import logger


class DocumentWorkflowDialog:
    """Dialog for managing document workflow states"""

    def __init__(self, parent, checker, auth):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        self.dialog = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Create interface first
        self.create_search_interface()
        self.load_all_documents()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
        self.create_interface()
        self.load_workflow_documents()

    def create_interface(self):
        """Create the workflow interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.document_workflow_management"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Workflow states filter
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(filter_frame, text="Filter by status:").pack(side=tk.LEFT)

        self.status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.status_filter_var,
                                   values=["All", "Submitted", "Under Review", "Checked", "Flagged", "Approved"],
                                   state='readonly')
        status_combo.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)
        status_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_documents())

        ttk.Button(filter_frame, text="Refresh", command=self.load_workflow_documents).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0))

        # Documents tree
        docs_frame = ttk.LabelFrame(main_frame, text="Documents", padding=GuiConfig.PADDING_SMALL)
        docs_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        columns = ('Title', 'Author', 'Status', 'Last Check', 'Priority', 'Actions')
        self.docs_tree = ttk.Treeview(docs_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.docs_tree.heading(col, text=col)
            self.docs_tree.column(col, width=120)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(docs_frame, orient=tk.VERTICAL, command=self.docs_tree.yview)
        h_scrollbar = ttk.Scrollbar(docs_frame, orient=tk.HORIZONTAL, command=self.docs_tree.xview)

        self.docs_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.docs_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        docs_frame.grid_rowconfigure(0, weight=1)
        docs_frame.grid_columnconfigure(0, weight=1)

        # Workflow actions
        actions_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.workflow_actions"), padding=GuiConfig.PADDING_MEDIUM)
        actions_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Button(actions_frame, text=_t("plagiarism.mark_for_review"), command=self.mark_for_review).pack(side=tk.LEFT)
        ttk.Button(actions_frame, text=_t("plagiarism.approve_document"), command=self.approve_document).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(actions_frame, text=_t("plagiarism.flag_document"), command=self.flag_document).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(actions_frame, text=_t("plagiarism.add_comment"), command=self.add_comment).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def load_workflow_documents(self):
        """Load documents for workflow management"""
        try:
            # Clear existing items
            for item in self.docs_tree.get_children():
                self.docs_tree.delete(item)

            documents = self.checker.search_repository()

            for doc in documents:
                try:
                    doc_details = self.checker.get_document_details(doc['id'])

                    # Determine workflow status
                    status = "Submitted"
                    last_check = "Never"

                    if doc_details.get('latest_check'):
                        check = doc_details['latest_check']
                        last_check = check['check_date']

                        if check['status'] in ['EXACT_MATCH', 'HIGH_SIMILARITY']:
                            status = "Flagged"
                        elif check['status'] in ['MODERATE_SIMILARITY', 'LOW_SIMILARITY']:
                            status = "Checked"
                        else:
                            status = "Under Review"

                    # Determine priority (placeholder logic)
                    priority = "Normal"
                    if status == "Flagged":
                        priority = "High"
                    elif status == "Under Review":
                        priority = "Medium"

                    self.docs_tree.insert('', tk.END, values=(
                        doc['title'][:40] + ('...' if len(doc['title']) > 40 else ''),
                        doc_details.get('author_name', 'Unknown'),
                        status,
                        last_check,
                        priority,
                        "Available"
                    ), tags=(str(doc['id']),))

                except Exception as e:
                    logger.error(f"Error loading document {doc['id']}: {e}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load documents: {e}")

    def filter_documents(self):
        """Filter documents by status"""
        filter_status = self.status_filter_var.get()

        # This would implement filtering logic
        # For now, just reload all documents
        if filter_status == "All":
            self.load_workflow_documents()
        else:
            # Placeholder - would filter by actual status
            messagebox.showinfo("Filter", f"Filtering by status: {filter_status}")

    def get_selected_document(self):
        """Get the selected document ID"""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document.")
            return None

        item = selection[0]
        return int(self.docs_tree.item(item, 'tags')[0])

    def mark_for_review(self):
        """Mark document for review"""
        doc_id = self.get_selected_document()
        if doc_id:
            # This would update document status in database
            messagebox.showinfo("Action", f"Document {doc_id} marked for review.")
            self.load_workflow_documents()

    def approve_document(self):
        """Approve document"""
        doc_id = self.get_selected_document()
        if doc_id:
            if messagebox.askyesno("Confirm", "Approve this document?"):
                messagebox.showinfo("Action", f"Document {doc_id} approved.")
                self.load_workflow_documents()

    def flag_document(self):
        """Flag document for attention"""
        doc_id = self.get_selected_document()
        if doc_id:
            reason = simpledialog.askstring("Flag Document", "Reason for flagging:")
            if reason:
                messagebox.showinfo("Action", f"Document {doc_id} flagged: {reason}")
                self.load_workflow_documents()

    def add_comment(self):
        """Add comment to document"""
        doc_id = self.get_selected_document()
        if doc_id:
            comment = simpledialog.askstring("Add Comment", "Enter comment:")
            if comment:
                messagebox.showinfo("Action", f"Comment added to document {doc_id}")
