"""
Documents mixin - document vault management and uploads.
"""

import os

from education_system.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    tk,
    ttk,
    scrolledtext,
    logging,
    clear_frame,
    create_data_table,
    format_date,
    log_activity,
    show_error,
    show_success,
)
from education_system.university_system.core.i18n import get_text
from tkinter import filedialog

# Import secure file upload handler
try:
    from education_system.university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

logger = logging.getLogger(__name__)


class DocumentsMixin:
    """Document vault management functionality"""

    def show_documents(self):
        """Display document vault"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.documents.title", "Document Vault"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Control frame
        control_frame = ttk.Frame(self.parent_frame)
        control_frame.pack(pady=10)

        ttk.Label(control_frame, text=get_text("financial_aid.student_portal.documents.filter_by_type", "Filter by Type:")).pack(side='left', padx=5)
        self.doc_type_var = tk.StringVar(value=get_text("financial_aid.student_portal.documents.types.all", "All"))
        doc_types = [
            get_text("financial_aid.student_portal.documents.types.all", "All"),
            get_text("financial_aid.student_portal.documents.types.essay", "Essay"),
            get_text("financial_aid.student_portal.documents.types.transcript", "Transcript"),
            get_text("financial_aid.student_portal.documents.types.resume", "Resume"),
            get_text("financial_aid.student_portal.documents.types.recommendation", "Recommendation"),
            get_text("financial_aid.student_portal.documents.types.financial_document", "Financial Document"),
            get_text("financial_aid.student_portal.documents.types.certificate", "Certificate"),
            get_text("financial_aid.student_portal.documents.types.portfolio", "Portfolio"),
            get_text("financial_aid.student_portal.documents.types.other", "Other"),
        ]
        ttk.Combobox(control_frame, textvariable=self.doc_type_var, values=doc_types,
                    width=15, state='readonly').pack(side='left', padx=5)

        ttk.Button(control_frame, text=get_text("financial_aid.student_portal.buttons.filter", "Filter"), command=self._load_documents).pack(side='left', padx=10)
        ttk.Button(control_frame, text=get_text("financial_aid.student_portal.buttons.upload_new", "Upload New"), command=self._upload_document_dialog).pack(side='left', padx=5)
        ttk.Button(control_frame, text=get_text("financial_aid.student_portal.buttons.refresh", "Refresh"), command=self._load_documents).pack(side='left', padx=5)

        # Documents table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        col_id = get_text("financial_aid.student_portal.documents.columns.id", "ID")
        col_name = get_text("financial_aid.student_portal.documents.columns.name", "Name")
        col_type = get_text("financial_aid.student_portal.documents.columns.type", "Type")
        col_upload_date = get_text("financial_aid.student_portal.documents.columns.upload_date", "Upload Date")
        col_file_path = get_text("financial_aid.student_portal.documents.columns.file_path", "File Path")
        col_usage = get_text("financial_aid.student_portal.documents.columns.usage", "Usage")
        columns = [col_id, col_name, col_type, col_upload_date, col_file_path, col_usage]
        self.doc_tree = create_data_table(table_frame, columns, {
            col_id: 50, col_name: 250, col_type: 150,
            col_upload_date: 120, col_file_path: 300, col_usage: 80
        })

        # Load documents
        self._load_documents()

    def _load_documents(self):
        """Load and display documents"""
        try:
            # Clear tree
            for item in self.doc_tree.get_children():
                self.doc_tree.delete(item)

            doc_type = self.doc_type_var.get()
            all_text = get_text("financial_aid.student_portal.documents.types.all", "All")
            doc_type_filter = None if doc_type == all_text else doc_type.lower().replace(' ', '-')

            from education_system.university_system.modules.domain.finance.scholarship_finder.services.scholarship_service import DocumentVaultManager

            documents = DocumentVaultManager.get_student_documents(self.student_id, doc_type_filter)

            for doc in documents:
                file_path = doc.get('file_path', '')
                file_display = file_path[:50] + '...' if len(file_path) > 50 else file_path

                self.doc_tree.insert('', 'end', values=(
                    doc['document_id'],
                    doc['document_name'],
                    doc['document_type'],
                    format_date(doc['upload_date']),
                    file_display,
                    get_text("financial_aid.student_portal.documents.usage_times", "{count} times", count=doc.get('usage_count', 0))
                ))

        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_load_documents", "Failed to load documents: {error}", error=str(e)))

    def _upload_document_dialog(self):
        """Open dialog to upload document"""
        from tkinter import filedialog

        dialog = tk.Toplevel(self.parent_frame)
        dialog.title(get_text("financial_aid.student_portal.documents.upload_title", "Upload Document"))
        dialog.geometry("500x400")

        ttk.Label(dialog, text=get_text("financial_aid.student_portal.documents.upload_heading", "Upload Document"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Document type
        ttk.Label(dialog, text=get_text("financial_aid.student_portal.documents.document_type", "Document Type:")).pack(pady=5)
        doc_type_var = tk.StringVar()
        doc_types = ['essay', 'transcript', 'resume', 'recommendation', 'financial-document',
                     'certificate', 'portfolio', 'other']
        type_combo = ttk.Combobox(dialog, textvariable=doc_type_var, values=doc_types, state='readonly')
        type_combo.pack(pady=5)
        type_combo.current(0)

        # Document name
        ttk.Label(dialog, text=get_text("financial_aid.student_portal.documents.document_name", "Document Name:")).pack(pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=40).pack(pady=5)

        # File path
        ttk.Label(dialog, text=get_text("financial_aid.student_portal.documents.file_path", "File Path:")).pack(pady=5)
        path_frame = ttk.Frame(dialog)
        path_frame.pack(pady=5)
        path_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=path_var, width=35).pack(side='left', padx=5)

        def browse_file():
            filename = filedialog.askopenfilename()
            if filename:
                path_var.set(filename)

        ttk.Button(path_frame, text=get_text("financial_aid.student_portal.buttons.browse", "Browse"), command=browse_file).pack(side='left')

        # Description
        ttk.Label(dialog, text=get_text("financial_aid.student_portal.documents.description_optional", "Description (optional):")).pack(pady=5)
        desc_text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, height=5)
        desc_text.pack(fill='both', expand=True, padx=20, pady=5)

        # Tags
        ttk.Label(dialog, text=get_text("financial_aid.student_portal.documents.tags_label", "Tags (comma-separated):")).pack(pady=5)
        tags_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=tags_var, width=40).pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)

        def save_document():
            doc_type = doc_type_var.get()
            name = name_var.get().strip()
            path = path_var.get().strip()

            if not name or not path:
                show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.name_file_required", "Name and file path are required."))
                return

            # Security: Validate file before upload
            if SECURE_UPLOAD_AVAILABLE and validate_upload and os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        file_content = f.read()
                    original_filename = os.path.basename(path)
                    validation = validate_upload(original_filename, file_content, category='documents')
                    if not validation['valid']:
                        show_error(
                            get_text("financial_aid.student_portal.errors.security_error_title", "Security Error"),
                            get_text("financial_aid.student_portal.errors.file_validation_failed", "File validation failed: {error}", error=validation['error'])
                        )
                        log_activity(
                            'security_blocked',
                            'financial_aid_document',
                            student_id=self.student_id,
                            filename=original_filename,
                            reason=validation['error']
                        )
                        return
                except Exception as e:
                    logger.warning(f"File validation warning: {e}")

            description = desc_text.get('1.0', tk.END).strip()
            tags = tags_var.get().strip()

            try:
                from education_system.university_system.modules.domain.finance.scholarship_finder.services.scholarship_service import DocumentVaultManager

                doc_id = DocumentVaultManager.upload_document(
                    self.student_id, name, doc_type, path,
                    description=description, tags=tags
                )
                show_success(get_text("financial_aid.student_portal.success.title", "Success"), get_text("financial_aid.student_portal.success.document_uploaded", "Document uploaded! ID: {id}", id=doc_id))
                dialog.destroy()
                self._load_documents()

            except Exception as e:
                show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_upload_document", "Failed to upload document: {error}", error=str(e)))

        ttk.Button(button_frame, text=get_text("financial_aid.student_portal.buttons.upload", "Upload"), command=save_document).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.student_portal.buttons.cancel", "Cancel"), command=dialog.destroy).pack(side='left', padx=5)
