import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import logger


class CheckResultDialog:
    """Dialog for showing plagiarism check results"""

    def __init__(self, parent, checker, result, auth=None, on_email_result=None):
        self.parent = parent
        self.checker = checker
        self.result = result
        self.auth = auth
        self.on_email_result = on_email_result

        self.dialog = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Plagiarism Check Result")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab

        self.create_result_interface()

    def create_result_interface(self):
        """Create the result interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.plagiarism_check_result"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Result summary
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding=GuiConfig.PADDING_MEDIUM)
        summary_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Status
        status = self.result.get('status', 'UNKNOWN')
        similarity = self.result.get('highest_similarity', 0) * 100

        # Determine color based on status
        if status in ['EXACT_MATCH', 'HIGH_SIMILARITY']:
            status_color = GuiConfig.DANGER_COLOR
            status_icon = "⚠️ HIGH RISK"
        elif status == 'MODERATE_SIMILARITY':
            status_color = GuiConfig.WARNING_COLOR
            status_icon = "⚠️ MODERATE RISK"
        else:
            status_color = GuiConfig.SUCCESS_COLOR
            status_icon = "✅ LOW RISK"

        status_frame = ttk.Frame(summary_frame)
        status_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(status_frame, text="Status:", font=GuiConfig.SUBHEADER_FONT).pack(side=tk.LEFT)

        status_label = tk.Label(
            status_frame,
            text=f"{status_icon} - {status}",
            font=GuiConfig.SUBHEADER_FONT,
            fg=status_color
        )
        status_label.pack(side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0))

        # Similarity score
        similarity_frame = ttk.Frame(summary_frame)
        similarity_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(similarity_frame, text=_t("plagiarism.highest_similarity"), font=GuiConfig.SUBHEADER_FONT).pack(side=tk.LEFT)
        ttk.Label(similarity_frame, text=f"{similarity:.1f}%", font=GuiConfig.BODY_FONT).pack(
            side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0)
        )

        # Threshold used
        threshold = self.result.get('threshold_used', 0) * 100
        threshold_frame = ttk.Frame(summary_frame)
        threshold_frame.pack(fill=tk.X)

        ttk.Label(threshold_frame, text=_t("plagiarism.threshold_used"), font=GuiConfig.SUBHEADER_FONT).pack(side=tk.LEFT)
        ttk.Label(threshold_frame, text=f"{threshold:.0f}%", font=GuiConfig.BODY_FONT).pack(
            side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0)
        )

        # Matches
        if self.result.get('matches'):
            matches_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.similar_documents"), padding=GuiConfig.PADDING_SMALL)
            matches_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

            # Matches tree
            columns = ('Document', 'Similarity')
            matches_tree = ttk.Treeview(matches_frame, columns=columns, show='headings', height=10)

            matches_tree.heading('Document', text='Document Title')
            matches_tree.heading('Similarity', text='Similarity Score')

            matches_tree.column('Document', width=400)
            matches_tree.column('Similarity', width=150)

            # Populate matches
            for match_id, match_title, match_similarity in self.result['matches']:
                match_percentage = match_similarity * 100
                matches_tree.insert('', tk.END, values=(
                    match_title,
                    f"{match_percentage:.1f}%"
                ), tags=(str(match_id),))

            # Scrollbar
            matches_scrollbar = ttk.Scrollbar(matches_frame, orient=tk.VERTICAL, command=matches_tree.yview)
            matches_tree.configure(yscrollcommand=matches_scrollbar.set)

            # Pack
            matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            matches_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        close_btn = ttk.Button(button_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack(side=tk.RIGHT)

        if self.on_email_result:
            email_btn = ttk.Button(
                button_frame,
                text=_t("plagiarism.email_results"),
                command=self._email_result
            )
            email_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

        if self.result.get('result_id'):
            details_btn = ttk.Button(
                button_frame,
                text=_t("plagiarism.view_full_report"),
                command=self.view_full_report
            )
            details_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

    def _email_result(self):
        """Email this result to the current user"""
        user_email = None
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user_email = self.auth.current_user.get('email')

        if not user_email:
            messagebox.showwarning(
                _t("common.warning"),
                _t("plagiarism.email_no_user_email")
            )
            return

        result_data = {
            'result_id': self.result.get('result_id', 'Unknown'),
            'similarity_score': (self.result.get('highest_similarity', 0) * 100),
            'document_name': self.result.get('document_title', 'Unknown Document'),
        }
        self.on_email_result(result_data, user_email)

    def view_full_report(self):
        """View full detailed report"""
        if self.result.get('result_id'):
            details_dialog = ResultDetailsDialog(self.dialog, self.checker, self.result['result_id'],
                                                 auth=self.auth,
                                                 on_email_result=self.on_email_result)
            details_dialog.show()


class ResultDetailsDialog:
    """Dialog for showing detailed plagiarism result information"""

    def __init__(self, parent, checker, result_id, auth=None, on_email_result=None):
        self.parent = parent
        self.checker = checker
        self.result_id = result_id
        self.auth = auth
        self.on_email_result = on_email_result
        self._result_cache = None

        self.dialog = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Plagiarism Result Details")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Load and display the result details
        self.load_and_display_details()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab

    def load_and_display_details(self):
        """Load and display detailed results"""
        def load_task():
            try:
                result = self.checker.get_plagiarism_result(self.result_id)
                self.dialog.after(0, lambda: self.create_details_interface(result))

            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: self.show_error(err))

        # Show loading message
        loading_label = ttk.Label(self.dialog, text="Loading detailed report...", font=GuiConfig.BODY_FONT)
        loading_label.pack(expand=True)

        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()

    def create_details_interface(self, result):
        """Create the details interface"""
        self._result_cache = result

        # Clear loading message
        for widget in self.dialog.winfo_children():
            widget.destroy()

        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.detailed_plagiarism_report"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Document information
        doc_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.document_information"), padding=GuiConfig.PADDING_MEDIUM)
        doc_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        doc_info = [
            ("Document:", result['document_title']),
            ("Author:", result['author_name'] or 'Unknown'),
            ("Check Date:", result['check_date']),
            ("Checked By:", result['checker_name'] or 'Unknown')
        ]

        for i, (label, value) in enumerate(doc_info):
            ttk.Label(doc_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
            )
            ttk.Label(doc_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
            )

        # Results summary
        results_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.check_results"), padding=GuiConfig.PADDING_MEDIUM)
        results_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        similarity = result['similarity_score'] * 100
        threshold = result['threshold_used'] * 100

        results_info = [
            ("Status:", result['status']),
            ("Similarity Score:", f"{similarity:.1f}%"),
            ("Threshold Used:", f"{threshold:.0f}%")
        ]

        if result.get('matched_document_title'):
            results_info.append(("Matched Document:", result['matched_document_title']))

        for i, (label, value) in enumerate(results_info):
            ttk.Label(results_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
            )

            if label == "Status:":
                color = GuiConfig.DANGER_COLOR if result['status'] in ['EXACT_MATCH', 'HIGH_SIMILARITY'] else \
                       GuiConfig.WARNING_COLOR if result['status'] == 'MODERATE_SIMILARITY' else \
                       GuiConfig.SUCCESS_COLOR
                status_label = tk.Label(results_frame, text=value, font=GuiConfig.BODY_FONT, fg=color)
                status_label.grid(row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL)
            else:
                ttk.Label(results_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                    row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
                )

        # Detailed report
        if result.get('report'):
            report_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.detailed_report"), padding=GuiConfig.PADDING_SMALL)
            report_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

            report_text = scrolledtext.ScrolledText(
                report_frame,
                height=10,
                font=GuiConfig.MONOSPACE_FONT,
                state=tk.DISABLED,
                wrap=tk.WORD
            )
            report_text.pack(fill=tk.BOTH, expand=True)

            report_text.config(state=tk.NORMAL)
            report_text.insert(1.0, result['report'])
            report_text.config(state=tk.DISABLED)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        close_btn = ttk.Button(button_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack(side=tk.RIGHT)

        if self.on_email_result:
            email_btn = ttk.Button(
                button_frame,
                text=_t("plagiarism.email_results"),
                command=self._email_result
            )
            email_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

        if result.get('matched_document_id'):
            view_match_btn = ttk.Button(
                button_frame,
                text=_t("plagiarism.view_matched_document"),
                command=lambda: self.view_matched_document(result['matched_document_id'])
            )
            view_match_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

    def _email_result(self):
        """Email this result to the current user"""
        user_email = None
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user_email = self.auth.current_user.get('email')

        if not user_email:
            messagebox.showwarning(
                _t("common.warning"),
                _t("plagiarism.email_no_user_email")
            )
            return

        result = self._result_cache or {}
        result_data = {
            'result_id': result.get('result_id', self.result_id),
            'similarity_score': (result.get('similarity_score', 0) * 100),
            'document_name': result.get('document_title', 'Unknown Document'),
        }
        self.on_email_result(result_data, user_email)

    def view_matched_document(self, doc_id):
        """View the matched document"""
        from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.document_details import DocumentDetailsDialog
        details_dialog = DocumentDetailsDialog(self.dialog, self.checker, doc_id)
        details_dialog.show()

    def show_error(self, error):
        """Show error message"""
        # Clear any existing widgets
        for widget in self.dialog.winfo_children():
            widget.destroy()

        error_label = ttk.Label(
            self.dialog,
            text=f"Error loading detailed report:\n{error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(expand=True)

        close_btn = ttk.Button(self.dialog, text="Close", command=self.dialog.destroy)
        close_btn.pack(pady=GuiConfig.PADDING_MEDIUM)
