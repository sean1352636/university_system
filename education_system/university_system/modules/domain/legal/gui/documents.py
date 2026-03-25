"""Documents mixin for the Legal Services GUI."""

from education_system.university_system.modules.domain.legal.gui._imports import (
    tk, ttk, messagebox, scrolledtext, filedialog, simpledialog, traceback,
    os, datetime,
    Dict,
    CaseManager, DocumentManager,
    _t,
)


class DocumentsMixin:
    """Documents tab: generate, upload, view history, refresh."""

    def create_documents_tab(self):
        """Create documents tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.documents", default="Documents"))

        # Top section: Case selector and document list
        top_frame = ttk.Frame(tab)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Case selector
        selector_frame = ttk.Frame(top_frame)
        selector_frame.pack(fill=tk.X, pady=5)

        ttk.Label(selector_frame, text=_t("legal.select_case", default="Select Case") + ":").pack(side=tk.LEFT, padx=5)
        self.doc_case_combo = ttk.Combobox(selector_frame, state='readonly', width=40)
        self.doc_case_combo.pack(side=tk.LEFT, padx=5)
        self.doc_case_combo.bind('<<ComboboxSelected>>', self.load_case_documents)

        ttk.Button(selector_frame, text=_t("common.refresh", default="Refresh"), command=self.refresh_document_cases).pack(side=tk.LEFT, padx=5)

        # Documents list
        list_frame = ttk.LabelFrame(top_frame, text=_t("legal.case_documents", default="Case Documents"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('id', 'name', 'type', 'version', 'created_by', 'created_at')
        self.docs_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)

        self.docs_tree.heading('id', text='ID')
        self.docs_tree.heading('name', text=_t("legal.labels.document_name", default="Document Name"))
        self.docs_tree.heading('type', text=_t("legal.labels.document_type", default="Type"))
        self.docs_tree.heading('version', text=_t("legal.labels.version", default="Version"))
        self.docs_tree.heading('created_by', text=_t("legal.labels.created_by", default="Created By"))
        self.docs_tree.heading('created_at', text=_t("legal.labels.created_at", default="Created At"))

        self.docs_tree.column('id', width=40)
        self.docs_tree.column('name', width=200)
        self.docs_tree.column('type', width=120)
        self.docs_tree.column('version', width=60)
        self.docs_tree.column('created_by', width=100)
        self.docs_tree.column('created_at', width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.docs_tree.yview)
        self.docs_tree.configure(yscrollcommand=scrollbar.set)

        self.docs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom: Action buttons and forms
        bottom_frame = ttk.Frame(tab)
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)

        btn_frame = ttk.Frame(bottom_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text=_t("legal.btn.generate_document", default="Generate Document"), command=self.generate_legal_document).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("legal.btn.upload_document", default="Upload Document"), command=self.upload_case_document).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("legal.btn.view_history", default="View History"), command=self.view_document_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("legal.btn.generate_invoice", default="Generate Invoice"), command=self.generate_invoice).pack(side=tk.RIGHT, padx=5)

        # Initialize case list
        self.refresh_document_cases()

    def generate_legal_document(self):
        """Generate a legal document from template"""
        case_selection = self.doc_case_combo.get()
        if not case_selection:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)
            if not case:
                messagebox.showerror(_t("common.error", default="Error"), "Case not found")
                return

            # Document type dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(_t("legal.btn.generate_document", default="Generate Document"))
            dialog.geometry("450x400")
            dialog.transient(self.window)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Case: {case['case_number']}", font=('Arial', 11, 'bold')).pack(pady=10)

            ttk.Label(dialog, text=_t("legal.labels.document_type", default="Document Type") + ":").pack(pady=5)
            doc_types = ['Engagement Letter', 'Legal Opinion', 'Case Summary', 'Client Agreement', 'Cease and Desist', 'Demand Letter', 'Affidavit', 'Power of Attorney']
            type_combo = ttk.Combobox(dialog, values=doc_types, state='readonly', width=35)
            type_combo.set('Engagement Letter')
            type_combo.pack(pady=5)

            ttk.Label(dialog, text=_t("legal.labels.document_name", default="Document Name") + ":").pack(pady=5)
            name_entry = ttk.Entry(dialog, width=38)
            name_entry.insert(0, f"{case['case_number']}_engagement_letter")
            name_entry.pack(pady=5)

            ttk.Label(dialog, text=_t("legal.labels.additional_notes", default="Additional Notes") + ":").pack(pady=5)
            notes_text = scrolledtext.ScrolledText(dialog, width=40, height=6)
            notes_text.pack(pady=5)

            def generate():
                doc_type = type_combo.get()
                doc_name = name_entry.get().strip()
                notes = notes_text.get('1.0', tk.END).strip()

                if not doc_name:
                    messagebox.showwarning(_t("common.warning", default="Warning"), "Please enter a document name")
                    return

                # Generate document content based on type
                content = self._generate_document_content(case, doc_type, notes)

                doc_id = DocumentManager.create_document(
                    case_id=case['case_id'],
                    document_type=doc_type,
                    document_name=doc_name,
                    file_content=content,
                    created_by=self.current_user.get('username'),
                    notes=notes
                )

                if doc_id:
                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.document_generated", default="Document generated successfully")
                    )
                    dialog.destroy()
                    self.load_case_documents(None)
                else:
                    messagebox.showerror(_t("common.error", default="Error"), "Failed to generate document")

            ttk.Button(dialog, text=_t("legal.btn.generate_document", default="Generate"), command=generate).pack(pady=20)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error generating document: {traceback.format_exc()}")

    def _generate_document_content(self, case: Dict, doc_type: str, notes: str) -> str:
        """Generate document content based on type"""
        date = datetime.now().strftime('%Y-%m-%d')

        if doc_type == 'Engagement Letter':
            return f"""
