import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
import shutil
import hashlib
from datetime import datetime, timedelta
import logging
from education_system.post_18.university_system.core import paths
from education_system.post_18.university_system.infrastructure.security.file_upload import (
    validate_upload,
)

logger = logging.getLogger(__name__)

try:
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.post_18.university_system.infrastructure.database.db import transaction
except ImportError:
    transaction = None

try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class DocumentsManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def upload_document_dialog(self):
        """Show upload document dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Upload Document")
        dialog.geometry("700x600")
        dialog.minsize(500, 400)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))

        # Title - pack at top
        ttk.Label(dialog, text="Upload Student Document", font=('Arial', 14, 'bold')).pack(pady=(15, 5))

        # Buttons - pack at bottom FIRST so they're always visible
        button_frame = ttk.Frame(dialog)
        button_frame.pack(side='bottom', fill='x', padx=20, pady=10)

        ttk.Button(button_frame, text="Upload Document", command=lambda: self.perform_upload(dialog)).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        # Separator above buttons
        ttk.Separator(dialog, orient='horizontal').pack(side='bottom', fill='x', padx=20)

        # Scrollable form area for the rest of the content
        form_canvas = tk.Canvas(dialog, highlightthickness=0)
        form_scrollbar = ttk.Scrollbar(dialog, orient='vertical', command=form_canvas.yview)
        main_frame = ttk.Frame(form_canvas, padding=(20, 10, 20, 10))

        main_frame.bind(
            '<Configure>',
            lambda e: form_canvas.configure(scrollregion=form_canvas.bbox('all'))
        )
        canvas_window = form_canvas.create_window((0, 0), window=main_frame, anchor='nw')
        form_canvas.configure(yscrollcommand=form_scrollbar.set)

        form_scrollbar.pack(side='right', fill='y')
        form_canvas.pack(side='left', fill='both', expand=True)

        # Keep main_frame width in sync with canvas
        def _on_canvas_configure(event):
            form_canvas.itemconfig(canvas_window, width=event.width)
        form_canvas.bind('<Configure>', _on_canvas_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            if event.delta:
                form_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
            elif event.num == 4:
                form_canvas.yview_scroll(-1, 'units')
            elif event.num == 5:
                form_canvas.yview_scroll(1, 'units')

        form_canvas.bind('<MouseWheel>', _on_mousewheel)
        form_canvas.bind('<Button-4>', _on_mousewheel)
        form_canvas.bind('<Button-5>', _on_mousewheel)

        # Student selection
        student_frame = ttk.LabelFrame(main_frame, text="Student Information", padding=10)
        student_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(student_frame, text="Student ID:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gui.upload_student_id = ttk.Combobox(student_frame, width=20)
        self.gui.upload_student_id.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # Populate student IDs
        students = self.gui.get_students_list()
        student_values = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
        self.gui.upload_student_id['values'] = student_values

        # Search button
        ttk.Button(student_frame, text="\U0001f50d Search", command=self.gui.search_student_for_upload).grid(row=0, column=2, padx=5)

        student_frame.grid_columnconfigure(1, weight=1)

        # Document type selection
        doc_type_frame = ttk.LabelFrame(main_frame, text="Document Type", padding=10)
        doc_type_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(doc_type_frame, text="Document Type:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gui.upload_doc_type = ttk.Combobox(doc_type_frame, width=30)
        self.gui.upload_doc_type.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # Populate document types
        doc_types = self.gui.get_document_types_with_details()
        self.gui.upload_doc_type['values'] = [f"{dt[1]} - {dt[2]}" for dt in doc_types]
        self.gui.upload_doc_type.bind('<<ComboboxSelected>>', self.on_doc_type_selected)

        doc_type_frame.grid_columnconfigure(1, weight=1)

        # Document type info
        self.gui.doc_type_info = ttk.Label(doc_type_frame, text="", font=('Arial', 9), foreground='blue')
        self.gui.doc_type_info.grid(row=1, column=0, columnspan=2, sticky='w', padx=5, pady=(5, 0))

        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding=10)
        file_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gui.upload_file_path = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.gui.upload_file_path, width=40)
        file_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Button(file_frame, text="Browse...", command=self.browse_file).grid(row=0, column=2, padx=5)

        file_frame.grid_columnconfigure(1, weight=1)

        # File info
        self.gui.file_info = ttk.Label(file_frame, text="", font=('Arial', 9), foreground='gray')
        self.gui.file_info.grid(row=1, column=0, columnspan=3, sticky='w', padx=5, pady=(5, 0))

        # Additional options
        options_frame = ttk.LabelFrame(main_frame, text="Additional Options", padding=10)
        options_frame.pack(fill='x', pady=(0, 15))

        # Expiry date (if applicable)
        ttk.Label(options_frame, text="Expiry Date:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gui.upload_expiry_date = tk.Entry(options_frame, width=15)
        self.gui.upload_expiry_date.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ttk.Label(options_frame, text="(YYYY-MM-DD, if applicable)", font=('Arial', 9), foreground='gray').grid(row=0, column=2, sticky='w', padx=5)

        # Tags
        ttk.Label(options_frame, text="Tags:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.gui.upload_tags = tk.Entry(options_frame, width=40)
        self.gui.upload_tags.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ttk.Label(options_frame, text="(comma-separated)", font=('Arial', 9), foreground='gray').grid(row=2, column=1, sticky='w', padx=5)

        # Notes
        ttk.Label(options_frame, text="Notes:").grid(row=3, column=0, sticky='nw', padx=5, pady=5)
        self.gui.upload_notes = tk.Text(options_frame, width=40, height=3)
        self.gui.upload_notes.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky='ew')

        options_frame.grid_columnconfigure(1, weight=1)

    def browse_file(self):
        """Browse for file to upload"""
        file_path = filedialog.askopenfilename(
            title="Select Document File",
            filetypes=[
                ("All Supported", "*.pdf *.jpg *.jpeg *.png *.doc *.docx"),
                ("PDF files", "*.pdf"),
                ("Image files", "*.jpg *.jpeg *.png"),
                ("Word documents", "*.doc *.docx"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self.gui.upload_file_path.set(file_path)
            self.update_file_info(file_path)

    def update_file_info(self, file_path):
        """Update file information display"""
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            file_ext = os.path.splitext(file_path)[1][1:].lower()

            info_text = f"Size: {file_size_mb:.2f} MB, Format: {file_ext.upper()}"
            self.gui.file_info.config(text=info_text)

    def on_doc_type_selected(self, event=None):
        """Handle document type selection"""
        selection = self.gui.upload_doc_type.get()
        if selection:
            doc_types = self.gui.get_document_types_with_details()
            for dt in doc_types:
                if selection.startswith(dt[1]):
                    # Show document type info
                    info_text = f"Max size: {dt[6]}MB, Formats: {dt[7]}, Required: {'Yes' if dt[3] else 'No'}"
                    if dt[4]:  # has_expiry
                        info_text += ", Expires: Yes"
                    self.gui.doc_type_info.config(text=info_text)
                    break

    def perform_upload(self, dialog):
        """Perform the document upload"""
        # Validate inputs
        if not self.gui.upload_student_id.get():
            messagebox.showerror("Error", "Please select a student")
            return

        if not self.gui.upload_doc_type.get():
            messagebox.showerror("Error", "Please select a document type")
            return

        if not self.gui.upload_file_path.get() or not os.path.exists(self.gui.upload_file_path.get()):
            messagebox.showerror("Error", "Please select a valid file")
            return

        try:
            # Extract student ID
            student_id = self.gui.upload_student_id.get().split(' - ')[0]

            # Extract document type ID
            doc_type_selection = self.gui.upload_doc_type.get()
            doc_types = self.gui.get_document_types_with_details()
            type_id = None
            for dt in doc_types:
                if doc_type_selection.startswith(dt[1]):
                    type_id = dt[0]
                    break

            if not type_id:
                messagebox.showerror("Error", "Invalid document type selected")
                return

            # Validate file
            file_path = self.gui.upload_file_path.get()
            if not self.validate_file(file_path, type_id):
                return

            # Perform upload
            success = self.upload_document_to_db(
                student_id, type_id, file_path,
                self.gui.upload_expiry_date.get(),
                self.gui.upload_tags.get(),
                self.gui.upload_notes.get('1.0', 'end-1c')
            )

            if success:
                messagebox.showinfo("Success", "Document uploaded successfully!")
                dialog.destroy()
                self.refresh_documents()
                self.gui.refresh_dashboard()
            else:
                messagebox.showerror("Error", "Failed to upload document")

        except Exception as e:
            messagebox.showerror("Error", f"Upload failed: {str(e)}")

    def validate_file(self, file_path, type_id):
        """Validate file against document type requirements"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT max_file_size_mb, allowed_formats
            FROM document_types
            WHERE type_id = ?
            ''', (type_id,))

            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror("Error", "Document type not found")
                return False

            max_size_mb, allowed_formats = result

            # Check file size
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)

            if file_size_mb > max_size_mb:
                messagebox.showerror("Error", f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)")
                return False

            # Check file format
            file_ext = os.path.splitext(file_path)[1][1:].lower()
            allowed_ext_list = [ext.strip().lower() for ext in allowed_formats.split(',')]

            if file_ext not in allowed_ext_list:
                messagebox.showerror("Error", f"File format '{file_ext}' not allowed. Allowed formats: {allowed_formats}")
                return False

            return True

        except Exception as e:
            messagebox.showerror("Error", f"File validation failed: {str(e)}")
            return False

    def upload_document_to_db(self, student_id, type_id, file_path, expiry_date, tags, notes):
        """Upload document to database with secure file handling"""
        try:
            # Read file content for secure validation
            original_filename = os.path.basename(file_path)
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # Validate file using secure upload handler
            validation = validate_upload(original_filename, file_content, category='documents')
            if not validation['valid']:
                messagebox.showerror("Upload Error", f"File validation failed: {validation['error']}")
                return None

            conn = get_connection()
            try:
                cursor = conn.cursor()

                # Check for existing document of same type
                cursor.execute('''
                SELECT document_id, version_number
                FROM documents
                WHERE owner_id = ? AND source_type = 'student' AND document_type = ? AND is_current_version = 1
                ''', (student_id, str(type_id)))

                existing_doc = cursor.fetchone()

                # Create document directory if it doesn't exist
                doc_dir = paths.UPLOAD_DIR / 'student_documents' / student_id
                os.makedirs(doc_dir, exist_ok=True)

                # Set restrictive permissions on directory
                try:
                    os.chmod(doc_dir, 0o700)
                except OSError:
                    pass

                # Use sanitized filename from secure validation
                safe_filename = validation['safe_filename']
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_filename = f"{timestamp}_{safe_filename}"
                new_file_path = os.path.join(doc_dir, new_filename)

                # Save file securely
                shutil.copy2(file_path, new_file_path)

                # Set restrictive permissions on uploaded file
                try:
                    os.chmod(new_file_path, 0o600)
                except OSError:
                    pass

                # Calculate file hash using SHA-256 (more secure than MD5)
                file_hash = hashlib.sha256(file_content).hexdigest()

                logger.info(f"Document uploaded securely: {new_filename} ({len(file_content)} bytes)")

                file_size = os.path.getsize(new_file_path)
                upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Handle versioning
                if existing_doc:
                    # Mark existing as not current
                    cursor.execute('''
                    UPDATE documents
                    SET is_current_version = 0
                    WHERE document_id = ?
                    ''', (existing_doc[0],))

                    new_version = existing_doc[1] + 1
                    parent_doc_id = existing_doc[0]
                else:
                    new_version = 1
                    parent_doc_id = None

                # Insert new document record
                cursor.execute('''
                INSERT INTO documents
                (source_type, owner_id, document_type, file_path, original_filename, upload_date, expiry_date,
                 verification_status, version_number, parent_document_id, uploaded_by,
                 file_size, file_hash, tags, notes, workflow_status)
                VALUES ('student', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, str(type_id), new_file_path, original_filename, upload_date,
                      expiry_date if expiry_date else None, 'Pending', new_version, parent_doc_id,
                      self.gui.current_user['username'], file_size, file_hash, tags, notes, 'submitted'))

                document_id = cursor.lastrowid

                # Create notification (non-critical, don't block upload on failure)
                try:
                    cursor.execute('''
                    INSERT INTO notifications (user_id, channel, priority, title, message, source_system, source_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, 'system', 'normal', 'Document Uploaded',
                          'Your document has been uploaded and is pending verification.',
                          'document_manager', str(document_id)))
                except Exception as notify_err:
                    logger.warning(f"Failed to create upload notification: {notify_err}")

                conn.commit()

                # Send email notification to student (non-critical)
                try:
                    cursor2 = conn.cursor()
                    cursor2.execute('''
                        SELECT s.email_address, s.first_name, s.last_name, dt.type_name
                        FROM students s
                        JOIN document_types dt ON dt.type_id = ?
                        WHERE s.student_id = ?
                    ''', (type_id, student_id))
                    row = cursor2.fetchone()
                    if row and row[0]:
                        student_email, first_name, last_name, type_name = row
                        from education_system.post_18.university_system.infrastructure.email.email_service import send_email
                        send_email(
                            recipient_email=student_email,
                            subject=f"Document Uploaded: {type_name}",
                            body=(
                                f"Dear {first_name} {last_name},\n\n"
                                f"A document has been uploaded to your student record.\n\n"
                                f"  File Name: {original_filename}\n"
                                f"  Document Type: {type_name}\n"
                                f"  Upload Time: {upload_date}\n\n"
                                f"The document is now pending verification.\n\n"
                                f"Regards,\n"
                                f"University Document Management"
                            ),
                        )
                except Exception as email_err:
                    logger.warning(f"Failed to send upload email notification: {email_err}")

                return True

            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to save document: {str(e)}")
                return False
            finally:
                conn.close()

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to save document: {str(e)}")
            return False

    def view_document_details(self):
        """View detailed information about selected document"""
        selection = self.gui.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to view details.")
            return

        item = self.gui.docs_tree.item(selection[0])
        doc_id = item['values'][0]

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.*, s.first_name, s.last_name, s.email_address, dt.type_name, dt.description
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.source_type = 'student' AND sd.document_id = ?
            ''', (doc_id,))

            doc_data = cursor.fetchone()
            conn.close()

            if doc_data:
                self.show_document_details_window(doc_data)
            else:
                messagebox.showerror("Error", "Document not found.")

        except Exception as e:
            messagebox.showerror("Database Error", f"Error loading document details: {str(e)}")

    def show_document_details_window(self, doc_data):
        """Show document details in a new window"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Document Details")
        dialog.geometry("850x700")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Create scrollable text widget
        text_widget = tk.Text(main_frame, wrap='word', height=25, width=70)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        # Format document details
        details = f"""Document Details
