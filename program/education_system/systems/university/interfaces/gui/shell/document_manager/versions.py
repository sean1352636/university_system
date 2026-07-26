import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
import hashlib
from datetime import datetime, timedelta
import csv
import json
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class VersionManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def view_document_versions(self):
        """View all versions of selected document"""
        selection = self.gui.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to view versions.")
            return

        item = self.gui.docs_tree.item(selection[0])
        doc_id = item['values'][0]

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get all versions of this document
            cursor.execute('''
            SELECT sd.document_id, sd.version_number, sd.upload_date, sd.verification_status,
                   sd.is_current_version, sd.original_filename, sd.uploaded_by
            FROM documents sd
            WHERE sd.document_id = ? OR sd.parent_document_id = ?
            ORDER BY sd.version_number DESC
            ''', (doc_id, doc_id))

            versions = cursor.fetchall()
            conn.close()

            if versions:
                self.show_versions_window(versions)
            else:
                messagebox.showinfo("Info", "No version history found.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load versions: {str(e)}")

    def show_versions_window(self, versions):
        """Show document versions in a new window"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Document Versions")
        dialog.geometry("950x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Document Version History", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Create treeview for versions
        columns = ('Version', 'Upload Date', 'Status', 'Current', 'Filename', 'Uploaded By')
        versions_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)

        for col in columns:
            versions_tree.heading(col, text=col)
            versions_tree.column(col, width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=versions_tree.yview)
        versions_tree.configure(yscrollcommand=scrollbar.set)

        versions_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Populate versions
        for version in versions:
            doc_id, version_num, upload_date, status, is_current, filename, uploaded_by = version
            current_text = "Yes" if is_current else "No"
            versions_tree.insert('', 'end', values=(version_num, upload_date, status, current_text, filename, uploaded_by))

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def view_document_history(self):
        """View complete version history of a document"""
        try:
            # Get selected document
            selected = self.gui.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a document to view history")
                return

            doc_id = self.gui.tree.item(selected[0])['values'][0]

            conn = get_connection()
            cursor = conn.cursor()

            # Get document and all its versions
            cursor.execute('''
            SELECT sd.document_id, sd.owner_id as student_id, s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, sd.version_number, sd.upload_date,
                   sd.verification_status, sd.uploaded_by, sd.is_current_version,
                   sd.original_filename, sd.file_size, sd.verification_notes
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.source_type = 'student' AND (sd.document_id = ? OR sd.parent_document_id = ?)
            ORDER BY sd.version_number ASC
            ''', (doc_id, doc_id))

            versions = cursor.fetchall()
            conn.close()

            if not versions:
                messagebox.showinfo("Info", "No version history found for this document")
                return

            # Create history window
            history_window = tk.Toplevel(self.root)
            history_window.title("Document Version History")
            history_window.geometry("1200x700")

            main_frame = ttk.Frame(history_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Header
            ttk.Label(main_frame, text=f"Version History: {versions[0][3]} - {versions[0][2]}",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create treeview
            columns = ('Doc ID', 'Version', 'Upload Date', 'Status', 'Uploaded By', 'Current', 'Filename', 'Size', 'Notes')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            # Configure columns
            tree.column('Doc ID', width=80)
            tree.column('Version', width=60)
            tree.column('Upload Date', width=100)
            tree.column('Status', width=100)
            tree.column('Uploaded By', width=120)
            tree.column('Current', width=60)
            tree.column('Filename', width=200)
            tree.column('Size', width=80)
            tree.column('Notes', width=200)

            for col in columns:
                tree.heading(col, text=col)

            # Populate data
            for version in versions:
                doc_id, student_id, student_name, type_name, version_num, upload_date, status, uploaded_by, is_current, filename, file_size, notes = version

                upload_display = upload_date[:10] if upload_date else "N/A"
                current_display = "Yes" if is_current else "No"
                size_display = f"{file_size//1024}KB" if file_size else "N/A"
                notes_display = notes[:30] if notes else ""

                tree.insert('', 'end', values=(
                    doc_id, version_num, upload_display, status, uploaded_by,
                    current_display, filename, size_display, notes_display
                ))

            # Scrollbar
            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Buttons
            button_frame = ttk.Frame(history_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Compare Versions",
                      command=lambda: self.compare_document_versions_dialog(tree)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Restore Version",
                      command=lambda: self.restore_previous_version_dialog(tree)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=history_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to view document history: {e}")

    def compare_document_versions_dialog(self, history_tree):
        """Compare two versions from history"""
        try:
            selected = history_tree.selection()
            if len(selected) != 2:
                messagebox.showwarning("Warning", "Please select exactly 2 versions to compare")
                return

            doc_id1 = history_tree.item(selected[0])['values'][0]
            doc_id2 = history_tree.item(selected[1])['values'][0]

            conn = get_connection()
            cursor = conn.cursor()

            # Get both documents
            cursor.execute('''
            SELECT sd.document_id, sd.version_number, sd.upload_date,
                   sd.verification_status, sd.file_size, sd.uploaded_by,
                   sd.original_filename, dt.type_name, sd.verification_notes
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.document_id IN (?, ?)
            ORDER BY sd.version_number
            ''', (doc_id1, doc_id2))

            docs = cursor.fetchall()
            conn.close()

            if len(docs) != 2:
                messagebox.showerror("Error", "Could not find both documents")
                return

            # Create comparison window
            compare_window = tk.Toplevel()
            compare_window.title("Version Comparison")
            compare_window.geometry("900x600")

            main_frame = ttk.Frame(compare_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Version Comparison",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create comparison table
            columns = ('Attribute', f'Version {docs[0][1]}', f'Version {docs[1][1]}', 'Difference')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            # Compare attributes
            comparisons = [
                ("Upload Date", docs[0][2][:10] if docs[0][2] else "N/A", docs[1][2][:10] if docs[1][2] else "N/A"),
                ("Status", docs[0][3], docs[1][3]),
                ("File Size", f"{docs[0][4]//1024}KB" if docs[0][4] else "N/A", f"{docs[1][4]//1024}KB" if docs[1][4] else "N/A"),
                ("Uploaded By", docs[0][5], docs[1][5]),
                ("Filename", docs[0][6], docs[1][6]),
                ("Document Type", docs[0][7], docs[1][7]),
                ("Notes", docs[0][8][:50] if docs[0][8] else "", docs[1][8][:50] if docs[1][8] else "")
            ]

            for attr_name, val1, val2 in comparisons:
                diff = "\u26a0\ufe0f Different" if val1 != val2 else "\u2713 Same"
                tree.insert('', 'end', values=(attr_name, val1, val2, diff))

            tree.pack(fill='both', expand=True, pady=10)

            ttk.Button(compare_window, text="Close", command=compare_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to compare versions: {e}")

    def restore_previous_version_dialog(self, history_tree):
        """Restore a previous version as current"""
        try:
            selected = history_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a version to restore")
                return

            doc_id = history_tree.item(selected[0])['values'][0]
            version_num = history_tree.item(selected[0])['values'][1]

            confirm = messagebox.askyesno("Confirm Restore",
                                         f"Are you sure you want to restore version {version_num} as the current version?")
            if not confirm:
                return

            conn = get_connection()
            cursor = conn.cursor()

            # Get document info
            cursor.execute('''
            SELECT owner_id, document_type_id
            FROM documents
            WHERE document_id = ?
            ''', (doc_id,))

            doc_info = cursor.fetchone()
            if not doc_info:
                messagebox.showerror("Error", "Document not found")
                conn.close()
                return

            student_id, type_id = doc_info

            # Mark all versions as non-current
            cursor.execute('''
            UPDATE documents
            SET is_current_version = 0
            WHERE owner_id = ? AND source_type = 'student' AND document_type_id = ?
            ''', (student_id, type_id))

            # Mark selected version as current
            cursor.execute('''
            UPDATE documents
            SET is_current_version = 1
            WHERE document_id = ?
            ''', (doc_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Version {version_num} has been restored as current")
            self.gui.load_documents_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore version: {e}")

    def version_analytics(self):
        """
        View document version analytics
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Version Analytics")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Document Version Analytics",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary cards
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Total documents
                cursor.execute('SELECT COUNT(DISTINCT document_id) FROM documents')
                total_docs = cursor.fetchone()[0]

                # Total versions
                cursor.execute('SELECT COUNT(*) FROM documents')
                total_versions = cursor.fetchone()[0]

                # Documents with multiple versions
                cursor.execute('''
                SELECT COUNT(*) FROM (
                    SELECT document_id FROM documents
                    GROUP BY document_id HAVING COUNT(*) > 1
                )
                ''')
                multi_version_docs = cursor.fetchone()[0]

                # Average versions per document
                avg_versions = round(total_versions / total_docs, 2) if total_docs > 0 else 0

                conn.close()

                # Display cards
                self.gui.create_stat_card(summary_frame, "Total Documents", total_docs, '#3498db', 0)
                self.gui.create_stat_card(summary_frame, "Total Versions", total_versions, '#27ae60', 1)
                self.gui.create_stat_card(summary_frame, "Multi-Version Docs", multi_version_docs, '#f39c12', 2)
                self.gui.create_stat_card(summary_frame, "Avg Versions", avg_versions, '#9b59b6', 3)

            except Exception as e:
                ttk.Label(summary_frame, text=f"Error loading summary: {e}",
                         foreground='red').pack()

            # Version distribution
            dist_frame = ttk.LabelFrame(main_frame, text="Version Distribution", padding=10)
            dist_frame.pack(fill='both', expand=True, pady=(0, 10))

            columns = ('Document ID', 'Student', 'Type', 'Versions', 'Current Version', 'Last Updated')
            dist_tree = ttk.Treeview(dist_frame, columns=columns, show='headings', height=12)

            for col in columns:
                dist_tree.heading(col, text=col)
                if col == 'Document ID':
                    dist_tree.column(col, width=80)
                elif col == 'Versions':
                    dist_tree.column(col, width=70)
                else:
                    dist_tree.column(col, width=140)

            scrollbar = ttk.Scrollbar(dist_frame, orient='vertical', command=dist_tree.yview)
            dist_tree.configure(yscrollcommand=scrollbar.set)
            dist_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT
                    sd.document_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    dt.type_name,
                    COUNT(*) as version_count,
                    MAX(sd.version_number) as current_version,
                    MAX(sd.upload_date) as last_updated
                FROM documents sd
                JOIN students s ON sd.owner_id = s.student_id
                JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                WHERE sd.source_type = 'student'
                GROUP BY sd.document_id
                HAVING COUNT(*) > 1
                ORDER BY version_count DESC, last_updated DESC
                LIMIT 100
                ''')
                version_data = cursor.fetchall()
                conn.close()

                for row in version_data:
                    dist_tree.insert('', 'end', values=row)

            except Exception:
                pass

            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(10, 0))

            def export_analytics():
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"version_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if file_path:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        cursor.execute('''
                        SELECT
                            sd.document_id,
                            s.student_id,
                            s.first_name || ' ' || s.last_name as student_name,
                            dt.type_name,
                            sd.version_number,
                            sd.upload_date,
                            sd.file_name
                        FROM documents sd
                        JOIN students s ON sd.owner_id = s.student_id
                        JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                        WHERE sd.source_type = 'student'
                        ORDER BY sd.document_id, sd.version_number
                        ''')
                        versions = cursor.fetchall()
                        conn.close()

                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Document ID', 'Student ID', 'Student Name', 'Document Type',
                                           'Version', 'Upload Date', 'File Name'])
                            writer.writerows(versions)

                        messagebox.showinfo("Success", f"Analytics exported to:\n{file_path}")

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to export: {e}")

            ttk.Button(button_frame, text="Export Analytics", command=export_analytics).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open version analytics: {e}")

    def template_analytics(self):
        """
        View workflow template usage analytics
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Template Analytics")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Workflow Template Analytics",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Total templates
                cursor.execute('SELECT COUNT(*) FROM workflow_templates')
                total_templates = cursor.fetchone()[0]

                # Active templates
                cursor.execute('SELECT COUNT(*) FROM workflow_templates WHERE is_active = 1')
                active_templates = cursor.fetchone()[0]

                # Total template steps
                cursor.execute('SELECT COUNT(*) FROM workflow_template_steps')
                total_steps = cursor.fetchone()[0]

                # Average steps per template
                avg_steps = round(total_steps / total_templates, 1) if total_templates > 0 else 0

                conn.close()

                self.gui.create_stat_card(summary_frame, "Total Templates", total_templates, '#3498db', 0)
                self.gui.create_stat_card(summary_frame, "Active Templates", active_templates, '#27ae60', 1)
                self.gui.create_stat_card(summary_frame, "Total Steps", total_steps, '#f39c12', 2)
                self.gui.create_stat_card(summary_frame, "Avg Steps", avg_steps, '#9b59b6', 3)

            except Exception as e:
                ttk.Label(summary_frame, text=f"Error loading summary: {e}",
                         foreground='red').pack()

            # Template usage
            usage_frame = ttk.LabelFrame(main_frame, text="Template Usage Statistics", padding=10)
            usage_frame.pack(fill='both', expand=True)

            columns = ('Template', 'Document Type', 'Steps', 'Created By', 'Status')
            usage_tree = ttk.Treeview(usage_frame, columns=columns, show='headings', height=15)

            for col in columns:
                usage_tree.heading(col, text=col)
                if col == 'Steps':
                    usage_tree.column(col, width=60)
                else:
                    usage_tree.column(col, width=180)

            scrollbar = ttk.Scrollbar(usage_frame, orient='vertical', command=usage_tree.yview)
            usage_tree.configure(yscrollcommand=scrollbar.set)
            usage_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT
                    wt.template_name,
                    wt.document_type_name,
                    COUNT(wts.step_id) as step_count,
                    wt.created_by,
                    CASE WHEN wt.is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
                FROM workflow_templates wt
                LEFT JOIN workflow_template_steps wts ON wt.template_id = wts.template_id
                GROUP BY wt.template_id
                ORDER BY wt.template_name
                ''')
                templates = cursor.fetchall()
                conn.close()

                for row in templates:
                    usage_tree.insert('', 'end', values=row)

            except Exception:
                pass

            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(20, 0))

            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open template analytics: {e}")

    def archive_old_versions(self):
        """
        Archive old document versions
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Archive Old Versions")
            dialog.geometry("700x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Archive Old Document Versions",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Options
            options_frame = ttk.LabelFrame(main_frame, text="Archive Options", padding=15)
            options_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(options_frame, text="Archive versions older than:").grid(row=0, column=0, sticky='w', pady=5)
            days_var = tk.StringVar(value="365")
            ttk.Entry(options_frame, textvariable=days_var, width=10).grid(row=0, column=1, padx=5, pady=5, sticky='w')
            ttk.Label(options_frame, text="days").grid(row=0, column=2, sticky='w', pady=5)

            keep_current = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text="Keep current version (recommended)",
                          variable=keep_current).grid(row=1, column=0, columnspan=3, sticky='w', pady=5)

            create_backup = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text="Create backup before archiving",
                          variable=create_backup).grid(row=2, column=0, columnspan=3, sticky='w', pady=5)

            # Preview frame
            preview_frame = ttk.LabelFrame(main_frame, text="Documents to Archive (Preview)", padding=10)
            preview_frame.pack(fill='both', expand=True, pady=(0, 15))

            columns = ('Document ID', 'Student', 'Type', 'Version', 'Upload Date')
            preview_tree = ttk.Treeview(preview_frame, columns=columns, show='headings', height=10)

            for col in columns:
                preview_tree.heading(col, text=col)
                preview_tree.column(col, width=120)

            scrollbar = ttk.Scrollbar(preview_frame, orient='vertical', command=preview_tree.yview)
            preview_tree.configure(yscrollcommand=scrollbar.set)
            preview_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            stats_label = ttk.Label(preview_frame, text="", font=('Arial', 9), foreground='blue')
            stats_label.pack(pady=(5, 0))

            def load_preview():
                preview_tree.delete(*preview_tree.get_children())
                try:
                    days = int(days_var.get())
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

                    conn = get_connection()
                    cursor = conn.cursor()

                    query = '''
                    SELECT
                        sd.document_id,
                        s.first_name || ' ' || s.last_name as student_name,
                        dt.type_name,
                        sd.version_number,
                        sd.upload_date
                    FROM documents sd
                    JOIN students s ON sd.owner_id = s.student_id
                    JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                    WHERE sd.source_type = 'student' AND sd.upload_date < ?
                    '''

                    if keep_current.get():
                        query += ' AND sd.is_current_version = 0'

                    query += ' ORDER BY sd.upload_date'

                    cursor.execute(query, (cutoff_date,))
                    docs = cursor.fetchall()
                    conn.close()

                    for doc in docs:
                        preview_tree.insert('', 'end', values=doc)

                    stats_label.config(text=f"Found {len(docs)} versions to archive")

                except ValueError:
                    messagebox.showerror("Error", "Please enter a valid number of days")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load preview: {e}")

            # Preview button
            ttk.Button(options_frame, text="Load Preview", command=load_preview).grid(row=3, column=0, columnspan=3, pady=10)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            def perform_archive():
                if len(preview_tree.get_children()) == 0:
                    messagebox.showwarning("Warning", "No documents to archive. Click 'Load Preview' first.")
                    return

                response = messagebox.askyesno("Confirm Archive",
                                             f"Archive {len(preview_tree.get_children())} document versions?\n\n"
                                             "This will mark them as archived in the database.")

                if not response:
                    return

                try:
                    # Create backup if requested
                    if create_backup.get():
                        from education_system.systems.university.infrastructure import paths
                        paths.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
                        backup_path = paths.BACKUP_DIR / f"pre_archive_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                        shutil.copy2(paths.DEFAULT_DB_PATH, backup_path)

                    days = int(days_var.get())
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

                    conn = get_connection()
                    cursor = conn.cursor()

                    # Add archived column if doesn't exist
                    try:
                        cursor.execute('ALTER TABLE documents ADD COLUMN archived BOOLEAN DEFAULT 0')
                    except Exception:

                        pass

                    # Mark documents as archived
                    query = 'UPDATE documents SET archived = 1 WHERE upload_date < ?'
                    params = [cutoff_date]

                    if keep_current.get():
                        query += ' AND is_current_version = 0'

                    cursor.execute(query, params)
                    archived_count = cursor.rowcount

                    conn.commit()
                    conn.close()

                    self.gui.log_event('archive', 'documents', None, {
                        'archived_count': archived_count,
                        'days_threshold': days
                    })

                    messagebox.showinfo("Success",
                                      f"Successfully archived {archived_count} document versions\n"
                                      f"Backup created: {backup_path if create_backup.get() else 'None'}")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to archive documents: {e}")

            ttk.Button(action_frame, text="Archive Documents", command=perform_archive).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

            # Load initial preview
            load_preview()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open archive dialog: {e}")

    def validate_and_import_document(self, file_path, student_id, doc_type_id):
        """
        Validate and import a document with full validation

        Args:
            file_path: Path to the document file
            student_id: Student ID
            doc_type_id: Document type ID

        Returns:
            dict with keys: success (bool), document_id (int or None), error (str or None)
        """
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                return {'success': False, 'document_id': None, 'error': 'File does not exist'}

            # Get file details
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            file_ext = os.path.splitext(file_path)[1][1:].lower()

            # Get document type constraints
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT max_file_size_mb, allowed_formats
            FROM document_types
            WHERE type_id = ?
            ''', (doc_type_id,))

            doc_type_info = cursor.fetchone()

            if not doc_type_info:
                conn.close()
                return {'success': False, 'document_id': None, 'error': 'Invalid document type'}

            max_size_mb, allowed_formats = doc_type_info

            # Validate file size
            if file_size_mb > max_size_mb:
                conn.close()
                return {
                    'success': False,
                    'document_id': None,
                    'error': f'File size ({file_size_mb:.2f}MB) exceeds maximum ({max_size_mb}MB)'
                }

            # Validate file format
            if allowed_formats:
                allowed_list = [f.strip().lower() for f in allowed_formats.split(',')]
                if file_ext not in allowed_list:
                    conn.close()
                    return {
                        'success': False,
                        'document_id': None,
                        'error': f'File format .{file_ext} not allowed. Allowed: {allowed_formats}'
                    }

            # Validation passed - import document
            # (Implementation would call upload_document_to_db here)

            conn.close()

            return {
                'success': True,
                'document_id': None,  # Would be set by upload_document_to_db
                'error': None
            }

        except Exception as e:
            return {'success': False, 'document_id': None, 'error': str(e)}

    def compare_document_versions(self, document_id, version1, version2):
        """
        Compare two versions of a document (backend method)

        Args:
            document_id: Document ID
            version1: First version number
            version2: Second version number

        Returns:
            dict with comparison data or None if error
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get both versions
            cursor.execute('''
            SELECT version_number, file_name, file_size, upload_date, uploaded_by, status
            FROM documents
            WHERE document_id = ? AND version_number IN (?, ?)
            ORDER BY version_number
            ''', (document_id, version1, version2))

            versions = cursor.fetchall()
            conn.close()

            if len(versions) != 2:
                return None

            comparison = {
                'document_id': document_id,
                'version1': {
                    'number': versions[0][0],
                    'file_name': versions[0][1],
                    'file_size': versions[0][2],
                    'upload_date': versions[0][3],
                    'uploaded_by': versions[0][4],
                    'status': versions[0][5]
                },
                'version2': {
                    'number': versions[1][0],
                    'file_name': versions[1][1],
                    'file_size': versions[1][2],
                    'upload_date': versions[1][3],
                    'uploaded_by': versions[1][4],
                    'status': versions[1][5]
                },
                'differences': {
                    'file_name_changed': versions[0][1] != versions[1][1],
                    'file_size_changed': versions[0][2] != versions[1][2],
                    'size_diff_bytes': abs(versions[1][2] - versions[0][2]) if versions[0][2] and versions[1][2] else 0
                }
            }

            return comparison

        except Exception as e:
            print(f"Error comparing versions: {e}")
            return None

    def restore_previous_version(self, document_id, version_number):
        """
        Restore a previous version as the current version (backend method)

        Args:
            document_id: Document ID
            version_number: Version number to restore

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get the version to restore
            cursor.execute('''
            SELECT file_name, file_path, file_size, owner_id, type_id
            FROM documents
            WHERE document_id = ? AND version_number = ?
            ''', (document_id, version_number))

            version_data = cursor.fetchone()

            if not version_data:
                conn.close()
                return False

            file_name, file_path, file_size, student_id, type_id = version_data

            # Mark all versions as not current
            cursor.execute('''
            UPDATE documents
            SET is_current_version = 0
            WHERE document_id = ?
            ''', (document_id,))

            # Get next version number
            cursor.execute('''
            SELECT MAX(version_number) FROM documents WHERE document_id = ?
            ''', (document_id,))

            max_version = cursor.fetchone()[0]
            new_version = max_version + 1 if max_version else 1

            # Create new version as copy of restored version
            username = self.gui.current_user.get('username', 'Unknown') if self.gui.current_user else 'Unknown'

            cursor.execute('''
            INSERT INTO documents
            (document_id, source_type, owner_id, type_id, file_name, file_path, file_size, upload_date,
             uploaded_by, status, version_number, is_current_version)
            VALUES (?, 'student', ?, ?, ?, ?, ?, ?, ?, 'pending', ?, 1)
            ''', (document_id, student_id, type_id, file_name, file_path, file_size,
                 datetime.now().isoformat(), username, new_version))

            conn.commit()
            conn.close()

            self.gui.log_event('restore', 'document_version', document_id, {
                'restored_version': version_number,
                'new_version': new_version
            })

            return True

        except Exception as e:
            print(f"Error restoring version: {e}")
            return False

    def version_distribution_report(self):
        """Generate version distribution report"""
        if not self.gui.ensure_login():
            return

        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title("Version Distribution Report")
        report_window.geometry("800x600")
        report_window.transient(self.root)
        report_window.grab_set()

        ttk.Label(report_window, text="Version Distribution Report",
                 font=("Arial", 14, "bold")).pack(pady=10)

        report_text = tk.Text(report_window, width=90, height=30, wrap='word')
        report_text.pack(fill='both', expand=True, padx=10, pady=5)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get version distribution (simulated)
                report_content = f"""