UNIVERSITY LEGAL AID CENTER
ENGAGEMENT LETTER

Date: {date}
Case Number: {case['case_number']}

Dear {case['client_name']},

This letter confirms our engagement to provide legal services regarding:

Case Type: {case['case_type'].replace('_', ' ').title()}
Matter: {case['case_title']}

SCOPE OF SERVICES:
{case.get('case_description', 'To be discussed during initial consultation.')}

We look forward to working with you on this matter.

Sincerely,
University Legal Aid Center

{'Additional Notes: ' + notes if notes else ''}
"""
        elif doc_type == 'Case Summary':
            return f"""
CASE SUMMARY

Case Number: {case['case_number']}
Date: {date}

CLIENT INFORMATION:
Name: {case['client_name']}
ID: {case['client_id']}
Email: {case.get('client_email', 'N/A')}

CASE DETAILS:
Type: {case['case_type'].replace('_', ' ').title()}
Title: {case['case_title']}
Priority: {case['priority']}
Status: {case['status']}
Assigned Lawyer: {case.get('assigned_lawyer', 'Not assigned')}

DESCRIPTION:
{case.get('case_description', 'No description provided.')}

{'NOTES: ' + notes if notes else ''}

Prepared by: {self.current_user.get('username', 'Legal Staff')}
"""
        else:
            return f"""
{doc_type.upper()}

Case Number: {case['case_number']}
Client: {case['client_name']}
Date: {date}

[Document content to be completed]

{notes if notes else ''}

Prepared by: University Legal Aid Center
"""

    def upload_case_document(self):
        """Upload a document to the selected case"""
        case_selection = self.doc_case_combo.get()
        if not case_selection:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)
            if not case:
                messagebox.showerror(_t("common.error", default="Error"), "Case not found")
                return

            # File selection
            file_path = filedialog.askopenfilename(
                title=_t("legal.btn.upload_document", default="Select Document"),
                filetypes=[
                    ("All Files", "*.*"),
                    ("PDF Files", "*.pdf"),
                    ("Word Documents", "*.docx"),
                    ("Text Files", "*.txt"),
                    ("Images", "*.png *.jpg *.jpeg")
                ]
            )

            if not file_path:
                return

            file_name = os.path.basename(file_path)

            # Ask for document type
            doc_type = simpledialog.askstring(
                _t("legal.labels.document_type", default="Document Type"),
                _t("legal.prompts.document_type", default="Enter document type (e.g., Evidence, Contract, ID):"),
                initialvalue="Supporting Document"
            )

            if not doc_type:
                return

            doc_id = DocumentManager.create_document(
                case_id=case['case_id'],
                document_type=doc_type,
                document_name=file_name,
                file_path=file_path,
                created_by=self.current_user.get('username')
            )

            if doc_id:
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.document_uploaded", default="Document uploaded successfully")
                )
                self.load_case_documents(None)
            else:
                messagebox.showerror(_t("common.error", default="Error"), "Failed to upload document")

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error uploading document: {traceback.format_exc()}")

    def view_document_history(self):
        """View version history for a document"""
        selected = self.docs_tree.selection()
        if not selected:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_document_selected", default="Please select a document first")
            )
            return

        try:
            item = self.docs_tree.item(selected[0])
            doc_id = item['values'][0]
            doc_name = item['values'][1]

            case_selection = self.doc_case_combo.get()
            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)

            if not case:
                return

            history = DocumentManager.get_document_history(doc_name, case['case_id'])

            if not history:
                messagebox.showinfo(
                    _t("common.info", default="Info"),
                    _t("legal.messages.no_history", default="No version history available")
                )
                return

            # Show history dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(f"Document History - {doc_name}")
            dialog.geometry("500x400")
            dialog.transient(self.window)

            ttk.Label(dialog, text=f"Version History for: {doc_name}", font=('Arial', 11, 'bold')).pack(pady=10)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            history_text = ""
            for doc in history:
                history_text += f"""
Version {doc['version']}
{'='*40}
Created: {doc['created_at']}
Created By: {doc.get('created_by', 'Unknown')}
Type: {doc['document_type']}
Notes: {doc.get('notes', 'None')}

"""

            text.insert('1.0', history_text)
            text.config(state='disabled')

            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def refresh_document_cases(self):
        """Refresh case list for document selector"""
        try:
            cases = CaseManager.get_all_cases()
            case_options = [f"{c['case_number']} - {c['client_name']}" for c in cases]
            self.doc_case_combo['values'] = case_options
            if case_options:
                self.doc_case_combo.set(case_options[0])
                self.load_case_documents(None)
        except Exception as e:
            print(f"Error refreshing document cases: {e}")

    def load_case_documents(self, event):
        """Load documents for the selected case"""
        try:
            for item in self.docs_tree.get_children():
                self.docs_tree.delete(item)

            case_selection = self.doc_case_combo.get()
            if not case_selection:
                return

            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)

            if case:
                documents = DocumentManager.get_case_documents(case['case_id'])
                for doc in documents:
                    self.docs_tree.insert('', tk.END, values=(
                        doc['document_id'],
                        doc['document_name'],
                        doc['document_type'],
                        doc['version'],
                        doc.get('created_by', 'Unknown'),
                        doc['created_at'][:19] if doc['created_at'] else ''
                    ))

        except Exception as e:
            print(f"Error loading case documents: {e}")
