"""Methods export_documents through _send_email_via_gui."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import main_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class PlagiarismCheckerGUI:
    def export_documents(self):
        """Export documents to external files"""
        if not self.checker:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.system_not_initialized', default="System not initialized"))
            return

        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.permission_denied', default="Permission Denied"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.you_don_t_have_permission_to_export_documents', default="You don't have permission to export documents."))
            return

        # Create selection dialog
        export_dialog = tk.Toplevel(self.root)
        export_dialog.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.windows.export_documents', default="Export Documents"))
        export_dialog.geometry("700x500")
        export_dialog.transient(self.root)
        export_dialog.grab_set()

        main_frame = ttk.Frame(export_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("plagiarism.export_documents"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(search_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.labels.search', default="Search:")).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Documents list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        columns = ('id', 'title', 'author', 'date')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', selectmode='extended')
        tree.heading('#0', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.select', default='Select'))
        tree.heading('id', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.id', default='ID'))
        tree.heading('title', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.title', default='Title'))
        tree.heading('author', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.author', default='Author'))
        tree.heading('date', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.date', default='Date'))

        tree.column('#0', width=50)
        tree.column('id', width=80)
        tree.column('title', width=250)
        tree.column('author', width=150)
        tree.column('date', width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load documents
        def load_docs():
            try:
                documents = self.checker.search_repository()
                tree.delete(*tree.get_children())

                for doc in documents:
                    tree.insert('', tk.END, text='', values=(
                        doc['id'],
                        doc['title'],
                        doc.get('author_name', 'Unknown'),
                        doc.get('created_at', 'N/A')
                    ))
            except Exception as e:
                messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), f"Failed to load documents: {e}")

        # Format selection
        format_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.export_format"), padding=GuiConfig.PADDING_SMALL)
        format_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        format_var = tk.StringVar(value=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.values.txt', default="txt"))
        ttk.Radiobutton(format_frame, text=_t("plagiarism.text_files"), variable=format_var, value="txt").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text=_t("plagiarism.zip_archive"), variable=format_var, value="zip").pack(anchor=tk.W)

        # Export button
        def export_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.no_selection', default="No Selection"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.please_select_documents_to_export', default="Please select documents to export."))
                return

            if format_var.get() == "zip":
                # Export as ZIP
                filename = filedialog.asksaveasfilename(
                    title=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.save_export_archive', default="Save Export Archive"),
                    defaultextension=".zip",
                    filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
                )

                if not filename:
                    return

                try:
                    import zipfile

                    with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        with self.checker.get_db_connection() as conn:
                            cursor = conn.cursor()

                            for item in selected:
                                doc_id = tree.item(item)['values'][0]
                                cursor.execute('SELECT title, content FROM document_repository WHERE id = ?', (doc_id,))
                                row = cursor.fetchone()

                                if row:
                                    title, content = row
                                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                    zipf.writestr(f'{doc_id}_{safe_title}.txt', content)

                    messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.success', default="Success"), f"Exported {len(selected)} documents to {filename}")
                    export_dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), f"Export failed: {e}")

            else:
                # Export as individual files
                directory = filedialog.askdirectory(title=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.select_export_directory', default="Select Export Directory"))

                if not directory:
                    return

                try:
                    exported = 0
                    with self.checker.get_db_connection() as conn:
                        cursor = conn.cursor()

                        for item in selected:
                            doc_id = tree.item(item)['values'][0]
                            cursor.execute('SELECT title, content FROM document_repository WHERE id = ?', (doc_id,))
                            row = cursor.fetchone()

                            if row:
                                title, content = row
                                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                file_path = os.path.join(directory, f'{doc_id}_{safe_title}.txt')

                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.write(content)
                                exported += 1

                    messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.success', default="Success"), f"Exported {exported} documents to {directory}")
                    export_dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), f"Export failed: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text=_t("common.select_all"), command=lambda: tree.selection_set(tree.get_children())).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_t("common.deselect_all"), command=lambda: tree.selection_remove(tree.get_children())).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(button_frame, text=_t("plagiarism.export_selected"), command=export_selected).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text=_t("common.cancel"), command=export_dialog.destroy).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

        # Load documents after dialog is ready
        export_dialog.after(100, load_docs)

    def show_my_documents(self):
        """Show documents for current user - focuses on Documents tab"""
        if not getattr(self, 'checker', None) or not getattr(self, 'auth', None):
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.system_not_initialized', default="System not initialized"))
            return
        try:
            if hasattr(self, 'notebook') and hasattr(self, 'documents_tab'):
                self.notebook.select(self.documents_tab)
            # Filter to show only current user's documents
            self.load_documents()  # This would be modified to filter by current user
        except Exception as e:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), f"Failed to open My Documents: {e}")

    def show_view_results(self):
        """Focus the Results tab"""
        try:
            if hasattr(self, 'notebook') and hasattr(self, 'results_tab'):
                self.notebook.select(self.results_tab)
            else:
                messagebox.showwarning(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.results', default="Results"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.results_tab_not_available_yet', default="Results tab not available yet."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), f"Failed to open Results: {e}")

    def show_delete_document_dialog(self):
        """Show dialog to delete a document"""
        if not getattr(self, 'checker', None):
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.system_not_initialized', default="System not initialized"))
            return

        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.permission_denied', default="Permission Denied"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.you_don_t_have_permission_to_delete_documents', default="You don't have permission to delete documents."))
            return

        # Create document selection dialog
        delete_dialog = tk.Toplevel(self.root)
        delete_dialog.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.windows.delete_document', default="Delete Document"))
        delete_dialog.geometry("700x500")
        delete_dialog.transient(self.root)
        delete_dialog.grab_set()

        main_frame = ttk.Frame(delete_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("plagiarism.delete_document"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Warning label
        warning_frame = ttk.Frame(main_frame)
        warning_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        ttk.Label(warning_frame, text=_t("plagiarism.delete_warning"),
                 foreground='red', font=GuiConfig.SUBHEADER_FONT).pack()

        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(search_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.labels.search', default="Search:")).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0), fill=tk.X, expand=True)

        # Documents list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        columns = ('id', 'title', 'author', 'date', 'module')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', selectmode='browse')
        tree.heading('id', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.id', default='ID'))
        tree.heading('title', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.title', default='Title'))
        tree.heading('author', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.author', default='Author'))
        tree.heading('date', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.date', default='Date'))
        tree.heading('module', text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.headings.module', default='Module'))

        tree.column('id', width=60)
        tree.column('title', width=250)
        tree.column('author', width=150)
        tree.column('date', width=120)
        tree.column('module', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Info label
        info_label = ttk.Label(main_frame, text=_t("plagiarism.select_document_delete"))
        info_label.pack()

        # Load documents
        def load_docs(search_term=''):
            try:
                tree.delete(*tree.get_children())

                if search_term:
                    documents = self.checker.search_repository(search_term)
                else:
                    documents = self.checker.search_repository()

                for doc in documents:
                    tree.insert('', tk.END, values=(
                        doc['id'],
                        doc['title'],
                        doc.get('author_name', 'Unknown'),
                        doc.get('submission_date', 'N/A'),
                        doc.get('module_code', 'N/A')
                    ))
            except Exception as e:
                messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), f"Failed to load documents: {e}")

        def search_docs():
            load_docs(search_var.get().strip())

        ttk.Button(search_frame, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.buttons.search', default="Search"), command=search_docs).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Delete button
        def delete_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.no_selection', default="No Selection"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.please_select_a_document_to_delete', default="Please select a document to delete."))
                return

            item = tree.item(selection[0])
            doc_id = item['values'][0]
            doc_title = item['values'][1]

            if not messagebox.askyesno(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.confirm_deletion', default="Confirm Deletion"),
                                      f"Are you sure you want to permanently delete:\n\n'{doc_title}' (ID: {doc_id})?\n\nThis action cannot be undone!"):
                return

            try:
                with self.checker.get_db_connection() as conn:
                    cursor = conn.cursor()

                    # Delete related plagiarism results first
                    cursor.execute('DELETE FROM plagiarism_results WHERE document_id = ?', (doc_id,))

                    # Delete the document
                    cursor.execute('DELETE FROM document_repository WHERE id = ?', (doc_id,))

                    conn.commit()

                messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.success', default="Success"), f"Document '{doc_title}' has been deleted.")
                load_docs(search_var.get().strip())  # Reload list

                # Refresh main documents list if available
                if hasattr(self, 'load_documents'):
                    self.load_documents()

            except Exception as e:
                messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), f"Failed to delete document: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text=_t("plagiarism.delete_selected"), command=delete_selected).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_t("common.close"), command=delete_dialog.destroy).pack(side=tk.RIGHT)

        # Load documents after dialog is ready
        delete_dialog.after(100, load_docs)

    def show_repository_integrity_dialog(self):
        """Show repository integrity check dialog"""
        if not getattr(self, 'checker', None):
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), _t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.system_not_initialized', default="System not initialized"))
            return

        # Call the full implementation from check_repository_integrity_gui
        self.check_repository_integrity_gui()

    def show_check_result(self, result):
        """Show plagiarism check result"""
        dialog = CheckResultDialog(self.root, self.checker, result,
                                   auth=self.auth,
                                   on_email_result=self.send_plagiarism_report_via_email)
        dialog.show()

    def show_result_details(self, result_data):
        """Show detailed result information"""
        dialog = ResultDetailsDialog(self.root, self.checker, result_data['result_id'],
                                     auth=self.auth,
                                     on_email_result=self.send_plagiarism_report_via_email)
        dialog.show()

    def send_plagiarism_report_via_email(self, result_data, user_email=None):
        """Send plagiarism report via email GUI"""
        try:
            # Extract result information
            result_id = result_data.get('result_id', 'Unknown')
            similarity_score = result_data.get('similarity_score', 0)
            document_name = result_data.get('document_name', 'Unknown Document')

            # Generate email content
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            status = '\u26a0\ufe0f ATTENTION REQUIRED' if similarity_score > 30 else '\u2705 WITHIN ACCEPTABLE LIMITS'
            subject, message = render_template('plagiarism_report', {
                'document_name': document_name,
                'result_id': result_id,
                'similarity_score': similarity_score,
                'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': status
            })

            if not (subject and message):
                print("Failed to load plagiarism report template")
                return

            # Send via email GUI
            success = self._send_email_via_gui(user_email, subject, message)

            if success:
                messagebox.showinfo(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.email_sent', default="Email Sent"), f"Plagiarism report sent to {user_email}")
            else:
                # Show fallback
                self._show_plagiarism_email_fallback(user_email, subject, message, result_data)

        except Exception as e:
            messagebox.showerror(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_export_documents.dialogs.error', default="Error"), f"Failed to send plagiarism report: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email using the core email service"""
        try:
            from education_system.systems.university.infrastructure.email.email_service.core import send_email
            return send_email(
                recipient_email=to_email,
                subject=subject,
                body=message
            )
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
