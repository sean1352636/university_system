import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.university_system.core.i18n import get_text as _t

from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import logger


class StatisticsDialog:
    """Dialog for showing system statistics"""

    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker

        self.dialog = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("System Statistics")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Load and display the statistics
        self.load_and_display_statistics()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab

    def load_and_display_statistics(self):
        """Load and display statistics"""
        def load_task():
            try:
                stats = self.checker.get_statistics()
                self.dialog.after(0, lambda: self.create_statistics_interface(stats))

            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: self.show_error(err))

        # Show loading message
        loading_label = ttk.Label(self.dialog, text="Loading statistics...", font=GuiConfig.BODY_FONT)
        loading_label.pack(expand=True)

        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()

    def create_statistics_interface(self, stats):
        """Create the statistics interface"""
        # Clear loading message
        for widget in self.dialog.winfo_children():
            widget.destroy()

        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.system_statistics"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Overview
        overview_frame = ttk.LabelFrame(main_frame, text="Overview", padding=GuiConfig.PADDING_MEDIUM)
        overview_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        overview_info = [
            ("Total Documents:", str(stats.get('total_documents', 0))),
            ("Total Checks:", str(stats.get('total_checks', 0))),
            ("Last Updated:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        ]

        for i, (label, value) in enumerate(overview_info):
            ttk.Label(overview_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
            )
            ttk.Label(overview_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
            )

        # Create notebook for detailed stats
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Status distribution tab
        self.create_status_tab(notebook, stats.get('status_counts', {}))

        # Module distribution tab
        self.create_modules_tab(notebook, stats.get('documents_by_module', {}))

        # Recent checks tab
        self.create_recent_tab(notebook, stats.get('recent_checks', []))

        # Close button
        close_btn = ttk.Button(main_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack()

    def create_status_tab(self, notebook, status_counts):
        """Create status distribution tab"""
        status_frame = ttk.Frame(notebook)
        notebook.add(status_frame, text=_t("plagiarism.check_status"))

        if not status_counts:
            no_data_label = ttk.Label(
                status_frame,
                text="No plagiarism check data available",
                font=GuiConfig.BODY_FONT
            )
            no_data_label.pack(expand=True)
            return

        # Status tree
        columns = ('Status', 'Count', 'Percentage')
        status_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=10)

        for col in columns:
            status_tree.heading(col, text=col)
            status_tree.column(col, width=150)

        # Calculate percentages
        total_checks = sum(status_counts.values())

        for status, count in sorted(status_counts.items()):
            percentage = (count / total_checks * 100) if total_checks > 0 else 0
            status_tree.insert('', tk.END, values=(
                status,
                str(count),
                f"{percentage:.1f}%"
            ))

        # Scrollbar
        status_scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=status_tree.yview)
        status_tree.configure(yscrollcommand=status_scrollbar.set)

        # Pack
        status_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_modules_tab(self, notebook, module_counts):
        """Create module distribution tab"""
        modules_frame = ttk.Frame(notebook)
        notebook.add(modules_frame, text=_t("plagiarism.documents_by_module"))

        if not module_counts:
            no_data_label = ttk.Label(
                modules_frame,
                text="No module data available",
                font=GuiConfig.BODY_FONT
            )
            no_data_label.pack(expand=True)
            return

        # Modules tree
        columns = ('Module', 'Documents', 'Percentage')
        modules_tree = ttk.Treeview(modules_frame, columns=columns, show='headings', height=10)

        for col in columns:
            modules_tree.heading(col, text=col)
            modules_tree.column(col, width=150)

        # Calculate percentages
        total_docs = sum(module_counts.values())

        for module, count in sorted(module_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_docs * 100) if total_docs > 0 else 0
            modules_tree.insert('', tk.END, values=(
                module,
                str(count),
                f"{percentage:.1f}%"
            ))

        # Scrollbar
        modules_scrollbar = ttk.Scrollbar(modules_frame, orient=tk.VERTICAL, command=modules_tree.yview)
        modules_tree.configure(yscrollcommand=modules_scrollbar.set)

        # Pack
        modules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        modules_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_recent_tab(self, notebook, recent_checks):
        """Create recent checks tab"""
        recent_frame = ttk.Frame(notebook)
        notebook.add(recent_frame, text=_t("plagiarism.recent_checks"))

        if not recent_checks:
            no_data_label = ttk.Label(
                recent_frame,
                text="No recent check data available",
                font=GuiConfig.BODY_FONT
            )
            no_data_label.pack(expand=True)
            return

        # Recent checks tree
        columns = ('Document', 'Status', 'Similarity', 'Date')
        recent_tree = ttk.Treeview(recent_frame, columns=columns, show='headings', height=15)

        recent_tree.heading('Document', text='Document Title')
        recent_tree.heading('Status', text='Status')
        recent_tree.heading('Similarity', text='Similarity Score')
        recent_tree.heading('Date', text='Check Date')

        recent_tree.column('Document', width=300)
        recent_tree.column('Status', width=120)
        recent_tree.column('Similarity', width=100)
        recent_tree.column('Date', width=150)

        # Populate recent checks
        for check in recent_checks:
            similarity = check['similarity_score'] * 100
            recent_tree.insert('', tk.END, values=(
                check['document_title'][:50] + ('...' if len(check['document_title']) > 50 else ''),
                check['status'],
                f"{similarity:.1f}%",
                check['check_date']
            ), tags=(str(check['result_id']),))

        # Scrollbars
        recent_v_scrollbar = ttk.Scrollbar(recent_frame, orient=tk.VERTICAL, command=recent_tree.yview)
        recent_h_scrollbar = ttk.Scrollbar(recent_frame, orient=tk.HORIZONTAL, command=recent_tree.xview)

        recent_tree.configure(yscrollcommand=recent_v_scrollbar.set, xscrollcommand=recent_h_scrollbar.set)

        # Pack
        recent_tree.grid(row=0, column=0, sticky='nsew')
        recent_v_scrollbar.grid(row=0, column=1, sticky='ns')
        recent_h_scrollbar.grid(row=1, column=0, sticky='ew')

        recent_frame.grid_rowconfigure(0, weight=1)
        recent_frame.grid_columnconfigure(0, weight=1)

    def show_error(self, error):
        """Show error message"""
        # Clear any existing widgets
        for widget in self.dialog.winfo_children():
            widget.destroy()

        error_label = ttk.Label(
            self.dialog,
            text=f"Error loading statistics:\n{error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(expand=True)

        close_btn = ttk.Button(self.dialog, text="Close", command=self.dialog.destroy)
        close_btn.pack(pady=GuiConfig.PADDING_MEDIUM)
