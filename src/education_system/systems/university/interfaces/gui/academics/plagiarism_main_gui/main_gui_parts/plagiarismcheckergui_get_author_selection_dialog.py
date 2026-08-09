"""Methods get_author_selection_dialog through update_documents_display."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import main_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class PlagiarismCheckerGUI:
    def get_author_selection_dialog(self, checker, author_name):
        """Dialog for selecting author from search results"""
        try:
            with checker.get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id, first_name, last_name
                FROM users
                WHERE first_name LIKE ? OR last_name LIKE ?
                ORDER BY last_name, first_name
                ''', (f"%{escape_like(author_name)}%", f"%{escape_like(author_name)}%"))

                authors = cursor.fetchall()

                if not authors:
                    messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.no_results', default="No Results"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.no_authors_found_matching_that_name', default="No authors found matching that name."))
                    return None

                # Create selection dialog
                dialog = tk.Toplevel(self.root)
                dialog.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.windows.select_author', default="Select Author"))
                dialog.geometry("400x300")
                dialog.transient(self.root)
                dialog.grab_set()

                selected_author = tk.IntVar()
                selected_author.set(-1)

                main_frame = ttk.Frame(dialog, padding=GuiConfig.PADDING_MEDIUM)
                main_frame.pack(fill=tk.BOTH, expand=True)

                ttk.Label(main_frame, text=_t("plagiarism.select_author"), font=GuiConfig.SUBHEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))

                # Author list
                for i, author in enumerate(authors):
                    ttk.Radiobutton(
                        main_frame,
                        text=f"{author[1]} {author[2]}",
                        variable=selected_author,
                        value=i
                    ).pack(anchor=tk.W, pady=GuiConfig.PADDING_SMALL)

                # Buttons
                button_frame = ttk.Frame(main_frame)
                button_frame.pack(fill=tk.X, pady=(GuiConfig.PADDING_MEDIUM, 0))

                def on_ok():
                    dialog.destroy()

                def on_cancel():
                    selected_author.set(-1)
                    dialog.destroy()

                ttk.Button(button_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.buttons.cancel', default="Cancel"), command=on_cancel).pack(side=tk.RIGHT)
                ttk.Button(button_frame, text=_t("common.ok"), command=on_ok).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

                dialog.wait_window()

                if selected_author.get() >= 0:
                    return authors[selected_author.get()][0]
                return None

        except Exception as e:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), f"Error selecting author: {e}")
            return None

    def get_module_selection_by_name_dialog(self, checker, module_name):
        """Dialog for selecting module by name from search results"""
        try:
            with checker.get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT module_code, module_name
                FROM modules
                WHERE module_code LIKE ? OR module_name LIKE ?
                ORDER BY module_code
                ''', (f"%{escape_like(module_name)}%", f"%{escape_like(module_name)}%"))

                modules = cursor.fetchall()

                if not modules:
                    messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.no_results', default="No Results"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.no_modules_found_matching_that_name', default="No modules found matching that name."))
                    return None

                # Create selection dialog
                dialog = tk.Toplevel(self.root)
                dialog.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.windows.select_module', default="Select Module"))
                dialog.geometry("500x400")
                dialog.transient(self.root)
                dialog.grab_set()

                selected_module = tk.IntVar()
                selected_module.set(-1)

                main_frame = ttk.Frame(dialog, padding=GuiConfig.PADDING_MEDIUM)
                main_frame.pack(fill=tk.BOTH, expand=True)

                ttk.Label(main_frame, text=_t("plagiarism.select_module"), font=GuiConfig.SUBHEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))

                # Module list with scrollbar
                list_frame = ttk.Frame(main_frame)
                list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

                scrollbar = ttk.Scrollbar(list_frame)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                module_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
                module_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.config(command=module_listbox.yview)

                for module in modules:
                    module_listbox.insert(tk.END, f"{module[0]} - {module[1]}")

                # Buttons
                button_frame = ttk.Frame(main_frame)
                button_frame.pack(fill=tk.X)

                def on_ok():
                    selection = module_listbox.curselection()
                    if selection:
                        selected_module.set(selection[0])
                    dialog.destroy()

                def on_cancel():
                    selected_module.set(-1)
                    dialog.destroy()

                ttk.Button(button_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.buttons.cancel', default="Cancel"), command=on_cancel).pack(side=tk.RIGHT)
                ttk.Button(button_frame, text=_t("common.ok"), command=on_ok).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

                dialog.wait_window()

                if selected_module.get() >= 0:
                    return modules[selected_module.get()][0]
                return None

        except Exception as e:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), f"Error selecting module: {e}")
            return None

    def show_setup_testing(self):
        """Show setup and testing dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = SetupTestingDialog(self.root, self.checker)
        dialog.show()

    def show_about(self):
        """Show about dialog"""
        about_text = """Plagiarism Detection System v2.0

A comprehensive tool for detecting plagiarism in academic documents.

Features:
\u2022 Document repository management
\u2022 Advanced similarity detection
\u2022 Multiple file format support
\u2022 Detailed reporting
\u2022 User-friendly GUI interface

Built with Python and Tkinter"""

        messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.about', default="About"), about_text)

    def load_dashboard_stats(self):
        """Load dashboard statistics"""
        if not self.checker:
            return

        def load_stats():
            try:
                stats = self.checker.get_statistics()

                stats_text = f"""System Statistics (Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

Repository Overview:
  Total Documents: {stats.get('total_documents', 0)}
  Total Checks Performed: {stats.get('total_checks', 0)}

Check Results by Status:"""

                for status, count in stats.get('status_counts', {}).items():
                    stats_text += f"\n  {status}: {count}"

                stats_text += "\n\nDocuments by Module:"
                for module, count in stats.get('documents_by_module', {}).items():
                    stats_text += f"\n  {module}: {count}"

                if stats.get('recent_checks'):
                    stats_text += "\n\nRecent Checks:"
                    for check in stats['recent_checks'][:5]:
                        similarity = check['similarity_score'] * 100
                        stats_text += f"\n  {check['document_title']} - {check['status']} ({similarity:.1f}%)"

                # Update GUI in main thread
                self.root.after(0, lambda: self.update_stats_display(stats_text))

            except Exception as e:
                error_text = f"Error loading statistics: {e}"
                self.root.after(0, lambda: self.update_stats_display(error_text))

        thread = threading.Thread(target=load_stats, daemon=True)
        thread.start()

    def update_stats_display(self, text):
        """Update statistics display"""
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, text)
        self.stats_text.config(state=tk.DISABLED)

    def load_documents(self):
        """Load documents list"""
        if not self.checker:
            return

        def load_docs():
            try:
                documents = self.checker.search_repository()
                self.root.after(0, lambda: self.update_documents_display(documents))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.show_error_in_documents(error_msg))

        thread = threading.Thread(target=load_docs, daemon=True)
        thread.start()

    def show_document_comparison(self):
        """Show document comparison dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = DocumentComparisonDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_file_converter(self):
        """Show file format converter dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = FileFormatConverterDialog(self.root, self.checker)
        dialog.show()

    def show_backup_restore(self):
        """Show backup/restore dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = BackupRestoreDialog(self.root, self.checker)
        dialog.show()

    def show_document_workflow(self):
        """Show document workflow management dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.system_not_initialized', default="System not initialized"))
            return

        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.permission_denied', default="Permission Denied"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.you_don_t_have_permission_to_manage_document_workflows', default="You don't have permission to manage document workflows."))
            return

        dialog = DocumentWorkflowDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_document_history(self, doc_id):
        """Show comprehensive document history"""
        try:
            # Create history dialog
            history_dialog = tk.Toplevel(self.root)
            history_dialog.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.windows.document_history', default="Document History"))
            history_dialog.geometry("700x500")
            history_dialog.transient(self.root)
            history_dialog.grab_set()

            main_frame = ttk.Frame(history_dialog, padding=GuiConfig.PADDING_MEDIUM)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Get document details
            doc_details = self.checker.get_document_details(doc_id)

            ttk.Label(main_frame, text=f"History: {doc_details['title']}", font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))

            # History notebook
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

            # Submission history tab
            submission_frame = ttk.Frame(notebook)
            notebook.add(submission_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.tabs.submission', default="Submission"))

            submission_info = f"""Document Information:
    Title: {doc_details['title']}
    Author: {doc_details.get('author_name', 'Unknown')}
    Module: {doc_details.get('module_code', 'N/A')}
    Submitted: {doc_details['submission_date']}
    File Type: {doc_details.get('file_type', 'Unknown')}
    Word Count: {doc_details.get('word_count', 0)}
    Created: {doc_details['created_at']}
    Last Updated: {doc_details['updated_at']}"""

            submission_text = scrolledtext.ScrolledText(submission_frame, height=15, font=GuiConfig.MONOSPACE_FONT, state=tk.DISABLED)
            submission_text.pack(fill=tk.BOTH, expand=True)
            submission_text.config(state=tk.NORMAL)
            submission_text.insert(1.0, submission_info)
            submission_text.config(state=tk.DISABLED)

            # Check history tab
            checks_frame = ttk.Frame(notebook)
            notebook.add(checks_frame, text=_t("plagiarism.plagiarism_checks"))

            try:
                check_history = self.checker.get_document_check_history(doc_id)

                checks_text = scrolledtext.ScrolledText(checks_frame, height=15, font=GuiConfig.MONOSPACE_FONT, state=tk.DISABLED)
                checks_text.pack(fill=tk.BOTH, expand=True)
                checks_text.config(state=tk.NORMAL)

                if check_history:
                    checks_text.insert(tk.END, "Plagiarism Check History:\n" + "="*50 + "\n\n")
                    for i, check in enumerate(check_history, 1):
                        similarity = check['similarity_score'] * 100
                        threshold = check.get('threshold_used', 0) * 100

                        check_info = f"""Check #{i}:
    Date: {check['check_date']}
    Status: {check['status']}
    Similarity Score: {similarity:.1f}%
    Threshold Used: {threshold:.0f}%
    Result ID: {check['result_id']}

    """
                        checks_text.insert(tk.END, check_info)
                else:
                    checks_text.insert(tk.END, "No plagiarism checks performed on this document.")

                checks_text.config(state=tk.DISABLED)

            except Exception as e:
                messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), f"Failed to load check history: {e}")

            ttk.Button(main_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.buttons.close', default="Close"), command=history_dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), f"Failed to show document history: {e}")

    def launch_external_viewer(self, file_path):
        """Launch external application to view file"""
        try:
            import subprocess
            import platform

            system = platform.system()

            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            elif system == "Linux":
                subprocess.run(["xdg-open", file_path])
            else:
                messagebox.showwarning(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.unsupported_platform', default="Unsupported Platform"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.cannot_launch_external_viewer_on_this_platform', default="Cannot launch external viewer on this platform."))

        except Exception as e:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.dialogs.error', default="Error"), f"Failed to launch external viewer: {e}")

    def search_documents(self):
        """Search documents"""
        if not self.checker:
            return

        search_term = self.doc_search_var.get().strip()

        def search_docs():
            try:
                documents = self.checker.search_repository(search_term)
                self.root.after(0, lambda: self.update_documents_display(documents))
            except Exception as e:
                self.root.after(0, lambda error=str(e): self.show_error_in_documents(error))

        thread = threading.Thread(target=search_docs, daemon=True)
        thread.start()

    def update_documents_display(self, documents):
        """Update documents display"""
        # Clear existing widgets
        for widget in self.documents_frame.scrollable_frame.winfo_children():
            widget.destroy()

        if not documents:
            no_docs_label = ttk.Label(
                self.documents_frame.scrollable_frame,
                text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_get_author_selection_dialog.labels.no_documents_found', default="No documents found"),
                font=GuiConfig.BODY_FONT
            )
            no_docs_label.pack(pady=GuiConfig.PADDING_LARGE)
            return

        for doc in documents:
            doc_card = self.create_document_card(doc)
            doc_card.pack(fill=tk.X, pady=GuiConfig.PADDING_SMALL)
