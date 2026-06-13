import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.university_system.core.i18n import get_text as _t

from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import logger


class DocumentDetailsDialog:
    """Dialog for showing document details"""

    def __init__(self, parent, checker, doc_id):
        self.parent = parent
        self.checker = checker
        self.doc_id = doc_id

        self.dialog = None
        self.doc_details = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Document Details")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Load and display the document details
        self.load_and_display_details()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab

    def load_and_display_details(self):
        """Load and display document details"""
        def load_task():
            try:
                # Get document details from the checker
                details = self.checker.get_document_details(self.doc_id)

                # Get check history for this document
                check_history = self.checker.get_document_check_history(self.doc_id)

                self.dialog.after(0, lambda d=details, h=check_history: self.create_details_interface(d, h))

            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: self.show_error(err))

        # Show loading message
        loading_label = ttk.Label(self.dialog, text="Loading document details...", font=GuiConfig.BODY_FONT)
        loading_label.pack(expand=True)

        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()

    def create_details_interface(self, details, check_history):
        """Create the details interface"""
        # Clear loading message
        for widget in self.dialog.winfo_children():
            widget.destroy()

        self.doc_details = details

        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.document_details"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Document info tab
        self.create_info_tab(notebook, details)

        # Plagiarism checks tab
        self.create_checks_tab(notebook, check_history)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        close_btn = ttk.Button(button_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack(side=tk.RIGHT)

        check_btn = ttk.Button(button_frame, text=_t("plagiarism.check_for_plagiarism"), command=self.check_plagiarism)
        check_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

    def create_info_tab(self, notebook, details):
        """Create document information tab"""
        info_frame = ttk.Frame(notebook)
        notebook.add(info_frame, text="Information")

        # Create scrollable frame
        canvas = tk.Canvas(info_frame)
        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Basic information
        basic_frame = ttk.LabelFrame(scrollable_frame, text=_t("plagiarism.basic_information"), padding=GuiConfig.PADDING_MEDIUM)
        basic_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        info_items = [
            ("Title:", details['title']),
            ("Author:", details['author_name']),
            ("Module:", details['module_code'] or 'N/A'),
            ("Submission Date:", details['submission_date']),
            ("File Type:", details['file_type']),
            ("Word Count:", str(details['word_count'])),
            ("Created:", details['created_at']),
            ("Last Updated:", details['updated_at'])
        ]

        for i, (label, value) in enumerate(info_items):
            ttk.Label(basic_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
            )
            ttk.Label(basic_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
            )

        # Latest check information
        if details.get('latest_check'):
            check = details['latest_check']
            similarity = check['similarity_score'] * 100

            check_frame = ttk.LabelFrame(scrollable_frame, text=_t("plagiarism.latest_plagiarism_check"), padding=GuiConfig.PADDING_MEDIUM)
            check_frame.pack(fill=tk.X)

            check_items = [
                ("Status:", check['status']),
                ("Similarity Score:", f"{similarity:.1f}%"),
                ("Check Date:", check['check_date']),
                ("Threshold Used:", f"{check['threshold_used']:.1%}")
            ]

            for i, (label, value) in enumerate(check_items):
                ttk.Label(check_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                    row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
                )

                # Color-code status
                if label == "Status:":
                    color = GuiConfig.DANGER_COLOR if check['status'] in ['EXACT_MATCH', 'HIGH_SIMILARITY'] else \
                           GuiConfig.WARNING_COLOR if check['status'] == 'MODERATE_SIMILARITY' else \
                           GuiConfig.SUCCESS_COLOR
                    status_label = tk.Label(check_frame, text=value, font=GuiConfig.BODY_FONT, fg=color)
                    status_label.grid(row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL)
                else:
                    ttk.Label(check_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                        row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
                    )

        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_checks_tab(self, notebook, check_history):
        """Create plagiarism checks tab"""
        checks_frame = ttk.Frame(notebook)
        notebook.add(checks_frame, text=_t("plagiarism.check_history"))

        if not check_history:
            no_checks_label = ttk.Label(
                checks_frame,
                text="No plagiarism checks performed on this document",
                font=GuiConfig.BODY_FONT
            )
            no_checks_label.pack(expand=True)
            return

        # Checks list
        columns = ('Date', 'Status', 'Similarity', 'Threshold')
        checks_tree = ttk.Treeview(checks_frame, columns=columns, show='headings', height=15)

        for col in columns:
            checks_tree.heading(col, text=col)
            checks_tree.column(col, width=150)

        # Populate checks
        for check in check_history:
            similarity = check['similarity_score'] * 100
            threshold = check['threshold_used'] * 100 if check['threshold_used'] else 0

            checks_tree.insert('', tk.END, values=(
                check['check_date'],
                check['status'],
                f"{similarity:.1f}%",
                f"{threshold:.0f}%"
            ), tags=(str(check['result_id']),))

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(checks_frame, orient=tk.VERTICAL, command=checks_tree.yview)
        h_scrollbar = ttk.Scrollbar(checks_frame, orient=tk.HORIZONTAL, command=checks_tree.xview)

        checks_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack elements
        checks_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        checks_frame.grid_rowconfigure(0, weight=1)
        checks_frame.grid_columnconfigure(0, weight=1)

        # Double-click to view details
        def on_check_double_click(event):
            selection = checks_tree.selection()
            if selection:
                item = selection[0]
                result_id = int(checks_tree.item(item, 'tags')[0])
                # This would show detailed results
                messagebox.showinfo("Details", f"Detailed results for check {result_id} would be shown here.")

        checks_tree.bind('<Double-1>', on_check_double_click)

    def check_plagiarism(self):
        """Start plagiarism check for this document"""
        messagebox.showinfo("Info", "Use the main application's Check for Plagiarism feature to check this document.")

    def show_error(self, error):
        """Show error message"""
        # Clear any existing widgets
        for widget in self.dialog.winfo_children():
            widget.destroy()

        error_label = ttk.Label(
            self.dialog,
            text=f"Error loading document details:\n{error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(expand=True)

        close_btn = ttk.Button(self.dialog, text="Close", command=self.dialog.destroy)
        close_btn.pack(pady=GuiConfig.PADDING_MEDIUM)