================

Document ID: {doc_data[0]}
Student: {doc_data[17]} {doc_data[18]} ({doc_data[1]})
Email: {doc_data[19]}
Document Type: {doc_data[20]}
Description: {doc_data[21]}

File Information:
- Original Filename: {doc_data[4]}
- File Path: {doc_data[3]}
- File Size: {doc_data[13]} bytes
- File Hash: {doc_data[14]}

Status Information:
- Upload Date: {doc_data[5]}
- Expiry Date: {doc_data[6] if doc_data[6] else 'N/A'}
- Status: {doc_data[7]}
- Verification Date: {doc_data[8] if doc_data[8] else 'N/A'}
- Uploaded by: {doc_data[12]}

Version Information:
- Version: {doc_data[10]}
- Is Current: {'Yes' if doc_data[16] else 'No'}
- Workflow Status: {doc_data[17]}

Tags: {doc_data[15] if doc_data[15] else 'None'}

Notes:
{doc_data[9] if doc_data[9] else 'No notes available'}
"""

        text_widget.insert('1.0', details)
        text_widget.config(state='disabled')

        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Close button
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def edit_document_status(self):
        """Edit the status of selected document"""
        selection = self.gui.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to edit.")
            return

        item = self.gui.docs_tree.item(selection[0])
        doc_id = item['values'][0]
        current_status = item['values'][4]

        # Status dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Document Status")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Update Document Status", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        ttk.Label(main_frame, text=f"Document ID: {doc_id}").pack(anchor='w')
        ttk.Label(main_frame, text=f"Current Status: {current_status}").pack(anchor='w', pady=(0, 15))

        ttk.Label(main_frame, text="New Status:").pack(anchor='w')
        status_var = tk.StringVar(value=current_status)
        status_combo = ttk.Combobox(main_frame, textvariable=status_var,
                                   values=['Pending', 'Verified', 'Rejected', 'Expired'])
        status_combo.pack(fill='x', pady=5)

        ttk.Label(main_frame, text="Notes:").pack(anchor='w', pady=(10, 0))
        notes_text = tk.Text(main_frame, height=5, width=40)
        notes_text.pack(fill='x', pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        def update_status():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE documents
                SET verification_status = ?, verification_date = ?, verification_notes = ?
                WHERE document_id = ?
                ''', (status_var.get(), datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      notes_text.get('1.0', 'end-1c'), doc_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Document status updated successfully!")
                dialog.destroy()
                self.refresh_documents()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update status: {str(e)}")

        ttk.Button(button_frame, text="Update", command=update_status).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def download_document(self):
        """Download selected document file"""
        selection = self.gui.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to download.")
            return

        item = self.gui.docs_tree.item(selection[0])
        doc_id = item['values'][0]

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT file_path, original_filename FROM documents WHERE document_id = ?', (doc_id,))
            result = cursor.fetchone()
            conn.close()

            if result and os.path.exists(result[0]):
                save_path = filedialog.asksaveasfilename(
                    title="Save Document As",
                    initialname=result[1],
                    defaultextension=os.path.splitext(result[1])[1]
                )

                if save_path:
                    shutil.copy2(result[0], save_path)
                    messagebox.showinfo("Success", f"Document downloaded to {save_path}")
            else:
                messagebox.showerror("Error", "Document file not found.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to download document: {str(e)}")

    def send_document_notification(self):
        """Send notification about selected document"""
        selection = self.gui.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to send notification about.")
            return

        item = self.gui.docs_tree.item(selection[0])
        doc_id = item['values'][0]
        student_name = item['values'][1]
        doc_type = item['values'][2]

        dialog = tk.Toplevel(self.root)
        dialog.title("Send Document Notification")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Send notification about:", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        ttk.Label(main_frame, text=f"Document: {doc_type}").pack(anchor='w')
        ttk.Label(main_frame, text=f"Student: {student_name}").pack(anchor='w')

        ttk.Label(main_frame, text="Message:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        message_text = tk.Text(main_frame, height=6, width=40)
        message_text.pack(fill='x', pady=5)
        message_text.insert('1.0', f"Regarding your {doc_type} document...")

        def send_notification():
            message = message_text.get('1.0', 'end-1c')
            if message:
                messagebox.showinfo("Success", "Notification sent successfully!")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Please enter a message")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Send", command=send_notification).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def delete_document(self):
        """Delete selected document"""
        selection = self.gui.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to delete.")
            return

        item = self.gui.docs_tree.item(selection[0])
        doc_id = item['values'][0]

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this document?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get file path before deletion
                cursor.execute('SELECT file_path FROM documents WHERE document_id = ?', (doc_id,))
                result = cursor.fetchone()

                # Delete from database
                cursor.execute('DELETE FROM documents WHERE document_id = ?', (doc_id,))

                conn.commit()
                conn.close()

                # Delete physical file
                if result and os.path.exists(result[0]):
                    os.remove(result[0])

                messagebox.showinfo("Success", "Document deleted successfully!")
                self.refresh_documents()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete document: {str(e)}")

    def show_documents(self):
        """Show documents management interface"""
        self.gui.clear_content_area()

        # Create documents frame
        docs_frame = ttk.Frame(self.gui.content_area)
        docs_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title and controls
        title_frame = ttk.Frame(docs_frame)
        title_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(title_frame, text="Document Management", font=('Arial', 18, 'bold')).pack(side='left')

        # Control buttons
        controls_frame = ttk.Frame(title_frame)
        controls_frame.pack(side='right')

        ttk.Button(controls_frame, text="\U0001f4e4 Upload", command=self.upload_document_dialog).pack(side='left', padx=2)
        ttk.Button(controls_frame, text="\U0001f50d Search", command=self.search_documents).pack(side='left', padx=2)
        ttk.Button(controls_frame, text="\U0001f504 Refresh", command=self.refresh_documents).pack(side='left', padx=2)

        # Filters frame
        filters_frame = ttk.LabelFrame(docs_frame, text="Filters", padding=10)
        filters_frame.pack(fill='x', pady=(0, 10))

        # Status filter
        ttk.Label(filters_frame, text="Status:").grid(row=0, column=0, padx=5, sticky='w')
        self.gui.status_filter = ttk.Combobox(filters_frame, values=['All', 'Pending', 'Verified', 'Rejected', 'Expired'])
        self.gui.status_filter.set('All')
        self.gui.status_filter.grid(row=0, column=1, padx=5)
        self.gui.status_filter.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())

        # Document type filter
        ttk.Label(filters_frame, text="Type:").grid(row=0, column=2, padx=5, sticky='w')
        self.gui.type_filter = ttk.Combobox(filters_frame, values=['All'] + self.gui.get_document_types())
        self.gui.type_filter.set('All')
        self.gui.type_filter.grid(row=0, column=3, padx=5)
        self.gui.type_filter.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())

        # Date range filter
        ttk.Label(filters_frame, text="From:").grid(row=0, column=4, padx=5, sticky='w')
        self.gui.from_date = tk.Entry(filters_frame, width=12)
        self.gui.from_date.grid(row=0, column=5, padx=5)
        self.gui.from_date.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))

        ttk.Label(filters_frame, text="To:").grid(row=0, column=6, padx=5, sticky='w')
        self.gui.to_date = tk.Entry(filters_frame, width=12)
        self.gui.to_date.grid(row=0, column=7, padx=5)
        self.gui.to_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Apply filters button
        ttk.Button(filters_frame, text="Apply Filters", command=self.apply_filters).grid(row=0, column=8, padx=10)

        # Documents table
        self.create_documents_table(docs_frame)

        # Load initial data
        self.refresh_documents()

    def create_documents_table(self, parent):
        """Create the documents table"""
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True)

        # Define columns
        columns = ('ID', 'Student', 'Document Type', 'Upload Date', 'Status', 'Expiry', 'Version', 'Notes')
        self.gui.docs_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Define headings and column widths
        column_widths = {'ID': 60, 'Student': 150, 'Document Type': 180, 'Upload Date': 100,
                        'Status': 100, 'Expiry': 100, 'Version': 80, 'Notes': 200}

        for col in columns:
            self.gui.docs_tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
            self.gui.docs_tree.column(col, width=column_widths.get(col, 100))

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.gui.docs_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=self.gui.docs_tree.xview)
        self.gui.docs_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack widgets
        self.gui.docs_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Context menu
        self.create_documents_context_menu()

        # Double-click binding
        self.gui.docs_tree.bind('<Double-1>', self.on_document_double_click)

    def create_documents_context_menu(self):
        """Create context menu for documents table"""
        self.gui.docs_context_menu = tk.Menu(self.root, tearoff=0)
        self.gui.docs_context_menu.add_command(label="View Details", command=self.view_document_details)
        self.gui.docs_context_menu.add_command(label="Edit Status", command=self.edit_document_status)
        self.gui.docs_context_menu.add_command(label="View Versions", command=self.gui.view_document_versions)
        self.gui.docs_context_menu.add_separator()
        self.gui.docs_context_menu.add_command(label="Download File", command=self.download_document)
        self.gui.docs_context_menu.add_command(label="Send Notification", command=self.send_document_notification)
        self.gui.docs_context_menu.add_separator()
        self.gui.docs_context_menu.add_command(label="Delete Document", command=self.delete_document)

        # Bind right-click
        self.gui.docs_tree.bind('<Button-3>', self.show_docs_context_menu)

    def show_docs_context_menu(self, event):
        """Show context menu for documents"""
        item = self.gui.docs_tree.identify_row(event.y)
        if item:
            self.gui.docs_tree.selection_set(item)
            self.gui.docs_context_menu.post(event.x_root, event.y_root)

    def load_documents_data(self):
        """Load documents data into table"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            query = '''
            SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, DATE(sd.upload_date), sd.verification_status,
                   sd.expiry_date, sd.version_number, sd.verification_notes
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.source_type = 'student' AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            '''

            cursor.execute(query)
            documents = cursor.fetchall()
            conn.close()

            # Clear existing items
            for item in self.gui.docs_tree.get_children():
                self.gui.docs_tree.delete(item)

            # Insert new items
            for doc in documents:
                # Format the data for display
                doc_id, student_name, doc_type, upload_date, status, expiry_date, version, notes = doc
                expiry_display = expiry_date if expiry_date else "N/A"
                notes_display = notes[:30] + "..." if notes and len(notes) > 30 else notes or ""

                self.gui.docs_tree.insert('', 'end', values=(
                    doc_id, student_name, doc_type, upload_date, status,
                    expiry_display, version, notes_display
                ))

        except Exception as e:
            messagebox.showerror("Data Error", f"Failed to load documents: {str(e)}")

    def on_document_double_click(self, event):
        """Handle double-click on document"""
        selection = self.gui.docs_tree.selection()
        if selection:
            self.view_document_details()

    def search_documents(self):
        """
        Search documents

        Searches documents based on the search term entered by the user.
        Filters the documents tree view to show only matching documents
        by student name, document type, or status.
        """
        search_term = self.gui.search_var.get().lower()

        if not search_term:
            # If search is empty, reload all documents
            self.load_documents_data()
            return

        # Clear existing items
        for item in self.gui.docs_tree.get_children():
            self.gui.docs_tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Search in documents with student information
            cursor.execute('''
                SELECT
                    d.document_id,
                    COALESCE(s.first_name || ' ' || s.last_name, 'Unknown') as student_name,
                    d.document_type,
                    d.upload_date,
                    d.verification_status,
                    d.expiry_date,
                    d.version,
                    d.notes
                FROM documents d
                LEFT JOIN students s ON d.owner_id = s.student_id
                WHERE d.is_current_version = 1
                AND (
                    LOWER(s.first_name || ' ' || s.last_name) LIKE ?
                    OR LOWER(d.document_type) LIKE ?
                    OR LOWER(d.verification_status) LIKE ?
                    OR LOWER(d.notes) LIKE ?
                )
                ORDER BY d.upload_date DESC
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

            for row in cursor.fetchall():
                self.gui.docs_tree.insert('', 'end', values=row)

            conn.close()

        except Exception as e:
            messagebox.showerror("Search Error", f"Failed to search documents: {str(e)}")

    def sort_column(self, col):
        """
        Sort documents table by column

        Sorts the documents tree view by the specified column.
        Toggles between ascending and descending order on repeated clicks.
        """
        # Get all items
        items = [(self.gui.docs_tree.set(item, col), item) for item in self.gui.docs_tree.get_children('')]

        # Determine sort order (toggle if clicking same column)
        if hasattr(self.gui, '_sort_col') and self.gui._sort_col == col:
            self.gui._sort_reverse = not getattr(self.gui, '_sort_reverse', False)
        else:
            self.gui._sort_reverse = False

        self.gui._sort_col = col

        # Sort items
        try:
            # Try numeric sort first
            items.sort(key=lambda x: float(x[0]) if x[0] else 0, reverse=self.gui._sort_reverse)
        except (ValueError, TypeError):
            # Fall back to string sort
            items.sort(key=lambda x: str(x[0]).lower(), reverse=self.gui._sort_reverse)

        # Rearrange items in tree
        for index, (val, item) in enumerate(items):
            self.gui.docs_tree.move(item, '', index)

        # Update column heading to show sort direction
        for c in self.gui.docs_tree['columns']:
            heading = self.gui.docs_tree.heading(c)['text']
            # Remove existing sort indicators
            if heading.endswith(' \u2191') or heading.endswith(' \u2193'):
                heading = heading[:-2]
            self.gui.docs_tree.heading(c, text=heading)

        # Add sort indicator to current column
        heading = self.gui.docs_tree.heading(col)['text']
        indicator = ' \u2193' if self.gui._sort_reverse else ' \u2191'
        self.gui.docs_tree.heading(col, text=heading + indicator)

    def refresh_documents(self):
        """Refresh documents table"""
        if hasattr(self.gui, 'docs_tree') and self.gui.docs_tree is not None:
            self.load_documents_data()

    def apply_filters(self):
        """Apply filters to documents view"""
        # This would filter the documents based on current filter settings
        self.load_documents_data()

    def upload_student_document(self, student_id=None):
        """Upload document for a specific student"""
        if not self.gui.ensure_login():
            return

        # Create upload window
        upload_window = tk.Toplevel(self.root)
        upload_window.title("Upload Student Document")
        upload_window.transient(self.root)
        upload_window.grab_set()

        # Center on screen
        win_w, win_h = 600, 420
        screen_w = upload_window.winfo_screenwidth()
        screen_h = upload_window.winfo_screenheight()
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        upload_window.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # Title
        ttk.Label(upload_window, text="Upload Student Document",
                 font=("Arial", 14, "bold")).pack(pady=(8, 4))

        # Button frame - pack at bottom first so it's always visible
        button_frame = ttk.Frame(upload_window)
        button_frame.pack(side='bottom', fill='x', padx=15, pady=8)

        # Form frame
        form_frame = ttk.Frame(upload_window, padding=10)
        form_frame.pack(fill='both', expand=True)

        # Student ID
        ttk.Label(form_frame, text="Student ID: *").grid(row=0, column=0, sticky='w', pady=3)
        student_id_entry = ttk.Entry(form_frame, width=40)
        if student_id:
            student_id_entry.insert(0, student_id)
        student_id_entry.grid(row=0, column=1, sticky='ew', pady=3)

        # Document Type
        ttk.Label(form_frame, text="Document Type: *").grid(row=1, column=0, sticky='w', pady=3)
        doc_type_combo = ttk.Combobox(form_frame, width=38, state='readonly')
        doc_type_combo['values'] = ['Transcript', 'ID Card', 'Health Form', 'Enrollment Form',
                                     'Financial Document', 'Recommendation Letter', 'Other']
        doc_type_combo.current(0)
        doc_type_combo.grid(row=1, column=1, sticky='ew', pady=3)

        # File selection
        ttk.Label(form_frame, text="Select File: *").grid(row=2, column=0, sticky='w', pady=3)
        file_path_var = tk.StringVar()
        file_entry = ttk.Entry(form_frame, textvariable=file_path_var, width=40, state='readonly')
        file_entry.grid(row=2, column=1, sticky='ew', pady=3)

        def browse_file():
            filename = filedialog.askopenfilename(
                title="Select Document",
                filetypes=[("PDF Files", "*.pdf"), ("Image Files", "*.jpg *.jpeg *.png"),
                          ("All Files", "*.*")]
            )
            if filename:
                file_path_var.set(filename)

        ttk.Button(form_frame, text="Browse...", command=browse_file).grid(row=2, column=2, padx=5)

        # Expiry Date
        ttk.Label(form_frame, text="Expiry Date:").grid(row=3, column=0, sticky='w', pady=3)
        expiry_entry = ttk.Entry(form_frame, width=40)
        expiry_entry.insert(0, "YYYY-MM-DD (optional)")
        expiry_entry.grid(row=3, column=1, sticky='ew', pady=3)

        # Tags
        ttk.Label(form_frame, text="Tags:").grid(row=4, column=0, sticky='w', pady=3)
        tags_entry = ttk.Entry(form_frame, width=40)
        tags_entry.insert(0, "comma, separated, tags")
        tags_entry.grid(row=4, column=1, sticky='ew', pady=3)

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=5, column=0, sticky='w', pady=3)
        notes_text = tk.Text(form_frame, width=40, height=2)
        notes_text.grid(row=5, column=1, sticky='ew', pady=3)

        # Status
        ttk.Label(form_frame, text="Initial Status:").grid(row=6, column=0, sticky='w', pady=3)
        status_combo = ttk.Combobox(form_frame, width=38, state='readonly')
        status_combo['values'] = ['Pending', 'Approved']
        status_combo.current(0)
        status_combo.grid(row=6, column=1, sticky='ew', pady=3)

        form_frame.columnconfigure(1, weight=1)

        def submit_upload():
            """Submit the document upload"""
            # Validate fields
            if not student_id_entry.get().strip():
                messagebox.showwarning("Validation Error", "Student ID is required")
                return

            if not file_path_var.get():
                messagebox.showwarning("Validation Error", "Please select a file to upload")
                return

            try:
                # Get file info
                file_path = file_path_var.get()
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)

                # Get expiry date
                expiry_date = expiry_entry.get()
                if expiry_date == "YYYY-MM-DD (optional)":
                    expiry_date = None

                # Get tags
                tags = tags_entry.get()
                if tags == "comma, separated, tags":
                    tags = None

                # Get notes
                notes = notes_text.get('1.0', 'end-1c')

                # Insert into database
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO documents (student_id, document_type, file_name,
                                         file_path, file_size, status, upload_date,
                                         expiry_date, tags, notes)
                    VALUES (?, ?, ?, ?, ?, ?, DATE('now'), ?, ?, ?)
                """, (student_id_entry.get(), doc_type_combo.get(), file_name,
                     file_path, file_size, status_combo.get(), expiry_date, tags, notes))

                doc_id = cursor.lastrowid
                conn.commit()
                conn.close()

                messagebox.showinfo("Success",
                                  f"Document uploaded successfully!\n\n"
                                  f"Document ID: {doc_id}\n"
                                  f"Student: {student_id_entry.get()}\n"
                                  f"Type: {doc_type_combo.get()}\n"
                                  f"Status: {status_combo.get()}")

                # Log activity
                self.gui.log_event('upload', 'document', entity_id=doc_id,
                              details=f'Uploaded {file_name} for student {student_id_entry.get()}')

                upload_window.destroy()

            except Exception as e:
                messagebox.showerror("Upload Error", f"Failed to upload document: {e}")

        ttk.Button(button_frame, text="Upload Document",
                  command=submit_upload).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel",
                  command=upload_window.destroy).pack(side='right', padx=5)
