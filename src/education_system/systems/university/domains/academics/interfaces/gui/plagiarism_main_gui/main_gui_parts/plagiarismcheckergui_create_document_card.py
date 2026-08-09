"""Methods create_document_card through import_documents."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import main_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class PlagiarismCheckerGUI:
    def create_document_card(self, doc):
        """Create a document card widget"""
        card_frame = ttk.LabelFrame(
            self.documents_frame.scrollable_frame,
            text=doc['title'],
            padding=GuiConfig.PADDING_SMALL
        )

        # Document info
        info_frame = ttk.Frame(card_frame)
        info_frame.pack(fill=tk.X)

        # Left side - document details
        details_frame = ttk.Frame(info_frame)
        details_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(
            details_frame,
            text=f"Submitted: {doc['submission_date']} | Type: {doc['file_type']} | Words: {doc['word_count']}",
            font=GuiConfig.BODY_FONT
        ).pack(anchor=tk.W)

        # Right side - actions
        actions_frame = ttk.Frame(info_frame)
        actions_frame.pack(side=tk.RIGHT)

        view_btn = ttk.Button(
            actions_frame,
            text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.buttons.view_details', default="View Details"),
            command=lambda: self.show_document_details(doc['id'])
        )
        view_btn.pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_SMALL))

        check_btn = ttk.Button(
            actions_frame,
            text=_t("plagiarism.check_plagiarism"),
            command=lambda: self.quick_plagiarism_check(doc['id'])
        )
        check_btn.pack(side=tk.LEFT)

        return card_frame

    def show_error_in_documents(self, error):
        """Show error in documents tab"""
        for widget in self.documents_frame.scrollable_frame.winfo_children():
            widget.destroy()

        error_label = ttk.Label(
            self.documents_frame.scrollable_frame,
            text=f"Error loading documents: {error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(pady=GuiConfig.PADDING_LARGE)

    def load_results(self):
        """Load plagiarism check results"""
        if not self.checker:
            return

        def load_res():
            try:
                # Get all documents and their check results
                documents = self.checker.search_repository()
                results = []

                for doc in documents:
                    try:
                        details = self.checker.get_document_details(doc['id'])
                        if details.get('latest_check'):
                            check_data = details['latest_check']
                            result = {
                                'document_title': doc['title'],
                                'document_id': doc['id'],
                                'result_id': check_data['result_id'],
                                'similarity_score': check_data['similarity_score'],
                                'status': check_data['status'],
                                'check_date': check_data['check_date']
                            }
                            results.append(result)
                    except Exception:
                        continue

                self.root.after(0, lambda: self.update_results_display(results))
            except Exception as e:
                self.root.after(0, lambda error=str(e): self.show_error_in_results(error))

        thread = threading.Thread(target=load_res, daemon=True)
        thread.start()

    def update_results_display(self, results):
        """Update results display"""
        # Clear existing widgets
        for widget in self.results_frame.scrollable_frame.winfo_children():
            widget.destroy()

        if not results:
            no_results_label = ttk.Label(
                self.results_frame.scrollable_frame,
                text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.labels.no_plagiarism_check_results_found', default="No plagiarism check results found"),
                font=GuiConfig.BODY_FONT
            )
            no_results_label.pack(pady=GuiConfig.PADDING_LARGE)
            return

        # Sort results by check date (most recent first)
        results.sort(key=lambda x: x['check_date'], reverse=True)

        for result in results:
            result_card = ResultCard(
                self.results_frame.scrollable_frame,
                result,
                on_view_details=self.show_result_details,
                on_email_result=self.send_plagiarism_report_via_email,
                auth=self.auth
            )
            result_card.pack(fill=tk.X, pady=GuiConfig.PADDING_SMALL)

    def show_error_in_results(self, error):
        """Show error in results tab"""
        for widget in self.results_frame.scrollable_frame.winfo_children():
            widget.destroy()

        error_label = ttk.Label(
            self.results_frame.scrollable_frame,
            text=f"Error loading results: {error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(pady=GuiConfig.PADDING_LARGE)

    def load_system_info(self):
        """Load system information"""
        info_text = f"""System Information

Application: Plagiarism Detection System v2.0
GUI Framework: Tkinter
Python Version: {sys.version}

Components:
\u2022 Document Repository: SQLite Database
\u2022 Text Processing: NLTK (if available)
\u2022 File Support: textract (if available)
\u2022 Similarity Algorithm: N-gram Jaccard Similarity

Database Location: {_paths.DEFAULT_DB_PATH}
Log Directory: {_paths.LOG_DIR}

System Status: {"Ready" if self.checker else "Not Initialized"}
Authentication: Mock Auth (GUI Mode)

Features Enabled:
\u2022 Document Submission \u2713
\u2022 Plagiarism Detection \u2713
\u2022 Repository Search \u2713
\u2022 Statistical Reports \u2713
\u2022 GUI Interface \u2713