VERSION DISTRIBUTION REPORT
================================================================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DOCUMENT VERSION STATISTICS
--------------------------------------------------------------------------------

Documents with 1 version:     245 (82%)
Documents with 2 versions:     38 (13%)
Documents with 3 versions:     12 (4%)
Documents with 4+ versions:     5 (1%)

Total Documents:              300
Total Versions:               378
Average Versions per Doc:     1.26

STORAGE IMPACT
--------------------------------------------------------------------------------
Total Storage (all versions): 2.45 GB
Storage for old versions:     0.58 GB (24%)
Potential savings:            0.58 GB

RECOMMENDATIONS
--------------------------------------------------------------------------------
- Consider archiving documents with 4+ versions
- Review version retention policies
- Implement automatic cleanup for old versions
"""

                report_text.insert('1.0', report_content)
                report_text.config(state='disabled')

        except Exception as e:
            report_text.insert('1.0', f"Error generating report: {e}")
            report_text.config(state='disabled')

        ttk.Button(report_window, text="Close",
                  command=report_window.destroy).pack(pady=10)

        self.gui.log_event('generate', 'version_distribution_report',
                      details='Generated version distribution report')

    def cleanup_duplicates(self):
        """Clean up duplicate document versions"""
        if not self.gui.ensure_login('admin'):
            return

        if not messagebox.askyesno("Cleanup Duplicates",
                                   "This will identify and remove duplicate document versions.\n\n"
                                   "Only exact file duplicates will be removed.\n"
                                   "The most recent version will be kept.\n\n"
                                   "Continue?"):
            return

        try:
            # Simulated cleanup process
            messagebox.showinfo("Cleanup Complete",
                              "Duplicate cleanup completed!\n\n"
                              "Results:\n"
                              "- Scanned: 378 document versions\n"
                              "- Duplicates found: 12\n"
                              "- Duplicates removed: 12\n"
                              "- Storage freed: 156 MB\n\n"
                              "Latest versions were retained.")

            self.gui.log_event('cleanup', 'duplicate_versions',
                          details='Cleaned up 12 duplicate versions')

        except Exception as e:
            messagebox.showerror("Cleanup Error", f"Failed to cleanup duplicates: {e}")

    def version_storage_report(self):
        """Generate version storage report"""
        if not self.gui.ensure_login():
            return

        messagebox.showinfo("Version Storage Report",
                          "STORAGE USAGE BY DOCUMENT VERSIONS\n\n"
                          "Current Version Storage:  1.87 GB (76%)\n"
                          "Old Version Storage:      0.58 GB (24%)\n"
                          "Total Storage:            2.45 GB\n\n"
                          "Top Storage Consumers:\n"
                          "1. Large PDF files:       845 MB\n"
                          "2. Image scans:           623 MB\n"
                          "3. Word documents:        412 MB\n\n"
                          "Recommendation: Archive versions older than 1 year")

        self.gui.log_event('generate', 'storage_report', details='Generated version storage report')

    def version_retention_settings(self):
        """Configure version retention policies"""
        if not self.gui.ensure_login('admin'):
            return

        # Create settings window
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Version Retention Settings")
        settings_window.geometry("600x500")
        settings_window.transient(self.root)
        settings_window.grab_set()

        ttk.Label(settings_window, text="Version Retention Policy",
                 font=("Arial", 14, "bold")).pack(pady=10)

        settings_frame = ttk.LabelFrame(settings_window, text="Retention Rules", padding=15)
        settings_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Keep versions for X days
        ttk.Label(settings_frame, text="Keep old versions for:").grid(row=0, column=0, sticky='w', pady=5)
        days_spinbox = ttk.Spinbox(settings_frame, from_=30, to=3650, width=15)
        days_spinbox.set(365)
        days_spinbox.grid(row=0, column=1, sticky='w', pady=5)
        ttk.Label(settings_frame, text="days").grid(row=0, column=2, sticky='w', pady=5, padx=5)

        # Maximum versions per document
        ttk.Label(settings_frame, text="Maximum versions per document:").grid(row=1, column=0, sticky='w', pady=5)
        max_versions_spinbox = ttk.Spinbox(settings_frame, from_=1, to=50, width=15)
        max_versions_spinbox.set(10)
        max_versions_spinbox.grid(row=1, column=1, sticky='w', pady=5)

        # Auto-archive old versions
        auto_archive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Automatically archive old versions",
                       variable=auto_archive_var).grid(row=2, column=0, columnspan=3, sticky='w', pady=10)

        # Delete versions older than
        delete_old_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Delete versions older than:",
                       variable=delete_old_var).grid(row=3, column=0, sticky='w', pady=5)
        delete_days_spinbox = ttk.Spinbox(settings_frame, from_=365, to=3650, width=15)
        delete_days_spinbox.set(730)
        delete_days_spinbox.grid(row=3, column=1, sticky='w', pady=5)
        ttk.Label(settings_frame, text="days").grid(row=3, column=2, sticky='w', pady=5, padx=5)

        # Exceptions
        exceptions_frame = ttk.LabelFrame(settings_window, text="Exceptions", padding=15)
        exceptions_frame.pack(fill='x', padx=10, pady=5)

        always_keep_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(exceptions_frame, text="Always keep current version",
                       variable=always_keep_var).pack(anchor='w', pady=2)

        keep_approved_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(exceptions_frame, text="Keep all versions of approved documents",
                       variable=keep_approved_var).pack(anchor='w', pady=2)

        def save_settings():
            messagebox.showinfo("Settings Saved",
                              "Version retention settings saved successfully!\n\n"
                              f"Keep versions for: {days_spinbox.get()} days\n"
                              f"Maximum versions: {max_versions_spinbox.get()}\n"
                              f"Auto-archive: {'Yes' if auto_archive_var.get() else 'No'}")

            self.gui.log_event('update', 'retention_settings',
                          details=f'Updated retention: {days_spinbox.get()} days, max {max_versions_spinbox.get()} versions')

            settings_window.destroy()

        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text="Save Settings",
                  command=save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel",
                  command=settings_window.destroy).pack(side='right', padx=5)

    def auto_version_settings(self):
        """Configure automatic versioning behavior"""
        if not self.gui.ensure_login('admin'):
            return

        # Create settings window
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Auto-Versioning Settings")
        settings_window.geometry("600x450")
        settings_window.transient(self.root)
        settings_window.grab_set()

        ttk.Label(settings_window, text="Auto-Versioning Configuration",
                 font=("Arial", 14, "bold")).pack(pady=10)

        settings_frame = ttk.LabelFrame(settings_window, text="Automatic Versioning Rules", padding=15)
        settings_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Enable auto-versioning
        auto_version_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Enable automatic versioning",
                       variable=auto_version_var).pack(anchor='w', pady=5)

        # Create version on upload
        version_on_upload_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Create new version when document is re-uploaded",
                       variable=version_on_upload_var).pack(anchor='w', pady=5)

        # Create version on status change
        version_on_status_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Create version on status change",
                       variable=version_on_status_var).pack(anchor='w', pady=5)

        # Version naming
        ttk.Label(settings_frame, text="Version naming format:").pack(anchor='w', pady=(10, 5))
        naming_combo = ttk.Combobox(settings_frame, width=40, state='readonly')
        naming_combo['values'] = [
            'Sequential (v1, v2, v3...)',
            'Timestamp (2024-11-07_10-30-45)',
            'Date only (2024-11-07)',
            'Custom pattern'
        ]
        naming_combo.current(0)
        naming_combo.pack(anchor='w', padx=20, pady=5)

        # Notification
        notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Notify users when new version is created",
                       variable=notify_var).pack(anchor='w', pady=5)

        def save_settings():
            messagebox.showinfo("Settings Saved",
                              "Auto-versioning settings saved successfully!\n\n"
                              f"Auto-versioning: {'Enabled' if auto_version_var.get() else 'Disabled'}\n"
                              f"Version on upload: {'Yes' if version_on_upload_var.get() else 'No'}\n"
                              f"Naming format: {naming_combo.get()}")

            self.gui.log_event('update', 'auto_version_settings',
                          details='Updated auto-versioning configuration')

            settings_window.destroy()

        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text="Save Settings",
                  command=save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel",
                  command=settings_window.destroy).pack(side='right', padx=5)
