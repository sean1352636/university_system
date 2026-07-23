import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

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
    from contextlib import contextmanager
    @contextmanager
    def transaction():
        conn = get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class DocumentTypeManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def manage_document_types(self):
        """Open document types management with full functionality"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Document Types Management")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Document Types Management", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Document types list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        # Treeview for document types
        columns = ('ID', 'Name', 'Category', 'Required', 'Expiry', 'Max Size (MB)', 'Formats', 'Active')
        self.gui.doc_types_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.gui.doc_types_tree.heading(col, text=col)
            width = 60 if col == 'ID' else 100
            self.gui.doc_types_tree.column(col, width=width)

        # Scrollbar
        doc_types_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.gui.doc_types_tree.yview)
        self.gui.doc_types_tree.configure(yscrollcommand=doc_types_scrollbar.set)

        self.gui.doc_types_tree.pack(side='left', fill='both', expand=True)
        doc_types_scrollbar.pack(side='right', fill='y')

        # Load document types
        self.load_document_types_full()

        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='x')

        ttk.Button(buttons_frame, text="Add Type", command=self.add_document_type_full).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Edit Type", command=self.edit_document_type_full).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Delete Type", command=self.delete_document_type_full).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Refresh", command=self.load_document_types_full).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

    def load_document_types_full(self):
        """Load document types with full data"""
        if hasattr(self.gui, 'doc_types_tree') and self.gui.doc_types_tree is not None:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT type_id, type_name,
                       COALESCE(category, 'General') as category,
                       is_required, has_expiry,
                       max_file_size_mb, allowed_formats, is_active
                FROM document_types
                ORDER BY COALESCE(category, 'General'), COALESCE(sort_order, 0), type_name
                ''')
                doc_types = cursor.fetchall()
                conn.close()

                # Clear existing items
                for item in self.gui.doc_types_tree.get_children():
                    self.gui.doc_types_tree.delete(item)

                # Insert new items
                for doc_type in doc_types:
                    type_id, name, category, required, expiry, max_size, formats, active = doc_type
                    required_text = "Yes" if required else "No"
                    expiry_text = "Yes" if expiry else "No"
                    active_text = "Yes" if active else "No"

                    self.gui.doc_types_tree.insert('', 'end', values=(
                        type_id, name, category or "General", required_text, expiry_text, max_size, formats, active_text
                    ))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load document types: {str(e)}")

    def add_document_type_full(self):
        """Add new document type with full form"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Document Type")
        dialog.geometry("700x800")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Add New Document Type", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Form fields
        fields = {}

        # Type name
        ttk.Label(main_frame, text="Type Name:").pack(anchor='w')
        fields['name'] = tk.Entry(main_frame, width=40)
        fields['name'].pack(fill='x', pady=5)

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w')
        fields['description'] = tk.Text(main_frame, height=3, width=40)
        fields['description'].pack(fill='x', pady=5)

        # Category
        ttk.Label(main_frame, text="Category:").pack(anchor='w')
        fields['category'] = ttk.Combobox(main_frame, values=['Identity', 'Academic', 'Immigration', 'Health', 'Financial', 'Other'])
        fields['category'].pack(fill='x', pady=5)

        # Checkboxes
        fields['required'] = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Required Document", variable=fields['required']).pack(anchor='w', pady=5)

        fields['expiry'] = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Has Expiry Date", variable=fields['expiry']).pack(anchor='w', pady=5)

        fields['approval'] = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Requires Approval", variable=fields['approval']).pack(anchor='w', pady=5)

        # Max file size
        ttk.Label(main_frame, text="Max File Size (MB):").pack(anchor='w')
        fields['max_size'] = tk.Entry(main_frame, width=40)
        fields['max_size'].insert(0, "10")
        fields['max_size'].pack(fill='x', pady=5)

        # Allowed formats
        ttk.Label(main_frame, text="Allowed Formats (comma-separated):").pack(anchor='w')
        fields['formats'] = tk.Entry(main_frame, width=40)
        fields['formats'].insert(0, "pdf,jpg,jpeg,png")
        fields['formats'].pack(fill='x', pady=5)

        # Sort order
        ttk.Label(main_frame, text="Sort Order:").pack(anchor='w')
        fields['sort_order'] = tk.Entry(main_frame, width=40)
        fields['sort_order'].insert(0, "0")
        fields['sort_order'].pack(fill='x', pady=5)

        def save_document_type():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                INSERT INTO document_types
                (type_name, description, category, is_required, has_expiry, requires_approval,
                 max_file_size_mb, allowed_formats, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    fields['name'].get(),
                    fields['description'].get('1.0', 'end-1c'),
                    fields['category'].get(),
                    fields['required'].get(),
                    fields['expiry'].get(),
                    fields['approval'].get(),
                    int(fields['max_size'].get() or 10),
                    fields['formats'].get(),
                    int(fields['sort_order'].get() or 0)
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Document type added successfully!")
                dialog.destroy()
                self.load_document_types_full()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add document type: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Save", command=save_document_type).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def edit_document_type_full(self):
        """Edit selected document type"""
        selection = self.gui.doc_types_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document type to edit.")
            return

        item = self.gui.doc_types_tree.item(selection[0])
        type_id = item['values'][0]

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM document_types WHERE type_id = ?', (type_id,))
            doc_type_data = cursor.fetchone()
            conn.close()

            if not doc_type_data:
                messagebox.showerror("Error", "Document type not found.")
                return

            # Create edit dialog (similar to add dialog but pre-populated)
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Document Type")
            dialog.geometry("700x800")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Edit Document Type", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

            # Pre-populate fields with existing data
            fields = {}

            ttk.Label(main_frame, text="Type Name:").pack(anchor='w')
            fields['name'] = tk.Entry(main_frame, width=40)
            fields['name'].insert(0, doc_type_data[1] or "")
            fields['name'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Description:").pack(anchor='w')
            fields['description'] = tk.Text(main_frame, height=3, width=40)
            fields['description'].insert('1.0', doc_type_data[2] or "")
            fields['description'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Category:").pack(anchor='w')
            fields['category'] = ttk.Combobox(main_frame, values=['Identity', 'Academic', 'Immigration', 'Health', 'Financial', 'Other'])
            fields['category'].set(doc_type_data[9] or "")
            fields['category'].pack(fill='x', pady=5)

            fields['required'] = tk.BooleanVar(value=bool(doc_type_data[3]))
            ttk.Checkbutton(main_frame, text="Required Document", variable=fields['required']).pack(anchor='w', pady=5)

            fields['expiry'] = tk.BooleanVar(value=bool(doc_type_data[4]))
            ttk.Checkbutton(main_frame, text="Has Expiry Date", variable=fields['expiry']).pack(anchor='w', pady=5)

            fields['approval'] = tk.BooleanVar(value=bool(doc_type_data[8]))
            ttk.Checkbutton(main_frame, text="Requires Approval", variable=fields['approval']).pack(anchor='w', pady=5)

            ttk.Label(main_frame, text="Max File Size (MB):").pack(anchor='w')
            fields['max_size'] = tk.Entry(main_frame, width=40)
            fields['max_size'].insert(0, str(doc_type_data[6] or 10))
            fields['max_size'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Allowed Formats:").pack(anchor='w')
            fields['formats'] = tk.Entry(main_frame, width=40)
            fields['formats'].insert(0, doc_type_data[7] or "")
            fields['formats'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Sort Order:").pack(anchor='w')
            fields['sort_order'] = tk.Entry(main_frame, width=40)
            fields['sort_order'].insert(0, str(doc_type_data[10] or 0))
            fields['sort_order'].pack(fill='x', pady=5)

            fields['active'] = tk.BooleanVar(value=bool(doc_type_data[11]))
            ttk.Checkbutton(main_frame, text="Active", variable=fields['active']).pack(anchor='w', pady=5)

            def update_document_type():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    UPDATE document_types SET
                    type_name = ?, description = ?, category = ?, is_required = ?,
                    has_expiry = ?, requires_approval = ?, max_file_size_mb = ?,
                    allowed_formats = ?, sort_order = ?, is_active = ?
                    WHERE type_id = ?
                    ''', (
                        fields['name'].get(),
                        fields['description'].get('1.0', 'end-1c'),
                        fields['category'].get(),
                        fields['required'].get(),
                        fields['expiry'].get(),
                        fields['approval'].get(),
                        int(fields['max_size'].get() or 10),
                        fields['formats'].get(),
                        int(fields['sort_order'].get() or 0),
                        fields['active'].get(),
                        type_id
                    ))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Document type updated successfully!")
                    dialog.destroy()
                    self.load_document_types_full()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update document type: {str(e)}")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(15, 0))

            ttk.Button(button_frame, text="Update", command=update_document_type).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load document type data: {str(e)}")

    def delete_document_type_full(self):
        """Delete selected document type"""
        selection = self.gui.doc_types_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document type to delete.")
            return

        item = self.gui.doc_types_tree.item(selection[0])
        type_id = item['values'][0]
        type_name = item['values'][1]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{type_name}'?\n\nThis will also affect any documents of this type."):
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Check if there are documents using this type
                cursor.execute('SELECT COUNT(*) FROM documents WHERE type_id = ?', (type_id,))
                doc_count = cursor.fetchone()[0]

                if doc_count > 0:
                    if not messagebox.askyesno("Warning", f"There are {doc_count} documents using this type. Delete anyway?"):
                        conn.close()
                        return

                # Delete the document type
                cursor.execute('DELETE FROM document_types WHERE type_id = ?', (type_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Document type deleted successfully!")
                self.load_document_types_full()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete document type: {str(e)}")

    def load_document_types(self):
        """Load document types into management interface"""
        if hasattr(self.gui, 'doc_types_tree') and self.gui.doc_types_tree is not None:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT type_id, type_name,
                       COALESCE(category, 'General') as category,
                       is_required, has_expiry,
                       max_file_size_mb, allowed_formats
                FROM document_types WHERE is_active = 1
                ORDER BY COALESCE(sort_order, 0), type_name
                ''')
                doc_types = cursor.fetchall()
                conn.close()

                # Clear existing items
                for item in self.gui.doc_types_tree.get_children():
                    self.gui.doc_types_tree.delete(item)

                # Insert new items
                for doc_type in doc_types:
                    type_id, name, category, required, expiry, max_size, formats = doc_type
                    required_text = "Yes" if required else "No"
                    expiry_text = "Yes" if expiry else "No"

                    self.gui.doc_types_tree.insert('', 'end', values=(
                        type_id, name, category, required_text, expiry_text, max_size, formats
                    ))
            except Exception as e:
                print(f"Error loading document types: {e}")

    def add_document_type(self):
        """Add new document type"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Document Type")
        dialog.geometry("700x800")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Add New Document Type", font=('Arial', 12, 'bold')).pack(pady=10)

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True, pady=10)

        fields = {}

        row = 0
        ttk.Label(form_frame, text="Type Name:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['name'] = ttk.Entry(form_frame, width=30)
        fields['name'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(form_frame, text="Category:").grid(row=row, column=0, sticky='w', pady=5)
        fields['category'] = ttk.Combobox(form_frame, values=['Academic', 'Personal', 'Administrative', 'Financial', 'General'], width=28)
        fields['category'].grid(row=row, column=1, pady=5, padx=10)
        fields['category'].current(4)

        row += 1
        ttk.Label(form_frame, text="Description:").grid(row=row, column=0, sticky='w', pady=5)
        fields['description'] = tk.Text(form_frame, width=30, height=4)
        fields['description'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        fields['required'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Required Document", variable=fields['required']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

        row += 1
        fields['has_expiry'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Has Expiry Date", variable=fields['has_expiry']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

        row += 1
        ttk.Label(form_frame, text="Max File Size (MB):").grid(row=row, column=0, sticky='w', pady=5)
        fields['max_size'] = ttk.Entry(form_frame, width=30)
        fields['max_size'].grid(row=row, column=1, pady=5, padx=10)
        fields['max_size'].insert(0, "10")

        row += 1
        ttk.Label(form_frame, text="Allowed Formats:").grid(row=row, column=0, sticky='w', pady=5)
        fields['formats'] = ttk.Entry(form_frame, width=30)
        fields['formats'].grid(row=row, column=1, pady=5, padx=10)
        fields['formats'].insert(0, "pdf,jpg,png,doc,docx")

        def save_document_type():
            name = fields['name'].get().strip()
            if not name:
                messagebox.showerror("Error", "Type name is required")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO document_types (
                        type_name, category, description, is_required, has_expiry,
                        max_file_size_mb, allowed_formats, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ''', (
                    name,
                    fields['category'].get(),
                    fields['description'].get("1.0", tk.END).strip(),
                    1 if fields['required'].get() else 0,
                    1 if fields['has_expiry'].get() else 0,
                    float(fields['max_size'].get()),
                    fields['formats'].get()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Document type '{name}' added successfully")
                self.load_document_types()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add document type: {e}")

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        ttk.Button(buttons_frame, text="Save", command=save_document_type).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def edit_document_type(self):
        """Edit selected document type"""
        if not hasattr(self.gui, 'doc_types_tree'):
            return

        selection = self.gui.doc_types_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a document type to edit")
            return

        values = self.gui.doc_types_tree.item(selection[0])['values']
        type_id = values[0]

        # Get full document type details
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT type_name, category, description, is_required, has_expiry,
                       max_file_size_mb, allowed_formats
                FROM document_types
                WHERE type_id = ?
            ''', (type_id,))
            doc_type = cursor.fetchone()
            conn.close()

            if not doc_type:
                messagebox.showerror("Error", "Document type not found")
                return

            # Create edit dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Document Type")
            dialog.geometry("700x800")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Edit Document Type", font=('Arial', 12, 'bold')).pack(pady=10)

            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill='both', expand=True, pady=10)

            fields = {}

            row = 0
            ttk.Label(form_frame, text="Type Name:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['name'] = ttk.Entry(form_frame, width=30)
            fields['name'].grid(row=row, column=1, pady=5, padx=10)
            fields['name'].insert(0, doc_type[0])

            row += 1
            ttk.Label(form_frame, text="Category:").grid(row=row, column=0, sticky='w', pady=5)
            fields['category'] = ttk.Combobox(form_frame, values=['Academic', 'Personal', 'Administrative', 'Financial', 'General'], width=28)
            fields['category'].grid(row=row, column=1, pady=5, padx=10)
            fields['category'].set(doc_type[1] or 'General')

            row += 1
            ttk.Label(form_frame, text="Description:").grid(row=row, column=0, sticky='w', pady=5)
            fields['description'] = tk.Text(form_frame, width=30, height=4)
            fields['description'].grid(row=row, column=1, pady=5, padx=10)
            if doc_type[2]:
                fields['description'].insert("1.0", doc_type[2])

            row += 1
            fields['required'] = tk.BooleanVar(value=bool(doc_type[3]))
            ttk.Checkbutton(form_frame, text="Required Document", variable=fields['required']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

            row += 1
            fields['has_expiry'] = tk.BooleanVar(value=bool(doc_type[4]))
            ttk.Checkbutton(form_frame, text="Has Expiry Date", variable=fields['has_expiry']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

            row += 1
            ttk.Label(form_frame, text="Max File Size (MB):").grid(row=row, column=0, sticky='w', pady=5)
            fields['max_size'] = ttk.Entry(form_frame, width=30)
            fields['max_size'].grid(row=row, column=1, pady=5, padx=10)
            fields['max_size'].insert(0, str(doc_type[5]))

            row += 1
            ttk.Label(form_frame, text="Allowed Formats:").grid(row=row, column=0, sticky='w', pady=5)
            fields['formats'] = ttk.Entry(form_frame, width=30)
            fields['formats'].grid(row=row, column=1, pady=5, padx=10)
            fields['formats'].insert(0, doc_type[6] or "")

            def save_changes():
                name = fields['name'].get().strip()
                if not name:
                    messagebox.showerror("Error", "Type name is required")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                        UPDATE document_types SET
                            type_name = ?, category = ?, description = ?,
                            is_required = ?, has_expiry = ?,
                            max_file_size_mb = ?, allowed_formats = ?
                        WHERE type_id = ?
                    ''', (
                        name,
                        fields['category'].get(),
                        fields['description'].get("1.0", tk.END).strip(),
                        1 if fields['required'].get() else 0,
                        1 if fields['has_expiry'].get() else 0,
                        float(fields['max_size'].get()),
                        fields['formats'].get(),
                        type_id
                    ))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Document type updated successfully")
                    self.load_document_types()
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update document type: {e}")

            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(pady=10)

            ttk.Button(buttons_frame, text="Save", command=save_changes).pack(side='left', padx=5)
            ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load document type: {e}")

    def delete_document_type(self):
        """Delete selected document type"""
        if not hasattr(self.gui, 'doc_types_tree'):
            return

        selection = self.gui.doc_types_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a document type to delete")
            return

        values = self.gui.doc_types_tree.item(selection[0])['values']
        type_id = values[0]
        type_name = values[1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete the document type '{type_name}'?\n\n"
                                   "This will not delete existing documents of this type."):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Soft delete - just mark as inactive
            cursor.execute('UPDATE document_types SET is_active = 0 WHERE type_id = ?', (type_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Document type '{type_name}' deleted successfully")
            self.load_document_types()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete document type: {e}")

    def get_document_types(self):
        """Get list of document type names"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1 ORDER BY type_name')
            types = [row[0] for row in cursor.fetchall()]
            conn.close()
            return types
        except Exception:
            return []

    def get_document_types_with_details(self):
        """Get document types with full details"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT type_id, type_name, description, is_required, has_expiry,
                   expiry_reminder_days, max_file_size_mb, allowed_formats
            FROM document_types WHERE is_active = 1 ORDER BY sort_order, type_name
            ''')
            types = cursor.fetchall()
            conn.close()
            return types
        except Exception:
            return []

    def view_document_types(self):
        """View and manage document types"""
        if not self.gui.ensure_login():
            return

        # Create document types window
        types_window = tk.Toplevel(self.root)
        types_window.title("Document Types Management")
        types_window.geometry("900x650")
        types_window.transient(self.root)
        types_window.grab_set()

        # Title
        ttk.Label(types_window, text="Document Types",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Treeview
        tree_frame = ttk.Frame(types_window)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        tree = ttk.Treeview(tree_frame,
                           columns=('Type', 'Count', 'Required', 'Expiry Days', 'Description'),
                           show='headings', height=20)
        tree.heading('Type', text='Document Type')
        tree.heading('Count', text='Documents')
        tree.heading('Required', text='Required')
        tree.heading('Expiry Days', text='Default Expiry (days)')
        tree.heading('Description', text='Description')

        tree.column('Type', width=150)
        tree.column('Count', width=100)
        tree.column('Required', width=80)
        tree.column('Expiry Days', width=150)
        tree.column('Description', width=250)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load_document_types():
            """Load document types from database"""
            for item in tree.get_children():
                tree.delete(item)

            try:
                with get_connection() as conn:
                    cursor = conn.cursor()

                    # Get document types with counts
                    cursor.execute("""
                        SELECT dt.type_name, dt.is_required, dt.default_expiry_days,
                               dt.description, COUNT(d.id) as doc_count
                        FROM document_types dt
                        LEFT JOIN documents d ON d.document_type = dt.type_name
                        GROUP BY dt.type_name
                        ORDER BY dt.type_name
                    """)
                    results = cursor.fetchall()

                    for row in results:
                        type_name, is_required, expiry_days, description, doc_count = row
                        required_text = "Yes" if is_required else "No"
                        expiry_text = str(expiry_days) if expiry_days else "None"
                        tree.insert('', 'end', values=(type_name, doc_count, required_text,
                                                      expiry_text, description or ''))

            except Exception:
                # If table doesn't exist, show default types
                default_types = [
                    ('Transcript', 0, 'No', '365', 'Academic transcript'),
                    ('ID Card', 0, 'Yes', '1825', 'Student ID card'),
                    ('Health Form', 0, 'Yes', '365', 'Health/Medical form'),
                    ('Enrollment Form', 0, 'Yes', 'None', 'Enrollment documentation'),
                    ('Financial Document', 0, 'No', '365', 'Financial aid/payment docs'),
                    ('Recommendation Letter', 0, 'No', 'None', 'Letters of recommendation')
                ]
                for row in default_types:
                    tree.insert('', 'end', values=row)

        load_document_types()

        # Button frame
        button_frame = ttk.Frame(types_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text="Add Type",
                  command=lambda: self.modify_document_type('add', tree, load_document_types)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Edit Type",
                  command=lambda: self.modify_document_type('edit', tree, load_document_types)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete Type",
                  command=lambda: self.modify_document_type('delete', tree, load_document_types)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=load_document_types).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close",
                  command=types_window.destroy).pack(side='right', padx=5)

        # Log activity
        self.gui.log_event('view', 'document_types', details='Viewed document types management')

    def modify_document_type(self, operation, tree=None, refresh_callback=None):
        """Add, edit, or delete document type"""
        if operation == 'delete':
            if not tree:
                return

            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select a document type to delete")
                return

            type_name = tree.item(selected[0], 'values')[0]

            if messagebox.askyesno("Confirm Delete",
                                  f"Are you sure you want to delete document type '{type_name}'?\n\n"
                                  "This will not delete existing documents of this type."):
                try:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM document_types WHERE type_name = ?", (type_name,))

                    messagebox.showinfo("Success", f"Document type '{type_name}' deleted")
                    self.gui.log_event('delete', 'document_type', details=f'Deleted type: {type_name}')

                    if refresh_callback:
                        refresh_callback()

                except Exception as e:
                    messagebox.showerror("Delete Error", f"Failed to delete document type: {e}")

            return

        # Add or Edit
        is_edit = operation == 'edit'
        if is_edit and tree:
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select a document type to edit")
                return

            values = tree.item(selected[0], 'values')
            type_name, _, is_required, expiry_days, description = values
        else:
            type_name, is_required, expiry_days, description = '', 'No', 'None', ''

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Document Type" if is_edit else "Add Document Type")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Form
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        ttk.Label(form_frame, text="Type Name: *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=40)
        name_entry.insert(0, type_name)
        if is_edit:
            name_entry.config(state='readonly')
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Required:").grid(row=1, column=0, sticky='w', pady=5)
        required_var = tk.BooleanVar(value=is_required == 'Yes')
        ttk.Checkbutton(form_frame, text="This document type is required",
                       variable=required_var).grid(row=1, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Default Expiry (days):").grid(row=2, column=0, sticky='w', pady=5)
        expiry_entry = ttk.Entry(form_frame, width=40)
        expiry_entry.insert(0, expiry_days if expiry_days != 'None' else '')
        expiry_entry.grid(row=2, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Description:").grid(row=3, column=0, sticky='w', pady=5)
        desc_text = tk.Text(form_frame, width=40, height=5)
        desc_text.insert('1.0', description)
        desc_text.grid(row=3, column=1, sticky='ew', pady=5)

        form_frame.columnconfigure(1, weight=1)

        def submit():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Validation Error", "Type name is required")
                return

            required = 1 if required_var.get() else 0
            expiry = expiry_entry.get().strip()
            expiry = int(expiry) if expiry else None
            desc = desc_text.get('1.0', 'end-1c').strip()

            try:
                with transaction() as conn:
                    cursor = conn.cursor()

                    # Create table if not exists
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS document_types (
                            type_name TEXT PRIMARY KEY,
                            is_required INTEGER DEFAULT 0,
                            default_expiry_days INTEGER,
                            description TEXT
                        )
                    """)

                    if is_edit:
                        cursor.execute("""
                            UPDATE document_types
                            SET is_required = ?, default_expiry_days = ?, description = ?
                            WHERE type_name = ?
                        """, (required, expiry, desc, name))
                        action = 'update'
                    else:
                        cursor.execute("""
                            INSERT INTO document_types (type_name, is_required,
                                                       default_expiry_days, description)
                            VALUES (?, ?, ?, ?)
                        """, (name, required, expiry, desc))
                        action = 'create'

                messagebox.showinfo("Success",
                                  f"Document type {'updated' if is_edit else 'added'} successfully!")

                self.gui.log_event(action, 'document_type', details=f'Type: {name}')

                if refresh_callback:
                    refresh_callback()

                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save document type: {e}")

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill='x', padx=20, pady=10)

        ttk.Button(button_frame, text="Save", command=submit).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def document_type_management(self):
        """Comprehensive document type management interface"""
        # This is a wrapper that calls view_document_types
        self.view_document_types()
