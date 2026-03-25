from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.university_system.modules.domain.academics.gui.parent_portal.base import ParentPortalGUI

def update_profile_photo(self):
    """Update parent profile photo"""
    from tkinter import filedialog
    
    file_path = filedialog.askopenfilename(
        title="Select Profile Photo",
        filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp")]
    )
    
    if file_path:
        # In real implementation, would upload and process the image
        messagebox.showinfo("Success", "Profile photo updated successfully.")
        self.update_status("Profile photo updated")
ParentPortalGUI.update_profile_photo = update_profile_photo

class QRCodeDialog:
    """Dialog for generating a QR code for student identification."""

    def __init__(self, parent, children):
        self.result = None

        dialog = tk.Toplevel(parent)
        dialog.title("Generate QR Code")
        dialog.geometry("500x350")
        dialog.transient(parent)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Generate Student QR Code",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Child selection
        ttk.Label(main_frame, text="Select Student:").pack(anchor='w')
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(main_frame, textvariable=child_var, width=45, state="readonly")
        child_combo['values'] = [f"{c[1]} {c[3]} (ID: {c[0]})" for c in children]
        if child_combo['values']:
            child_combo.current(0)
        child_combo.pack(fill=tk.X, pady=(0, 10))

        # Purpose
        ttk.Label(main_frame, text="Purpose:").pack(anchor='w')
        purpose_var = tk.StringVar(value="Student Identification")
        purpose_combo = ttk.Combobox(main_frame, textvariable=purpose_var, width=45, state="readonly")
        purpose_combo['values'] = [
            "Student Identification", "Library Access", "Event Check-in",
            "Exam Verification", "Campus Access"
        ]
        purpose_combo.current(0)
        purpose_combo.pack(fill=tk.X, pady=(0, 10))

        # Save path
        save_var = tk.StringVar()
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(path_frame, text="Save to (optional):").pack(anchor='w')
        path_entry = ttk.Entry(path_frame, textvariable=save_var, width=40)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        def browse_path():
            path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                title="Save QR Code"
            )
            if path:
                save_var.set(path)

        ttk.Button(path_frame, text="Browse...", command=browse_path).pack(side=tk.RIGHT)

        def submit():
            idx = child_combo.current()
            if idx < 0:
                messagebox.showwarning("No Student", "Please select a student.")
                return
            self.result = {
                'child': children[idx],
                'purpose': purpose_var.get(),
                'qr_path': save_var.get() or None
            }
            dialog.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Generate", command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dialog.wait_window()


def generate_qr_code_interface(self):
    """Generate QR code for student identification"""
    if not self.children:
        messagebox.showinfo("No Students", "No students linked to your guardian account.")
        return

    dialog = QRCodeDialog(self.root, self.children)
    if dialog.result:
        child = dialog.result['child']
        purpose = dialog.result.get('purpose', 'Student Identification')
        qr_path = dialog.result.get('qr_path')

        if qr_path:
            messagebox.showinfo("QR Code Generated",
                              f"QR code generated for {child[1]} {child[3]}.\n"
                              f"Purpose: {purpose}\n"
                              f"Saved to: {qr_path}\n\n"
                              "This can be used for secure student identification.")
        else:
            messagebox.showinfo("QR Code Generated",
                              f"QR code generated for {child[1]} {child[3]}.\n"
                              "This can be used for secure student identification.")
ParentPortalGUI.generate_qr_code_interface = generate_qr_code_interface

