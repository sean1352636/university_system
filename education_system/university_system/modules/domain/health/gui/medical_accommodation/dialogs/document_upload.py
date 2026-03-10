# dialogs/document_upload.py
# Dialog for uploading documents to accommodations.

from .._common import (
    tk, ttk, messagebox, filedialog, os, datetime,
    CLI_AVAILABLE, SECURE_UPLOAD_AVAILABLE, validate_upload, secure_filename,
    get_connection, logger,
)
from ..utils import resolve_user_identifier


class DocumentUploadDialog:
    """Dialog for uploading documents"""

    def __init__(self, parent, accommodation_id):
        self.result = None
        self.accommodation_id = accommodation_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Upload Document")
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)

        self.create_widgets()

        # Ensure window is visible before grabbing focus
        self.dialog.update_idletasks()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Ignore grab errors if window not ready

        self.dialog.wait_window()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Document name
        ttk.Label(main_frame, text="Document Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.doc_name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.doc_name_var, width=40).grid(row=0, column=1, pady=5, sticky='ew')

        # File path
        ttk.Label(main_frame, text="File Path:").grid(row=1, column=0, sticky='w', pady=5)
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=1, sticky='ew', pady=5)

        self.file_path_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.file_path_var, width=30).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(path_frame, text="Browse", command=self.browse_file).pack(side=tk.RIGHT, padx=(5,0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Upload", command=self.upload).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[("All files", "*.*")]
        )
        if file_path:
            self.file_path_var.set(file_path)
            # Auto-fill document name if not set
            if not self.doc_name_var.get():
                self.doc_name_var.set(os.path.basename(file_path))

    def upload(self):
        if not self.doc_name_var.get().strip():
            messagebox.showerror("Error", "Document name is required")
            return

        if not self.file_path_var.get().strip():
            messagebox.showerror("Error", "File path is required")
            return

        if not os.path.exists(self.file_path_var.get()):
            messagebox.showerror("Error", "File does not exist")
            return

        try:
            self.do_upload()
            if CLI_AVAILABLE:
                from .._common import log_action
                log_action('upload_document', self.accommodation_id,
                           f"Uploaded document '{self.doc_name_var.get().strip()}'")

            self.result = True
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Upload failed: {str(e)}")

    def do_upload(self):
        """Perform the actual file upload with secure validation"""
        import shutil

        file_path = self.file_path_var.get()
        original_filename = os.path.basename(file_path)

        # Read file content for secure validation
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Validate file using secure upload handler
        if SECURE_UPLOAD_AVAILABLE and validate_upload:
            validation = validate_upload(original_filename, file_content, category='documents')
            if not validation['valid']:
                raise ValueError(f"File validation failed: {validation['error']}")
            safe_name = validation['safe_filename']
        else:
            safe_name = secure_filename(original_filename)

        # Create uploads directory if it doesn't exist
        uploads_dir = "uploaded_documents"
        os.makedirs(uploads_dir, exist_ok=True)

        # Set restrictive permissions on uploads directory
        try:
            os.chmod(uploads_dir, 0o700)
        except OSError:
            pass

        # Create unique filename
        ext = os.path.splitext(safe_name)[1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{self.accommodation_id}_{timestamp}{ext}"
        destination_path = os.path.join(uploads_dir, unique_filename)

        # Copy file securely
        shutil.copy(file_path, destination_path)

        # Set restrictive permissions on uploaded file
        try:
            os.chmod(destination_path, 0o600)
        except OSError:
            pass

        # Record in database
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = resolve_user_identifier()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO accommodation_documents
                (accommodation_id, document_name, document_path, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.accommodation_id, self.doc_name_var.get().strip(),
                  destination_path, user, now))
            conn.commit()

    def cancel(self):
        self.dialog.destroy()