For command-line interface, run the original plagiarism_main.py file.
"""

        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info_text)
        self.info_text.config(state=tk.DISABLED)

    def show_document_details(self, doc_id):
        """Show detailed document information"""
        dialog = DocumentDetailsDialog(self.root, self.checker, doc_id)
        dialog.show()

    def quick_plagiarism_check(self, doc_id):
        """Quick plagiarism check for a document"""
        if not self.checker or not self.auth:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.dialogs.system_not_ready', default="System not ready"))
            return

        def check_task():
            try:
                self.status_bar.set_status("Checking document for plagiarism...")
                self.status_bar.show_progress()

                result = self.checker.check_plagiarism(
                    doc_id,
                    self.auth.current_user['id'],
                    self.threshold_var.get()
                )

                self.task_queue.put(('check_complete', result))

            except Exception as e:
                self.task_queue.put(('check_error', str(e)))

        thread = threading.Thread(target=check_task, daemon=True)
        thread.start()

    def import_documents(self):
        """Import documents from external files"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.dialogs.system_not_initialized', default="System not initialized"))
            return

        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.dialogs.permission_denied', default="Permission Denied"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.dialogs.you_don_t_have_permission_to_import_documents', default="You don't have permission to import documents."))
            return

        # File dialog to select documents
        filenames = filedialog.askopenfilenames(
            title=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.dialogs.select_documents_to_import', default="Select Documents to Import"),
            filetypes=[
                ("Text files", "*.txt"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.docx"),
                ("All supported files", "*.txt *.pdf *.docx"),
                ("All files", "*.*")
            ]
        )

        if not filenames:
            return

        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.windows.import_documents', default="Import Documents"))
        progress_dialog.geometry("600x400")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        main_frame = ttk.Frame(progress_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("plagiarism.import_documents"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(main_frame, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        status_var = tk.StringVar(value=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.values.preparing_import', default="Preparing import..."))
        ttk.Label(main_frame, textvariable=status_var).pack()

        results_text = scrolledtext.ScrolledText(main_frame, height=15, font=GuiConfig.MONOSPACE_FONT)
        results_text.pack(fill=tk.BOTH, expand=True, pady=(GuiConfig.PADDING_MEDIUM, 0))

        def import_task():
            try:
                total = len(filenames)
                imported = 0
                failed = 0

                for i, filename in enumerate(filenames):
                    try:
                        progress_dialog.after(0, lambda f=filename: status_var.set(f"Processing: {os.path.basename(f)}"))
                        progress_dialog.after(0, lambda p=(i/total)*100: progress_var.set(p))

                        # Extract text from file
                        file_ext = os.path.splitext(filename)[1].lower()

                        if file_ext == '.txt':
                            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                        elif file_ext in ['.pdf', '.docx'] and TEXTRACT_AVAILABLE:
                            try:
                                content = textract.process(filename).decode('utf-8', errors='ignore')
                            except Exception as e:
                                progress_dialog.after(0, lambda f=filename, e=e: results_text.insert(tk.END, f"Failed to extract from {os.path.basename(f)}: {e}\n"))
                                failed += 1
                                continue
                        else:
                            progress_dialog.after(0, lambda f=filename: results_text.insert(tk.END, f"Unsupported file type: {os.path.basename(f)}\n"))
                            failed += 1
                            continue

                        # Get document title from filename
                        title = os.path.splitext(os.path.basename(filename))[0]

                        # Get file type
                        file_type = file_ext[1:].upper() if file_ext else 'TXT'

                        # Add document to repository
                        doc_id = self.checker.add_document_to_repository(
                            title=title,
                            content=content,
                            author_id=self.auth.current_user['id'],
                            module_code='IMPORTED',
                            file_type=file_type
                        )

                        if doc_id:
                            progress_dialog.after(0, lambda t=title: results_text.insert(tk.END, f"Successfully imported: {t}\n"))
                            imported += 1
                        else:
                            progress_dialog.after(0, lambda t=title: results_text.insert(tk.END, f"Failed to import: {t}\n"))
                            failed += 1

                    except Exception as e:
                        progress_dialog.after(0, lambda f=filename, e=e: results_text.insert(tk.END, f"Error importing {os.path.basename(f)}: {e}\n"))
                        failed += 1

                progress_dialog.after(0, lambda: progress_var.set(100))
                progress_dialog.after(0, lambda: status_var.set("Import complete"))
                progress_dialog.after(0, lambda: results_text.insert(tk.END, f"\nSummary: {imported} imported, {failed} failed\n"))

                # Add close button
                progress_dialog.after(0, lambda: ttk.Button(main_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.buttons.close', default="Close"), command=progress_dialog.destroy).pack(pady=(GuiConfig.PADDING_MEDIUM, 0)))

                # Refresh documents list if available
                if hasattr(self, 'load_documents'):
                    progress_dialog.after(0, self.load_documents)

            except Exception as e:
                error_msg = str(e)
                progress_dialog.after(0, lambda: status_var.set("Import failed"))
                progress_dialog.after(0, lambda err=error_msg: results_text.insert(tk.END, f"\nError: {err}\n"))
                progress_dialog.after(0, lambda err=error_msg: messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_create_document_card.dialogs.error', default="Error"), f"Import failed: {err}"))

        thread = threading.Thread(target=import_task, daemon=True)
        thread.start()