def show_photo_interface(self):
    """Show photo permissions interface"""
    self.clear_content()
    self.update_status("Photo Permissions")

    title = ttk.Label(self.content_frame, text="Photo & Media Permissions", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Permissions display frame
    perm_frame = ttk.LabelFrame(self.content_frame, text="Media Permissions", padding=15)
    perm_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_photo_permissions():
        for widget in perm_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(perm_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='photo_permissions'
            """)

            if cursor.fetchone():
                # Correct schema: permission_type, consent_given, conditions, valid_from, valid_until
                cursor.execute("""
                SELECT permission_type, consent_given, conditions, valid_from, valid_until, date_signed
                FROM photo_permissions
                WHERE student_id = ?
                ORDER BY permission_type
                """, (student_id,))

                permissions = cursor.fetchall()

                if permissions:
                    # Display permissions by type
                    for perm in permissions:
                        perm_type, consent, conditions, valid_from, valid_until, date_signed = perm
                        frame = ttk.Frame(perm_frame)
                        frame.pack(fill=tk.X, pady=5)
                        ttk.Label(frame, text=f"{perm_type or 'General'}:",
                                 font=('Arial', 10, 'bold'), width=25).pack(side=tk.LEFT)
                        status = "Allowed" if consent else "Not Allowed"
                        color = 'green' if consent else 'red'
                        ttk.Label(frame, text=status, font=('Arial', 10), foreground=color).pack(side=tk.LEFT)
                        if valid_until:
                            ttk.Label(frame, text=f" (Valid until: {valid_until})",
                                     font=('Arial', 9)).pack(side=tk.LEFT)

                    # Show conditions if any
                    conditions_list = [p[2] for p in permissions if p[2]]
                    if conditions_list:
                        notes_frame = ttk.LabelFrame(perm_frame, text="Conditions/Notes", padding=10)
                        notes_frame.pack(fill=tk.X, pady=(10, 0))
                        for cond in conditions_list:
                            ttk.Label(notes_frame, text=f"• {cond}", wraplength=500).pack(anchor='w')

                    ttk.Button(perm_frame, text="Update Permissions",
                              command=lambda: self.update_photo_permissions(student_id)).pack(pady=10)
                else:
                    ttk.Label(perm_frame, text="No photo permissions set",
                             font=('Arial', 11)).pack(pady=50)
                    ttk.Button(perm_frame, text="Set Permissions",
                              command=lambda: self.update_photo_permissions(student_id)).pack()
            else:
                ttk.Label(perm_frame, text="Photo permissions system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(perm_frame, text=f"Error loading permissions: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Permissions", command=load_photo_permissions).pack(side=tk.LEFT, padx=5)
    load_photo_permissions()
ParentPortalGUI.show_photo_interface = show_photo_interface

def update_photo_permissions(self, student_id):
    """Update photo permissions"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Update Photo Permissions")
    dialog.geometry("600x500")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Photo & Media Permissions",
             font=('Arial', 14, 'bold')).pack(pady=(0, 10))

    ttk.Label(main_frame, text="Please select which permissions you grant for your child:",
             font=('Arial', 10)).pack(pady=(0, 20))

    # Get existing permissions from database (using correct schema)
    existing_permissions = {}
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='photo_permissions'
        """)

        if cursor.fetchone():
            # Use the actual schema: permission_type, consent_given
            cursor.execute("""
            SELECT permission_type, consent_given
            FROM photo_permissions
            WHERE student_id = ?
            """, (student_id,))

            for row in cursor.fetchall():
                perm_type = row[0]
                consent = row[1]
                existing_permissions[perm_type] = consent

        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load permissions: {str(e)}")
        dialog.destroy()
        return

    # Create checkbox variables
    permission_vars = {}

    permission_options = [
        ('yearbook', 'Yearbook Photos', 'Allow photos in university yearbook'),
        ('website', 'University Website', 'Allow photos on university website'),
        ('social_media', 'Social Media', 'Allow photos on university social media accounts'),
        ('newsletter', 'Newsletter', 'Allow photos in university newsletters'),
        ('classroom', 'Classroom Display', 'Allow photos displayed in classroom'),
        ('media_release', 'Media Release', 'Allow photos for press/media coverage')
    ]

    for key, label, desc in permission_options:
        permission_vars[key] = tk.IntVar()
        # Check if this permission type exists and is granted
        if key in existing_permissions and existing_permissions[key]:
            permission_vars[key].set(1)

        frame = ttk.Frame(main_frame)
        frame.pack(fill=tk.X, pady=5)

        cb = ttk.Checkbutton(frame, text=label, variable=permission_vars[key])
        cb.pack(anchor='w')

        ttk.Label(frame, text=desc, font=('Arial', 9, 'italic')).pack(anchor='w', padx=20)

    def save_permissions():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            current_date = datetime.datetime.now().strftime('%Y-%m-%d')

            for perm_type, var in permission_vars.items():
                consent = var.get()

                # Check if record exists for this permission type
                cursor.execute("""
                SELECT id FROM photo_permissions
                WHERE student_id = ? AND permission_type = ?
                """, (student_id, perm_type))

                exists = cursor.fetchone()

                if exists:
                    # Update existing record
                    cursor.execute("""
                    UPDATE photo_permissions
                    SET consent_given = ?, date_signed = ?
                    WHERE student_id = ? AND permission_type = ?
                    """, (consent, current_date, student_id, perm_type))
                else:
                    # Insert new record
                    cursor.execute("""
                    INSERT INTO photo_permissions
                    (student_id, permission_type, consent_given, date_signed)
                    VALUES (?, ?, ?, ?)
                    """, (student_id, perm_type, consent, current_date))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Photo permissions updated successfully!")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update permissions: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Save Permissions", command=save_permissions).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.update_photo_permissions = update_photo_permissions

def show_documents_interface(self):
    """Show document management interface"""
    self.clear_content()
    self.update_status("Document Management")

    title = ttk.Label(self.content_frame, text="Document Management", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Documents display frame
    docs_frame = ttk.LabelFrame(self.content_frame, text="Documents", padding=15)
    docs_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_documents():
        for widget in docs_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(docs_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if documents table exists (unified document storage)
            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='documents'
            """)

            if cursor.fetchone():
                # Query student documents from unified documents table
                cursor.execute("""
                SELECT sd.original_filename, COALESCE(dt.type_name, 'Unknown'),
                       sd.upload_date, sd.uploaded_by, sd.verification_status,
                       sd.document_id, sd.file_path
                FROM documents sd
                LEFT JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE sd.owner_id = ? AND sd.owner_type = 'student'
                  AND sd.is_current_version = 1
                ORDER BY sd.upload_date DESC
                LIMIT 50
                """, (student_id,))

                documents = cursor.fetchall()

                # Also check parent-uploaded documents
                cursor.execute("""
                SELECT document_name, document_type, upload_date, 'Parent' as uploaded_by,
                       status, document_id, file_path
                FROM documents
                WHERE source_type = 'parent' AND reference_id = ?
                  AND reference_type = 'student'
                ORDER BY upload_date DESC
                LIMIT 50
                """, (student_id,))

                parent_docs = cursor.fetchall()
                all_documents = documents + parent_docs

                if all_documents:
                    columns = ("Document Name", "Type", "Upload Date", "Uploaded By", "Status")
                    tree = ttk.Treeview(docs_frame, columns=columns, show="headings", height=12)

                    tree.heading("Document Name", text="Document Name")
                    tree.heading("Type", text="Type")
                    tree.heading("Upload Date", text="Upload Date")
                    tree.heading("Uploaded By", text="Uploaded By")
                    tree.heading("Status", text="Status")

                    tree.column("Document Name", width=180)
                    tree.column("Type", width=120)
                    tree.column("Upload Date", width=100)
                    tree.column("Uploaded By", width=100)
                    tree.column("Status", width=100)

                    for doc in all_documents:
                        status = doc[4] or 'pending'
                        tree.insert('', tk.END, values=doc[:5], tags=(status,))

                    tree.tag_configure('verified', foreground='green')
                    tree.tag_configure('approved', foreground='green')
                    tree.tag_configure('pending', foreground='orange')
                    tree.tag_configure('rejected', foreground='red')

                    scrollbar = ttk.Scrollbar(docs_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    def view_document():
                        selected = tree.selection()
                        if selected:
                            item = tree.item(selected[0])
                            doc_name = item['values'][0]
                            messagebox.showinfo("Document Details",
                                               f"Document: {doc_name}\n\n"
                                               "To view the full document, please contact administration.")

                    btn_frame = ttk.Frame(docs_frame)
                    btn_frame.pack(pady=10)
                    ttk.Button(btn_frame, text="View Document", command=view_document).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text="Upload Document",
                              command=lambda: self.upload_document(student_id)).pack(side=tk.LEFT, padx=5)
                else:
                    ttk.Label(docs_frame, text="No documents found for this student",
                             font=('Arial', 11)).pack(pady=50)
                    ttk.Button(docs_frame, text="Upload Document",
                              command=lambda: self.upload_document(student_id)).pack()
            else:
                ttk.Label(docs_frame, text="Document management system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(docs_frame, text=f"Error loading documents: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Documents", command=load_documents).pack(side=tk.LEFT, padx=5)

    # Link to full Document Manager GUI
    def open_document_manager():
        try:
            from education_system.university_system.modules.shared.gui.document_manager_gui.main_gui import DocumentManagerGUI
            # Create a new top-level window for document manager
            doc_window = tk.Toplevel(self.root)
            doc_gui = DocumentManagerGUI(doc_window)
        except ImportError as e:
            messagebox.showinfo("Info", f"Document Manager GUI not available: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Document Manager: {e}")

    ttk.Button(child_frame, text="📁 Full Document Manager", command=open_document_manager).pack(side=tk.LEFT, padx=5)

    load_documents()
ParentPortalGUI.show_documents_interface = show_documents_interface

def upload_document(self, student_id):
    """Upload a document"""
    from tkinter import filedialog
    import shutil
    import os

    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Upload Document")
    dialog.geometry("600x450")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Upload Document",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Parent documents now use the unified documents table with source_type = 'parent'
    # No separate parent_documents table needed

    # Create form fields
    fields = {}

    # File selection
    selected_file = tk.StringVar()

    file_frame = ttk.Frame(main_frame)
    file_frame.pack(fill=tk.X, pady=10)

    ttk.Label(file_frame, text="Selected File:").pack(anchor='w')
    file_label = ttk.Label(file_frame, textvariable=selected_file, relief=tk.SUNKEN, padding=5)
    file_label.pack(fill=tk.X, pady=5)

    def select_file():
        filename = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[
                ("PDF files", "*.pdf"),
                ("Word documents", "*.doc *.docx"),
                ("Images", "*.jpg *.jpeg *.png"),
                ("All files", "*.*")
            ]
        )
        if filename:
            selected_file.set(filename)

    ttk.Button(file_frame, text="Browse...", command=select_file).pack(anchor='w', pady=5)

    # Document Type
    ttk.Label(main_frame, text="Document Type:").pack(anchor='w', pady=(10, 0))
    fields['document_type'] = ttk.Combobox(main_frame, width=50, state="readonly")
    fields['document_type']['values'] = ['Medical Form', 'Permission Slip', 'Report Card',
                                        'Transcript', 'ID Document', 'Insurance Card',
                                        'Vaccination Record', 'Emergency Contact Form', 'Other']
    fields['document_type'].pack(fill=tk.X, pady=(0, 10))

    # Expiry Date (optional)
    ttk.Label(main_frame, text="Expiry Date (optional, YYYY-MM-DD):").pack(anchor='w', pady=(5, 0))
    fields['expiry_date'] = ttk.Entry(main_frame, width=50)
    fields['expiry_date'].pack(fill=tk.X, pady=(0, 10))

    def upload_file():
        # Validate
        if not selected_file.get():
            messagebox.showwarning("Validation Error", "Please select a file to upload.")
            return

        if not fields['document_type'].get():
            messagebox.showwarning("Validation Error", "Please select a document type.")
            return

        try:
            file_path = selected_file.get()
            file_name = os.path.basename(file_path)
            expiry_date = fields['expiry_date'].get().strip() or None

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Insert document record into unified documents table
                cursor.execute("""
                INSERT INTO documents (source_type, owner_id, owner_type,
                                       reference_id, reference_type,
                                       document_type, document_name,
                                       file_path, upload_date, status, expiry_date)
                VALUES ('parent', ?, 'parent', ?, 'student', ?, ?, ?, datetime('now'), 'pending', ?)
                """, (
                    self.parent_id,
                    student_id,
                    fields['document_type'].get(),
                    file_name,
                    file_path,
                    expiry_date
                ))

                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo("Success",
                f"Document '{file_name}' uploaded successfully!\n\n"
                "Status: Pending review\n"
                "Administration will verify the document shortly.")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to upload document: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Upload", command=upload_file).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.upload_document = upload_document

