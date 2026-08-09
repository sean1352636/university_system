"""Methods process_tasks through generate_reports_gui."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import main_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class PlagiarismCheckerGUI:
    def process_tasks(self):
        """Process background tasks"""
        if self._closing:
            return
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return

        try:
            while True:
                task_type, data = self.task_queue.get_nowait()

                if task_type == 'init_complete':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("System ready")
                    self.load_dashboard_stats()

                elif task_type == 'init_error':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("System initialization failed")
                    messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.initialization_error', default="Initialization Error"), f"Failed to initialize system:\n{data}")

                elif task_type == 'submit_complete':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("Document submitted successfully")
                    doc_id = data
                    messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.success', default="Success"), f"Document submitted successfully!\nDocument ID: {doc_id}")
                    self.load_documents()
                    self.load_dashboard_stats()

                elif task_type == 'submit_error':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("Document submission failed")
                    messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.submission_error', default="Submission Error"), f"Failed to submit document:\n{data}")

                elif task_type == 'check_complete':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("Plagiarism check completed")
                    result = data
                    self.show_check_result(result)
                    self.load_results()

                elif task_type == 'check_error':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("Plagiarism check failed")
                    messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.check_error', default="Check Error"), f"Plagiarism check failed:\n{data}")

        except queue.Empty:
            pass

        # Schedule next check (unless we're tearing down)
        if self._closing:
            return
        try:
            self._task_after_id = self.root.after(100, self.process_tasks)
        except tk.TclError:
            pass

    def show_submit_dialog(self):
        """Show document submission dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = DocumentSubmissionDialog(self.root, self.checker, self.auth, self.task_queue)
        dialog.show()

    def show_check_dialog(self):
        """Show plagiarism check dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = PlagiarismCheckDialog(self.root, self.checker, self.auth, self.task_queue, self.threshold_var.get())
        dialog.show()

    def show_search_dialog(self):
        """Show repository search dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = RepositorySearchDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_statistics(self):
        """Show detailed statistics"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = StatisticsDialog(self.root, self.checker)
        dialog.show()

    def show_advanced_repository_search(self):
        """Show advanced repository search dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = AdvancedRepositorySearchDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_bulk_operations(self):
        """Show bulk operations dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = BulkOperationsDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_system_testing(self):
        """Show system testing dialog"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        dialog = SystemTestingDialog(self.root, self.checker)
        dialog.show()

    def check_repository_integrity_gui(self):
        """GUI version of repository integrity check"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.permission_denied', default="Permission Denied"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.you_don_t_have_permission_to_check_repository_integrity', default="You don't have permission to check repository integrity."))
            return

        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.windows.repository_integrity_check', default="Repository Integrity Check"))
        progress_dialog.geometry("500x300")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        main_frame = ttk.Frame(progress_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("plagiarism.repository_integrity_check"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(main_frame, variable=progress_var, mode='indeterminate')
        progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        progress_bar.start()

        results_text = scrolledtext.ScrolledText(main_frame, height=10, font=GuiConfig.MONOSPACE_FONT)
        results_text.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        def check_integrity():
            try:
                results_text.insert(tk.END, "Starting repository integrity check...\n\n")

                with self.checker.get_db_connection() as conn:
                    cursor = conn.cursor()

                    # Check for orphaned records in plagiarism_results
                    results_text.insert(tk.END, "Checking for orphaned plagiarism results...\n")
                    cursor.execute('''
                    SELECT COUNT(*) FROM plagiarism_results pr
                    LEFT JOIN document_repository dr ON pr.document_id = dr.id
                    WHERE dr.id IS NULL
                    ''')
                    orphaned_results = cursor.fetchone()[0]
                    results_text.insert(tk.END, f"Found {orphaned_results} orphaned plagiarism results.\n")

                    # Check for documents without content
                    results_text.insert(tk.END, "Checking for documents without content...\n")
                    cursor.execute('''
                    SELECT COUNT(*) FROM document_repository
                    WHERE content IS NULL OR content = ''
                    ''')
                    empty_docs = cursor.fetchone()[0]
                    results_text.insert(tk.END, f"Found {empty_docs} documents without content.\n")

                    # Check for documents with invalid authors
                    results_text.insert(tk.END, "Checking for documents with invalid authors...\n")
                    cursor.execute('''
                    SELECT COUNT(*) FROM document_repository dr
                    LEFT JOIN users u ON dr.author_id = u.id
                    WHERE u.id IS NULL
                    ''')
                    invalid_authors = cursor.fetchone()[0]
                    results_text.insert(tk.END, f"Found {invalid_authors} documents with invalid authors.\n")

                    # Check for duplicate content hashes
                    results_text.insert(tk.END, "Checking for duplicate content...\n")
                    cursor.execute('''
                    SELECT content_hash, COUNT(*) as count
                    FROM document_repository
                    GROUP BY content_hash
                    HAVING COUNT(*) > 1
                    ''')
                    duplicates = cursor.fetchall()
                    results_text.insert(tk.END, f"Found {len(duplicates)} sets of duplicate content.\n")

                    total_issues = orphaned_results + empty_docs + invalid_authors + len(duplicates)

                    results_text.insert(tk.END, "\nSummary:\n")
                    results_text.insert(tk.END, f"Total issues found: {total_issues}\n")

                    if total_issues > 0:
                        results_text.insert(tk.END, "\nWould you like to fix these issues?\n")

                        progress_bar.stop()

                        fix_button = ttk.Button(main_frame, text=_t("plagiarism.fix_issues"),
                                              command=lambda: fix_issues(orphaned_results, empty_docs, invalid_authors))
                        fix_button.pack(side=tk.LEFT, pady=GuiConfig.PADDING_MEDIUM)
                    else:
                        results_text.insert(tk.END, "\nRepository is healthy! No issues found.\n")
                        progress_bar.stop()

                    close_button = ttk.Button(main_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.buttons.close', default="Close"), command=progress_dialog.destroy)
                    close_button.pack(side=tk.RIGHT, pady=GuiConfig.PADDING_MEDIUM)

            except Exception as e:
                progress_bar.stop()
                results_text.insert(tk.END, f"\nError during integrity check: {e}\n")
                messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), f"Integrity check failed: {e}")

        def fix_issues(orphaned_results, empty_docs, invalid_authors):
            try:
                if not messagebox.askyesno(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.confirm_fix', default="Confirm Fix"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.this_will_permanently_delete_problematic_records_continue', default="This will permanently delete problematic records. Continue?")):
                    return

                results_text.insert(tk.END, "\nFixing issues...\n")

                with self.checker.get_db_connection() as conn:
                    cursor = conn.cursor()

                    if orphaned_results > 0:
                        cursor.execute('''
                        DELETE FROM plagiarism_results
                        WHERE document_id NOT IN (SELECT id FROM document_repository)
                        ''')
                        results_text.insert(tk.END, f"Deleted {cursor.rowcount} orphaned plagiarism results.\n")

                    if empty_docs > 0:
                        cursor.execute('''
                        DELETE FROM document_repository
                        WHERE content IS NULL OR content = ''
                        ''')
                        results_text.insert(tk.END, f"Deleted {cursor.rowcount} empty documents.\n")

                    if invalid_authors > 0:
                        cursor.execute('''
                        DELETE FROM document_repository
                        WHERE author_id NOT IN (SELECT id FROM users)
                        ''')
                        results_text.insert(tk.END, f"Deleted {cursor.rowcount} documents with invalid authors.\n")

                    conn.commit()
                    results_text.insert(tk.END, "\nAll issues fixed successfully!\n")

            except Exception as e:
                results_text.insert(tk.END, f"\nError fixing issues: {e}\n")
                messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), f"Failed to fix issues: {e}")

        # Start integrity check in a thread
        thread = threading.Thread(target=check_integrity, daemon=True)
        thread.start()

    def generate_reports_gui(self):
        """Generate various system reports"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.system_not_initialized', default="System not initialized"))
            return

        # Create reports dialog
        reports_dialog = tk.Toplevel(self.root)
        reports_dialog.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.windows.generate_reports', default="Generate Reports"))
        reports_dialog.geometry("600x500")
        reports_dialog.transient(self.root)
        reports_dialog.grab_set()

        main_frame = ttk.Frame(reports_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("plagiarism.system_reports"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Report types
        reports_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.available_reports"), padding=GuiConfig.PADDING_MEDIUM)
        reports_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        report_var = tk.StringVar()

        reports = [
            ("Summary Statistics", "summary"),
            ("Plagiarism Trends", "trends"),
            ("Module Analysis", "modules"),
            ("User Activity", "users"),
            ("System Health", "health")
        ]

        for name, value in reports:
            ttk.Radiobutton(reports_frame, text=name, variable=report_var, value=value).pack(anchor=tk.W, pady=GuiConfig.PADDING_SMALL)

        report_var.set("summary")  # Default selection

        # Report options
        options_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.report_options"), padding=GuiConfig.PADDING_MEDIUM)
        options_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text=_t("plagiarism.include_charts_graphs"), variable=include_charts_var).pack(anchor=tk.W)

        export_format_var = tk.StringVar(value=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.values.html', default="html"))
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=GuiConfig.PADDING_SMALL)

        ttk.Label(format_frame, text=_t("plagiarism.export_format")).pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.buttons.html', default="HTML"), variable=export_format_var, value="html").pack(side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0))
        ttk.Radiobutton(format_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.buttons.pdf', default="PDF"), variable=export_format_var, value="pdf").pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.buttons.csv', default="CSV"), variable=export_format_var, value="csv").pack(side=tk.LEFT)

        # Generate button
        def generate_report():
            report_type = report_var.get()
            if not report_type:
                messagebox.showwarning(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.no_selection', default="No Selection"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.please_select_a_report_type', default="Please select a report type."))
                return

            try:
                from tkinter import filedialog

                # Get filename
                format_ext = {"html": ".html", "pdf": ".pdf", "csv": ".csv"}[export_format_var.get()]
                filename = filedialog.asksaveasfilename(
                    defaultextension=format_ext,
                    filetypes=[(f"{export_format_var.get().upper()} files", f"*{format_ext}"), ("All files", "*.*")],
                    title=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.save_report', default="Save Report")
                )

                if filename:
                    # Generate the report (simplified implementation)
                    messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.report_generated', default="Report Generated"), f"Report '{report_type}' would be generated and saved to {filename}")

            except Exception as e:
                messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_process_tasks.dialogs.error', default="Error"), f"Failed to generate report: {e}")

        ttk.Button(main_frame, text=_t("plagiarism.generate_report"), command=generate_report).pack(pady=GuiConfig.PADDING_MEDIUM)

        ttk.Button(main_frame, text=_t("common.close"), command=reports_dialog.destroy).pack()