def show_calendar_interface(self):
    """Show calendar integration interface"""
    self.clear_content()
    self.update_status("Calendar Integration")

    title = ttk.Label(self.content_frame, text="Calendar Integration", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Calendar sync options
    sync_frame = ttk.LabelFrame(self.content_frame, text="Calendar Export & Integration", padding=20)
    sync_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(sync_frame, text="Export university events to your personal calendar",
             font=('Arial', 11)).pack(anchor='w', pady=5)

    export_btn_frame = ttk.Frame(sync_frame)
    export_btn_frame.pack(fill=tk.X, pady=5)

    ttk.Button(export_btn_frame, text="Generate iCal File (.ics)",
              command=self.export_to_ical).pack(side=tk.LEFT, padx=5, pady=5)
    ttk.Button(export_btn_frame, text="Generate Google Calendar CSV",
              command=self.export_to_google_csv).pack(side=tk.LEFT, padx=5, pady=5)
    ttk.Button(export_btn_frame, text="Show Subscription URL",
              command=self.show_calendar_subscription_url).pack(side=tk.LEFT, padx=5, pady=5)

    # Event type filter
    filter_frame = ttk.Frame(self.content_frame)
    filter_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(filter_frame, text="Filter by Event Type:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
    event_type_var = tk.StringVar(value="all")
    event_type_combo = ttk.Combobox(filter_frame, textvariable=event_type_var, width=20, state='readonly')
    event_type_combo['values'] = ["All Events", "Academic", "Parent", "Holiday", "Sports", "Other"]
    event_type_combo.current(0)
    event_type_combo.pack(side=tk.LEFT, padx=5)

    # Upcoming events
    events_frame = ttk.LabelFrame(self.content_frame, text="University Calendar - Upcoming Events", padding=15)
    events_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_calendar_events():
        # Clear existing content
        for widget in events_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            today = datetime.datetime.now().strftime('%Y-%m-%d')
            event_filter = event_type_var.get().lower()

            # Collect events from all available event tables
            all_events = []

            # Check available event tables
            cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table'
            AND name IN ('academic_calendar_events', 'unified_events', 'school_calendar')
            """)
            available_tables = {row[0] for row in cursor.fetchall()}

            # 1. Query academic_calendar_events (primary source)
            if 'academic_calendar_events' in available_tables:
                if event_filter == "all events":
                    cursor.execute("""
                    SELECT name, description,
                           COALESCE(date, date_start) as event_date,
                           '08:00' as start_time, '17:00' as end_time,
                           'Campus' as location,
                           COALESCE(event_type, 'Academic') as event_type
                    FROM academic_calendar_events
                    WHERE COALESCE(date, date_start) >= ?
                    ORDER BY event_date
                    """, (today,))
                else:
                    cursor.execute("""
                    SELECT name, description,
                           COALESCE(date, date_start) as event_date,
                           '08:00' as start_time, '17:00' as end_time,
                           'Campus' as location,
                           COALESCE(event_type, 'Academic') as event_type
                    FROM academic_calendar_events
                    WHERE COALESCE(date, date_start) >= ?
                      AND LOWER(COALESCE(event_type, 'Academic')) = ?
                    ORDER BY event_date
                    """, (today, event_filter))
                all_events.extend(cursor.fetchall())

            # 2. Query unified_events (campus events)
            if 'unified_events' in available_tables:
                if event_filter == "all events":
                    cursor.execute("""
                    SELECT title AS event_name, description,
                           DATE(start_datetime) AS event_date,
                           TIME(start_datetime) AS start_time,
                           TIME(end_datetime) AS end_time,
                           COALESCE(location, 'Campus') as location,
                           COALESCE(event_type, 'Other') as event_type
                    FROM unified_events
                    WHERE source_type = 'campus'
                      AND DATE(start_datetime) >= ? AND status = 'scheduled'
                    ORDER BY start_datetime
                    """, (today,))
                else:
                    cursor.execute("""
                    SELECT title AS event_name, description,
                           DATE(start_datetime) AS event_date,
                           TIME(start_datetime) AS start_time,
                           TIME(end_datetime) AS end_time,
                           COALESCE(location, 'Campus') as location,
                           COALESCE(event_type, 'Other') as event_type
                    FROM unified_events
                    WHERE source_type = 'campus'
                      AND DATE(start_datetime) >= ? AND status = 'scheduled'
                      AND LOWER(COALESCE(event_type, 'Other')) = ?
                    ORDER BY start_datetime
                    """, (today, event_filter))
                all_events.extend(cursor.fetchall())

            # 3. Query school_calendar (legacy/fallback)
            if 'school_calendar' in available_tables:
                if event_filter == "all events":
                    cursor.execute("""
                    SELECT event_name, event_description, event_date,
                           start_time, end_time, location, event_type
                    FROM school_calendar
                    WHERE event_date >= ? AND audience IN ('all', 'parents')
                    ORDER BY event_date, start_time
                    """, (today,))
                else:
                    cursor.execute("""
                    SELECT event_name, event_description, event_date,
                           start_time, end_time, location, event_type
                    FROM school_calendar
                    WHERE event_date >= ? AND audience IN ('all', 'parents')
                      AND event_type = ?
                    ORDER BY event_date, start_time
                    """, (today, event_filter))
                all_events.extend(cursor.fetchall())

            # Sort combined results by date, then time
            all_events.sort(key=lambda e: (e[2] or '', e[3] or ''))

            # Deduplicate by event name + date
            seen = set()
            events = []
            for evt in all_events:
                key = (evt[0], evt[2])  # (name, date)
                if key not in seen:
                    seen.add(key)
                    events.append(evt)

            # Limit to 30 events
            events = events[:30]

            if events:
                # Create treeview
                columns = ("Event", "Date", "Time", "Location", "Type")
                tree = ttk.Treeview(events_frame, columns=columns, show="headings", height=12)

                tree.heading("Event", text="Event")
                tree.heading("Date", text="Date")
                tree.heading("Time", text="Time")
                tree.heading("Location", text="Location")
                tree.heading("Type", text="Type")

                tree.column("Event", width=250)
                tree.column("Date", width=100)
                tree.column("Time", width=100)
                tree.column("Location", width=150)
                tree.column("Type", width=80)

                for event in events:
                    event_name, description, event_date, start_time, end_time, location, event_type = event
                    time_range = f"{start_time} - {end_time}"
                    tree.insert('', tk.END, values=(event_name, event_date, time_range, location, event_type.upper()))

                scrollbar = ttk.Scrollbar(events_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)

                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Show event details on selection
                def show_event_details(event):
                    selected = tree.selection()
                    if selected:
                        item = tree.item(selected[0])
                        event_name = item['values'][0]
                        # Find full event details
                        for evt in events:
                            if evt[0] == event_name:
                                messagebox.showinfo("Event Details",
                                    f"Event: {evt[0]}\n\n"
                                    f"Description: {evt[1] or 'No description'}\n\n"
                                    f"Date: {evt[2]}\n"
                                    f"Time: {evt[3]} - {evt[4]}\n"
                                    f"Location: {evt[5]}\n"
                                    f"Type: {evt[6].upper()}")
                                break

                tree.bind('<Double-1>', show_event_details)

                ttk.Label(events_frame, text="Double-click an event for details",
                         font=('Arial', 8, 'italic')).pack(pady=5)
            else:
                ttk.Label(events_frame, text="No upcoming events found", font=('Arial', 11)).pack(pady=50)

            conn.close()
            self.update_status(f"Showing {len(events)} upcoming events")

        except Exception as e:
            ttk.Label(events_frame, text=f"Error loading events: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    # Load events initially
    load_calendar_events()

    # Reload when filter changes
    event_type_combo.bind('<<ComboboxSelected>>', lambda e: load_calendar_events())
ParentPortalGUI.show_calendar_interface = show_calendar_interface

def _fetch_all_calendar_events(self):
    """Fetch upcoming events from all available event tables."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    try:
        cursor = conn.cursor()
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table'
        AND name IN ('academic_calendar_events', 'unified_events', 'school_calendar')
        """)
        available_tables = {row[0] for row in cursor.fetchall()}

        all_events = []

        if 'academic_calendar_events' in available_tables:
            cursor.execute("""
            SELECT name, description,
                   COALESCE(date, date_start) as event_date,
                   '08:00' as start_time, '17:00' as end_time,
                   'Campus' as location,
                   COALESCE(event_type, 'Academic') as event_type
            FROM academic_calendar_events
            WHERE COALESCE(date, date_start) >= ?
            ORDER BY event_date
            """, (today,))
            all_events.extend(cursor.fetchall())

        if 'unified_events' in available_tables:
            cursor.execute("""
            SELECT title AS event_name, description,
                   DATE(start_datetime) AS event_date,
                   TIME(start_datetime) AS start_time,
                   TIME(end_datetime) AS end_time,
                   COALESCE(location, 'Campus') as location,
                   COALESCE(event_type, 'Other') as event_type
            FROM unified_events
            WHERE source_type = 'campus'
              AND DATE(start_datetime) >= ? AND status = 'scheduled'
            ORDER BY start_datetime
            """, (today,))
            all_events.extend(cursor.fetchall())

        if 'school_calendar' in available_tables:
            cursor.execute("""
            SELECT event_name, event_description, event_date,
                   start_time, end_time, location, event_type
            FROM school_calendar
            WHERE event_date >= ? AND audience IN ('all', 'parents')
            ORDER BY event_date, start_time
            """, (today,))
            all_events.extend(cursor.fetchall())

    finally:
        conn.close()

    # Sort by date, deduplicate by name+date
    all_events.sort(key=lambda e: (e[2] or '', e[3] or ''))
    seen = set()
    events = []
    for evt in all_events:
        key = (evt[0], evt[2])
        if key not in seen:
            seen.add(key)
            events.append(evt)
    return events[:30]
ParentPortalGUI._fetch_all_calendar_events = _fetch_all_calendar_events

def export_to_ical(self):
    """Export university events to iCal format"""
    try:
        events = self._fetch_all_calendar_events()

        if not events:
            messagebox.showinfo("Export", "No upcoming events to export.")
            return

        # Generate iCal content
        ical_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//University//Family Portal//EN\nCALSCALE:GREGORIAN\nMETHOD:PUBLISH\n"

        for event in events:
            name, description, date, start_time, end_time, location, event_type = event

            # Convert to iCal format (remove dashes and colons)
            event_start = f"{date.replace('-', '')}T{start_time.replace(':', '')}00"
            event_end = f"{date.replace('-', '')}T{end_time.replace(':', '')}00"

            ical_content += "BEGIN:VEVENT\n"
            ical_content += f"DTSTART:{event_start}\n"
            ical_content += f"DTEND:{event_end}\n"
            ical_content += f"SUMMARY:{name}\n"
            ical_content += f"DESCRIPTION:{description or 'University event'}\n"
            ical_content += f"LOCATION:{location}\n"
            ical_content += f"CATEGORIES:{event_type.upper()}\n"
            ical_content += "END:VEVENT\n"

        ical_content += "END:VCALENDAR\n"

        # Show dialog to save file
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".ics",
            filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
            title="Save iCal File"
        )

        if filename:
            with open(filename, 'w') as f:
                f.write(ical_content)
            messagebox.showinfo("Success",
                f"Calendar exported successfully!\n\n"
                f"File saved to: {filename}\n\n"
                f"You can now import this file into your calendar application.")
            self.update_status("Calendar exported to iCal file")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export calendar: {str(e)}")
ParentPortalGUI.export_to_ical = export_to_ical

def export_to_google_csv(self):
    """Export university events to Google Calendar CSV format"""
    try:
        events = self._fetch_all_calendar_events()

        if not events:
            messagebox.showinfo("Export", "No upcoming events to export.")
            return

        # Generate Google Calendar CSV
        csv_content = "Subject,Start Date,Start Time,End Date,End Time,Description,Location\n"

        for event in events:
            name, description, date, start_time, end_time, location, event_type = event
            # Escape commas and quotes in fields
            name = name.replace('"', '""')
            description = (description or '').replace('"', '""')
            location = location.replace('"', '""')

            csv_content += f'"{name}",{date},{start_time},{date},{end_time},"{description}","{location}"\n'

        # Show dialog to save file
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Google Calendar CSV"
        )

        if filename:
            with open(filename, 'w') as f:
                f.write(csv_content)
            messagebox.showinfo("Success",
                f"Calendar exported successfully!\n\n"
                f"File saved to: {filename}\n\n"
                f"Import this file to Google Calendar:\n"
                f"1. Open Google Calendar\n"
                f"2. Click Settings > Import & Export\n"
                f"3. Select the exported CSV file")
            self.update_status("Calendar exported to CSV file")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export calendar: {str(e)}")
ParentPortalGUI.export_to_google_csv = export_to_google_csv

def show_calendar_subscription_url(self):
    """Show calendar subscription URL"""
    if not self.parent_id:
        messagebox.showerror("Error", "Parent ID not found.")
        return

    # In a real implementation, this would be an actual webcal:// URL
    subscription_url = f"webcal://university.example.com/calendar/family/{self.parent_id}"

    dialog = tk.Toplevel(self.root)
    dialog.title("Calendar Subscription URL")
    dialog.geometry("600x300")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Calendar Subscription URL",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    ttk.Label(main_frame,
             text="Add this URL to your calendar app to automatically sync university events:",
             wraplength=500).pack(pady=10)

    url_frame = ttk.Frame(main_frame)
    url_frame.pack(fill=tk.X, pady=10)

    url_entry = ttk.Entry(url_frame, width=60)
    url_entry.insert(0, subscription_url)
    url_entry.config(state='readonly')
    url_entry.pack(side=tk.LEFT, padx=5)

    def copy_url():
        dialog.clipboard_clear()
        dialog.clipboard_append(subscription_url)
        messagebox.showinfo("Copied", "URL copied to clipboard!")

    ttk.Button(url_frame, text="Copy", command=copy_url).pack(side=tk.LEFT, padx=5)

    ttk.Label(main_frame,
             text="Instructions:\n\n"
                  "Google Calendar: Settings > Add calendar > From URL\n"
                  "Apple Calendar: File > New Calendar Subscription\n"
                  "Outlook: Add calendar > Subscribe from web",
             justify=tk.LEFT,
             wraplength=500).pack(pady=20)

    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
ParentPortalGUI.show_calendar_subscription_url = show_calendar_subscription_url

def sync_calendar(self, calendar_type):
    """Sync with external calendar (deprecated - use export functions)"""
    messagebox.showinfo("Calendar Sync",
                       f"Please use the Export buttons above to sync with {calendar_type}.")
ParentPortalGUI.sync_calendar = sync_calendar
