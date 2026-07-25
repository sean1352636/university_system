"""Annotation manager for inline commenting on student submissions"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


ANNOTATION_CATEGORIES = ['praise', 'suggestion', 'correction', 'question']

CATEGORY_COLORS = {
    'praise': '#d4edda',
    'suggestion': '#fff3cd',
    'correction': '#f8d7da',
    'question': '#cce5ff',
}

CATEGORY_TAG_COLORS = {
    'praise': {'bg': '#d4edda', 'fg': '#155724'},
    'suggestion': {'bg': '#fff3cd', 'fg': '#856404'},
    'correction': {'bg': '#f8d7da', 'fg': '#721c24'},
    'question': {'bg': '#cce5ff', 'fg': '#004085'},
}


class AnnotationManager:
    """Manager for inline annotations and comments on student submissions"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def _ensure_tables(self):
        """Ensure annotation tables exist in the database"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        # Must match the canonical definition in
        # modules/domain/academics/gui/assignment_system/db_manager.py
        # (reviewer_id is FK to users.id which is INTEGER; TEXT
        # timestamps to match the rest of the codebase; CHECK
        # constraint on category to match canonical schema).
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS submission_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                reviewer_id INTEGER NOT NULL,
                line_number INTEGER,
                position_start INTEGER,
                position_end INTEGER,
                comment TEXT NOT NULL,
                category TEXT DEFAULT 'suggestion' CHECK (category IN ('praise', 'suggestion', 'correction', 'question')),
                student_response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS annotation_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                text TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'suggestion',
                created_by TEXT NOT NULL,
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def _get_submission_text(self, submission_id):
        """Retrieve the submission content text for display"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT content, file_path FROM assignment_submissions
            WHERE id = ?
        ''', (submission_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        content, file_path = row
        if content:
            return content
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read()
            except (OSError, IOError):
                return None
        return None

    # ------------------------------------------------------------------
    # Main annotation interface
    # ------------------------------------------------------------------

    def show_annotation_interface(self, submission_id):
        """Main annotation view with submission text and inline comments"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to annotate submissions.")
            return

        self._ensure_tables()
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Annotation Interface", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        # Info bar
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(info_frame, text=f"Submission ID: {submission_id}").pack(side='left')

        # Main paned window: left = text, right = annotation panel
        paned = ttk.PanedWindow(parent, orient='horizontal')
        paned.pack(fill='both', expand=True, pady=(0, 10))

        # --- Left: submission text ---
        left_frame = ttk.LabelFrame(paned, text="Submission Content", padding=5)
        paned.add(left_frame, weight=3)

        text_widget = tk.Text(left_frame, wrap='word', font=('Consolas', 10), state='normal')
        text_scroll = ttk.Scrollbar(left_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=text_scroll.set)
        text_scroll.pack(side='right', fill='y')
        text_widget.pack(fill='both', expand=True)

        # Configure highlight tags for each category
        for cat, colors in CATEGORY_TAG_COLORS.items():
            text_widget.tag_configure(f'annot_{cat}', background=colors['bg'], foreground=colors['fg'])
        text_widget.tag_configure('line_highlight', background='#e8e8e8')

        # Load submission text
        content = self._get_submission_text(submission_id)
        if content:
            text_widget.insert('1.0', content)
        else:
            text_widget.insert('1.0', "(No submission content available)")
        text_widget.config(state='disabled')

        # --- Right: annotation panel ---
        right_frame = ttk.LabelFrame(paned, text="Annotations", padding=5)
        paned.add(right_frame, weight=2)

        # Add annotation controls
        controls_frame = ttk.Frame(right_frame)
        controls_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(controls_frame, text="Line #:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        line_var = tk.StringVar(value="1")
        line_entry = ttk.Spinbox(controls_frame, from_=1, to=99999, textvariable=line_var, width=6)
        line_entry.grid(row=0, column=1, sticky='w', padx=(0, 10))

        ttk.Label(controls_frame, text="Category:").grid(row=0, column=2, sticky='w', padx=(0, 5))
        category_var = tk.StringVar(value='suggestion')
        category_combo = ttk.Combobox(controls_frame, textvariable=category_var,
                                      values=ANNOTATION_CATEGORIES, state='readonly', width=12)
        category_combo.grid(row=0, column=3, sticky='w', padx=(0, 10))

        ttk.Label(controls_frame, text="Comment:").grid(row=1, column=0, sticky='nw', pady=(5, 0))
        comment_text = scrolledtext.ScrolledText(controls_frame, height=4, width=40, wrap='word')
        comment_text.grid(row=1, column=1, columnspan=3, sticky='ew', pady=(5, 0))

        controls_frame.columnconfigure(3, weight=1)

        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill='x', pady=(5, 5))

        ttk.Button(
            btn_frame, text="Add Annotation",
            command=lambda: self._do_add_annotation(
                submission_id, line_var, comment_text, category_var, text_widget, annot_tree
            )
        ).pack(side='left', padx=(0, 5))

        ttk.Button(
            btn_frame, text="Insert Template",
            command=lambda: self._insert_template(comment_text)
        ).pack(side='left', padx=(0, 5))

        ttk.Button(
            btn_frame, text="Delete Selected",
            command=lambda: self._delete_annotation(submission_id, annot_tree, text_widget)
        ).pack(side='left')

        # Annotations treeview
        columns = ('ID', 'Line', 'Category', 'Comment', 'Date')
        annot_tree = ttk.Treeview(right_frame, columns=columns, show='headings', height=10)
        for col in columns:
            annot_tree.heading(col, text=col)
        annot_tree.column('ID', width=40)
        annot_tree.column('Line', width=40)
        annot_tree.column('Category', width=80)
        annot_tree.column('Comment', width=200)
        annot_tree.column('Date', width=100)

        tree_scroll = ttk.Scrollbar(right_frame, orient='vertical', command=annot_tree.yview)
        annot_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side='right', fill='y')
        annot_tree.pack(fill='both', expand=True)

        # Double-click to highlight line in text
        annot_tree.bind('<Double-1>', lambda e: self._highlight_annotation_line(annot_tree, text_widget))

        # Load existing annotations
        self._load_annotations(submission_id, annot_tree, text_widget)

        # Bottom buttons
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill='x')

        ttk.Button(bottom_frame, text="Export Annotations",
                   command=lambda: self.export_annotations(submission_id)).pack(side='left', padx=(0, 10))
        ttk.Button(bottom_frame, text="Annotation Summary",
                   command=self.show_annotation_summary).pack(side='left', padx=(0, 10))
        ttk.Button(bottom_frame, text="Manage Templates",
                   command=self.show_annotation_templates).pack(side='left')

    def _do_add_annotation(self, submission_id, line_var, comment_text, category_var, text_widget, annot_tree):
        """Handle the Add Annotation button click"""
        try:
            line_number = int(line_var.get())
        except (ValueError, TypeError):
            messagebox.showwarning("Invalid Input", "Line number must be an integer.")
            return

        comment = comment_text.get('1.0', 'end').strip()
        if not comment:
            messagebox.showwarning("Missing Comment", "Please enter a comment.")
            return

        category = category_var.get()
        self.add_annotation(submission_id, line_number, comment, category)
        comment_text.delete('1.0', 'end')

        # Refresh the annotation list and highlights
        self._load_annotations(submission_id, annot_tree, text_widget)

    def _load_annotations(self, submission_id, annot_tree, text_widget):
        """Load annotations from DB into treeview and apply text highlights"""
        # Clear treeview
        for item in annot_tree.get_children():
            annot_tree.delete(item)

        # Clear text highlights
        text_widget.config(state='normal')
        for cat in ANNOTATION_CATEGORIES:
            text_widget.tag_remove(f'annot_{cat}', '1.0', 'end')
        text_widget.tag_remove('line_highlight', '1.0', 'end')

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, line_number, category, comment, created_at
            FROM submission_annotations
            WHERE submission_id = ?
            ORDER BY line_number, created_at
        ''', (submission_id,))
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            annot_id, line_num, category, comment, created_at = row
            display_comment = comment[:80] + '...' if len(comment) > 80 else comment
            date_str = created_at[:10] if created_at else ''
            annot_tree.insert('', 'end', values=(annot_id, line_num, category, display_comment, date_str))

            # Highlight the line in the text widget
            tag = f'annot_{category}' if category in ANNOTATION_CATEGORIES else 'line_highlight'
            try:
                text_widget.tag_add(tag, f'{line_num}.0', f'{line_num}.end')
            except tk.TclError:
                pass

        text_widget.config(state='disabled')

    def _highlight_annotation_line(self, annot_tree, text_widget):
        """Highlight and scroll to the annotated line on double-click"""
        selection = annot_tree.selection()
        if not selection:
            return
        values = annot_tree.item(selection[0], 'values')
        if not values:
            return
        line_num = values[1]
        try:
            text_widget.see(f'{line_num}.0')
            text_widget.config(state='normal')
            text_widget.tag_remove('line_highlight', '1.0', 'end')
            text_widget.tag_add('line_highlight', f'{line_num}.0', f'{line_num}.end')
            text_widget.config(state='disabled')
        except tk.TclError:
            pass

    def _delete_annotation(self, submission_id, annot_tree, text_widget):
        """Delete the selected annotation"""
        selection = annot_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select an annotation to delete.")
            return

        values = annot_tree.item(selection[0], 'values')
        annot_id = values[0]

        if not messagebox.askyesno("Confirm Delete", "Delete this annotation?"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM submission_annotations WHERE id = ?', (annot_id,))
            conn.commit()
            conn.close()
            self._load_annotations(submission_id, annot_tree, text_widget)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete annotation: {e}")

    def _insert_template(self, comment_text):
        """Show template picker and insert selected template text into comment field"""
        self._ensure_tables()
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, text, category FROM annotation_templates ORDER BY usage_count DESC')
        templates = cursor.fetchall()
        conn.close()

        if not templates:
            messagebox.showinfo("No Templates", "No annotation templates found. Create one first.")
            return

        picker = tk.Toplevel(self.root)
        picker.title("Select Annotation Template")
        picker.geometry("500x400")
        picker.transient(self.root)
        picker.grab_set()

        ttk.Label(picker, text="Select a template to insert:", font=('Segoe UI', 11, 'bold')).pack(
            anchor='w', padx=10, pady=(10, 5))

        columns = ('Name', 'Category', 'Text')
        tree = ttk.Treeview(picker, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
        tree.column('Name', width=120)
        tree.column('Category', width=80)
        tree.column('Text', width=260)
        tree.pack(fill='both', expand=True, padx=10, pady=5)

        template_map = {}
        for tid, name, text, category in templates:
            display_text = text[:60] + '...' if len(text) > 60 else text
            iid = tree.insert('', 'end', values=(name, category, display_text))
            template_map[iid] = (tid, text)

        def insert_selected():
            sel = tree.selection()
            if not sel:
                return
            tid, text = template_map[sel[0]]
            comment_text.insert('end', text)
            # Increment usage count
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('UPDATE annotation_templates SET usage_count = usage_count + 1 WHERE id = ?', (tid,))
                conn.commit()
                conn.close()
            except Exception:
                pass
            picker.destroy()

        ttk.Button(picker, text="Insert", command=insert_selected).pack(pady=10)

    # ------------------------------------------------------------------
    # Core add annotation
    # ------------------------------------------------------------------

    def add_annotation(self, submission_id, line_number, comment, category='suggestion'):
        """Add an annotation at a specific line/position in a submission"""
        if category not in ANNOTATION_CATEGORIES:
            category = 'suggestion'

        self._ensure_tables()
        reviewer_id = getattr(self.auth, 'username', 'unknown')

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO submission_annotations
                    (submission_id, reviewer_id, line_number, position_start, position_end,
                     comment, category, created_at, updated_at)
                VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?)
            ''', (submission_id, reviewer_id, line_number, comment, category,
                  datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add annotation: {e}")

    # ------------------------------------------------------------------
    # Annotation templates management
    # ------------------------------------------------------------------

    def show_annotation_templates(self):
        """Manage reusable annotation comment templates"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to manage templates.")
            return

        self._ensure_tables()
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Annotation Templates", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        # Templates treeview
        tree_frame = ttk.LabelFrame(parent, text="Saved Templates", padding=10)
        tree_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Name', 'Category', 'Text', 'Uses', 'Created')
        template_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        for col in columns:
            template_tree.heading(col, text=col)
        template_tree.column('ID', width=40)
        template_tree.column('Name', width=120)
        template_tree.column('Category', width=80)
        template_tree.column('Text', width=300)
        template_tree.column('Uses', width=50)
        template_tree.column('Created', width=100)

        tree_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=template_tree.yview)
        template_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side='right', fill='y')
        template_tree.pack(fill='both', expand=True)

        self._load_templates(template_tree)

        # Buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Create New Template",
                   command=lambda: self.create_template(template_tree)).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Edit Template",
                   command=lambda: self._edit_template(template_tree)).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Delete Template",
                   command=lambda: self._delete_template(template_tree)).pack(side='left')

    def _load_templates(self, template_tree):
        """Load templates into the treeview"""
        for item in template_tree.get_children():
            template_tree.delete(item)

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, category, text, usage_count, created_at
            FROM annotation_templates ORDER BY usage_count DESC, name
        ''')
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            tid, name, category, text, usage_count, created_at = row
            display_text = text[:80] + '...' if len(text) > 80 else text
            date_str = created_at[:10] if created_at else ''
            template_tree.insert('', 'end', values=(tid, name, category, display_text, usage_count, date_str))

    def create_template(self, template_tree=None):
        """Create a new annotation template via dialog"""
        self._ensure_tables()

        dialog = tk.Toplevel(self.root)
        dialog.title("Create Annotation Template")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form = ttk.Frame(dialog, padding=15)
        form.pack(fill='both', expand=True)

        ttk.Label(form, text="Template Name:").grid(row=0, column=0, sticky='w', pady=(0, 5))
        name_var = tk.StringVar()
        ttk.Entry(form, textvariable=name_var, width=40).grid(row=0, column=1, sticky='ew', pady=(0, 5))

        ttk.Label(form, text="Category:").grid(row=1, column=0, sticky='w', pady=(0, 5))
        cat_var = tk.StringVar(value='suggestion')
        ttk.Combobox(form, textvariable=cat_var, values=ANNOTATION_CATEGORIES,
                     state='readonly', width=37).grid(row=1, column=1, sticky='ew', pady=(0, 5))

        ttk.Label(form, text="Template Text:").grid(row=2, column=0, sticky='nw', pady=(0, 5))
        text_field = scrolledtext.ScrolledText(form, height=8, width=40, wrap='word')
        text_field.grid(row=2, column=1, sticky='ew', pady=(0, 5))

        form.columnconfigure(1, weight=1)

        def save():
            name = name_var.get().strip()
            text = text_field.get('1.0', 'end').strip()
            category = cat_var.get()
            if not name or not text:
                messagebox.showwarning("Missing Fields", "Please fill in both name and text.", parent=dialog)
                return
            try:
                created_by = getattr(self.auth, 'username', 'unknown')
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO annotation_templates (name, text, category, created_by, usage_count, created_at)
                    VALUES (?, ?, ?, ?, 0, ?)
                ''', (name, text, category, created_by, datetime.now().isoformat()))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", f"Template '{name}' created.", parent=dialog)
                dialog.destroy()
                if template_tree is not None:
                    self._load_templates(template_tree)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {e}", parent=dialog)

        ttk.Button(form, text="Save Template", command=save).grid(row=3, column=1, sticky='e', pady=(10, 0))

    def _edit_template(self, template_tree):
        """Edit a selected template"""
        selection = template_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a template to edit.")
            return

        values = template_tree.item(selection[0], 'values')
        tid = values[0]

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, text, category FROM annotation_templates WHERE id = ?', (tid,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            messagebox.showerror("Error", "Template not found.")
            return

        _, name, text, category = row

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Annotation Template")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form = ttk.Frame(dialog, padding=15)
        form.pack(fill='both', expand=True)

        ttk.Label(form, text="Template Name:").grid(row=0, column=0, sticky='w', pady=(0, 5))
        name_var = tk.StringVar(value=name)
        ttk.Entry(form, textvariable=name_var, width=40).grid(row=0, column=1, sticky='ew', pady=(0, 5))

        ttk.Label(form, text="Category:").grid(row=1, column=0, sticky='w', pady=(0, 5))
        cat_var = tk.StringVar(value=category)
        ttk.Combobox(form, textvariable=cat_var, values=ANNOTATION_CATEGORIES,
                     state='readonly', width=37).grid(row=1, column=1, sticky='ew', pady=(0, 5))

        ttk.Label(form, text="Template Text:").grid(row=2, column=0, sticky='nw', pady=(0, 5))
        text_field = scrolledtext.ScrolledText(form, height=8, width=40, wrap='word')
        text_field.grid(row=2, column=1, sticky='ew', pady=(0, 5))
        text_field.insert('1.0', text)

        form.columnconfigure(1, weight=1)

        def save():
            new_name = name_var.get().strip()
            new_text = text_field.get('1.0', 'end').strip()
            new_cat = cat_var.get()
            if not new_name or not new_text:
                messagebox.showwarning("Missing Fields", "Please fill in both name and text.", parent=dialog)
                return
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE annotation_templates SET name = ?, text = ?, category = ? WHERE id = ?
                ''', (new_name, new_text, new_cat, tid))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Template updated.", parent=dialog)
                dialog.destroy()
                self._load_templates(template_tree)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update template: {e}", parent=dialog)

        ttk.Button(form, text="Save Changes", command=save).grid(row=3, column=1, sticky='e', pady=(10, 0))

    def _delete_template(self, template_tree):
        """Delete the selected template"""
        selection = template_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a template to delete.")
            return

        values = template_tree.item(selection[0], 'values')
        tid = values[0]

        if not messagebox.askyesno("Confirm Delete", "Delete this template?"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM annotation_templates WHERE id = ?', (tid,))
            conn.commit()
            conn.close()
            self._load_templates(template_tree)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete template: {e}")

    # ------------------------------------------------------------------
    # Student view of annotations
    # ------------------------------------------------------------------

    def show_student_annotations(self, submission_id):
        """Student view of annotations on their submission with ability to respond"""
        self._ensure_tables()
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Submission Feedback", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        # Main paned layout
        paned = ttk.PanedWindow(parent, orient='horizontal')
        paned.pack(fill='both', expand=True, pady=(0, 10))

        # Left: submission text with highlights
        left_frame = ttk.LabelFrame(paned, text="Your Submission", padding=5)
        paned.add(left_frame, weight=3)

        text_widget = tk.Text(left_frame, wrap='word', font=('Consolas', 10), state='normal')
        text_scroll = ttk.Scrollbar(left_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=text_scroll.set)
        text_scroll.pack(side='right', fill='y')
        text_widget.pack(fill='both', expand=True)

        for cat, colors in CATEGORY_TAG_COLORS.items():
            text_widget.tag_configure(f'annot_{cat}', background=colors['bg'], foreground=colors['fg'])

        content = self._get_submission_text(submission_id)
        if content:
            text_widget.insert('1.0', content)
        else:
            text_widget.insert('1.0', "(No submission content available)")
        text_widget.config(state='disabled')

        # Right: annotations list with response capability
        right_frame = ttk.LabelFrame(paned, text="Instructor Feedback", padding=5)
        paned.add(right_frame, weight=2)

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, line_number, category, comment, student_response, reviewer_id, created_at
            FROM submission_annotations
            WHERE submission_id = ?
            ORDER BY line_number, created_at
        ''', (submission_id,))
        annotations = cursor.fetchall()
        conn.close()

        if not annotations:
            ttk.Label(right_frame, text="No annotations yet.").pack(pady=20)
            return

        # Scrollable frame for annotations
        canvas = tk.Canvas(right_frame)
        scroll = ttk.Scrollbar(right_frame, orient='vertical', command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scroll.set)

        scroll.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)

        # Apply highlights and build annotation cards
        text_widget.config(state='normal')
        for annot in annotations:
            annot_id, line_num, category, comment, student_response, reviewer_id, created_at = annot

            # Highlight in text
            tag = f'annot_{category}' if category in ANNOTATION_CATEGORIES else 'annot_suggestion'
            try:
                text_widget.tag_add(tag, f'{line_num}.0', f'{line_num}.end')
            except tk.TclError:
                pass

            # Annotation card
            bg_color = CATEGORY_COLORS.get(category, '#f0f0f0')
            card = ttk.LabelFrame(scroll_frame, text=f"Line {line_num} - {category.capitalize()}", padding=8)
            card.pack(fill='x', padx=5, pady=5)

            ttk.Label(card, text=f"By: {reviewer_id}  |  {created_at[:10] if created_at else ''}",
                      font=('Segoe UI', 8)).pack(anchor='w')
            ttk.Label(card, text=comment, wraplength=300, justify='left').pack(anchor='w', pady=(5, 5))

            if student_response:
                resp_frame = ttk.LabelFrame(card, text="Your Response", padding=5)
                resp_frame.pack(fill='x', pady=(2, 0))
                ttk.Label(resp_frame, text=student_response, wraplength=280, justify='left').pack(anchor='w')
            else:
                # Allow student to respond
                resp_entry = scrolledtext.ScrolledText(card, height=2, width=35, wrap='word')
                resp_entry.pack(fill='x', pady=(2, 2))
                ttk.Button(
                    card, text="Reply",
                    command=lambda aid=annot_id, entry=resp_entry: self._submit_student_response(
                        aid, entry, submission_id
                    )
                ).pack(anchor='e')

        text_widget.config(state='disabled')

        # Summary counts at bottom
        summary_frame = ttk.Frame(parent)
        summary_frame.pack(fill='x')
        counts = {}
        for annot in annotations:
            cat = annot[2]
            counts[cat] = counts.get(cat, 0) + 1
        summary_parts = [f"{cat.capitalize()}: {cnt}" for cat, cnt in sorted(counts.items())]
        ttk.Label(summary_frame, text=f"Total annotations: {len(annotations)}  |  " + "  |  ".join(summary_parts),
                  font=('Segoe UI', 9)).pack(anchor='w')

    def _submit_student_response(self, annotation_id, entry_widget, submission_id):
        """Save a student response to an annotation"""
        response = entry_widget.get('1.0', 'end').strip()
        if not response:
            messagebox.showwarning("Empty Response", "Please type a response.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE submission_annotations
                SET student_response = ?, updated_at = ?
                WHERE id = ?
            ''', (response, datetime.now().isoformat(), annotation_id))
            conn.commit()
            conn.close()
            messagebox.showinfo("Response Saved", "Your response has been saved.")
            # Refresh the view
            self.show_student_annotations(submission_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save response: {e}")

    # ------------------------------------------------------------------
    # Annotation summary
    # ------------------------------------------------------------------

    def show_annotation_summary(self):
        """Summary of all annotations across submissions for an assignment"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to view annotation summaries.")
            return

        self._ensure_tables()
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Annotation Summary", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        # Stats frame
        stats_frame = ttk.LabelFrame(parent, text="Overview Statistics", padding=10)
        stats_frame.pack(fill='x', pady=(0, 10))

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Total annotations
        cursor.execute('SELECT COUNT(*) FROM submission_annotations')
        total = cursor.fetchone()[0]

        # By category
        cursor.execute('''
            SELECT category, COUNT(*) FROM submission_annotations GROUP BY category ORDER BY COUNT(*) DESC
        ''')
        by_category = cursor.fetchall()

        # By reviewer
        cursor.execute('''
            SELECT reviewer_id, COUNT(*) FROM submission_annotations GROUP BY reviewer_id ORDER BY COUNT(*) DESC
        ''')
        by_reviewer = cursor.fetchall()

        # With student responses
        cursor.execute('SELECT COUNT(*) FROM submission_annotations WHERE student_response IS NOT NULL')
        with_responses = cursor.fetchone()[0]

        # Submissions with annotations
        cursor.execute('SELECT COUNT(DISTINCT submission_id) FROM submission_annotations')
        annotated_submissions = cursor.fetchone()[0]

        conn.close()

        row = 0
        ttk.Label(stats_frame, text=f"Total Annotations: {total}",
                  font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, sticky='w', padx=(0, 30))
        ttk.Label(stats_frame, text=f"Annotated Submissions: {annotated_submissions}",
                  font=('Segoe UI', 10, 'bold')).grid(row=row, column=1, sticky='w', padx=(0, 30))
        ttk.Label(stats_frame, text=f"Student Responses: {with_responses}",
                  font=('Segoe UI', 10, 'bold')).grid(row=row, column=2, sticky='w')

        # Category breakdown
        cat_frame = ttk.LabelFrame(parent, text="By Category", padding=10)
        cat_frame.pack(fill='x', pady=(0, 10))

        for i, (cat, cnt) in enumerate(by_category):
            color = CATEGORY_COLORS.get(cat, '#f0f0f0')
            lbl = tk.Label(cat_frame, text=f"  {cat.capitalize()}: {cnt}  ", bg=color,
                           font=('Segoe UI', 10), padx=10, pady=4)
            lbl.grid(row=0, column=i, padx=(0, 10), pady=5)

        # Reviewer breakdown
        reviewer_frame = ttk.LabelFrame(parent, text="By Reviewer", padding=10)
        reviewer_frame.pack(fill='x', pady=(0, 10))

        columns = ('Reviewer', 'Annotation Count')
        reviewer_tree = ttk.Treeview(reviewer_frame, columns=columns, show='headings', height=6)
        for col in columns:
            reviewer_tree.heading(col, text=col)
            reviewer_tree.column(col, width=200)
        reviewer_tree.pack(fill='x')

        for reviewer_id, cnt in by_reviewer:
            reviewer_tree.insert('', 'end', values=(reviewer_id, cnt))

        # Recent annotations list
        recent_frame = ttk.LabelFrame(parent, text="Recent Annotations", padding=10)
        recent_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Submission', 'Line', 'Category', 'Comment', 'Reviewer', 'Date')
        recent_tree = ttk.Treeview(recent_frame, columns=columns, show='headings', height=10)
        for col in columns:
            recent_tree.heading(col, text=col)
        recent_tree.column('ID', width=40)
        recent_tree.column('Submission', width=80)
        recent_tree.column('Line', width=40)
        recent_tree.column('Category', width=80)
        recent_tree.column('Comment', width=250)
        recent_tree.column('Reviewer', width=100)
        recent_tree.column('Date', width=100)

        r_scroll = ttk.Scrollbar(recent_frame, orient='vertical', command=recent_tree.yview)
        recent_tree.configure(yscrollcommand=r_scroll.set)
        r_scroll.pack(side='right', fill='y')
        recent_tree.pack(fill='both', expand=True)

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, submission_id, line_number, category, comment, reviewer_id, created_at
            FROM submission_annotations
            ORDER BY created_at DESC LIMIT 50
        ''')
        recent = cursor.fetchall()
        conn.close()

        for row in recent:
            annot_id, sub_id, line_num, category, comment, reviewer_id, created_at = row
            display_comment = comment[:60] + '...' if len(comment) > 60 else comment
            date_str = created_at[:10] if created_at else ''
            recent_tree.insert('', 'end', values=(
                annot_id, sub_id, line_num, category, display_comment, reviewer_id, date_str
            ))

    # ------------------------------------------------------------------
    # Export annotations
    # ------------------------------------------------------------------

    def export_annotations(self, submission_id):
        """Export annotations for a submission as PDF or text file"""
        self._ensure_tables()

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, line_number, category, comment, student_response, reviewer_id, created_at
            FROM submission_annotations
            WHERE submission_id = ?
            ORDER BY line_number, created_at
        ''', (submission_id,))
        annotations = cursor.fetchall()
        conn.close()

        if not annotations:
            messagebox.showinfo("No Annotations", "No annotations found for this submission.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Export Annotations",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )

        if not save_path:
            return

        try:
            if save_path.endswith('.json'):
                export_data = {
                    'submission_id': submission_id,
                    'exported_at': datetime.now().isoformat(),
                    'annotations': []
                }
                for annot in annotations:
                    annot_id, line_num, category, comment, student_response, reviewer_id, created_at = annot
                    export_data['annotations'].append({
                        'id': annot_id,
                        'line_number': line_num,
                        'category': category,
                        'comment': comment,
                        'student_response': student_response,
                        'reviewer': reviewer_id,
                        'created_at': created_at,
                    })
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                lines = []
                lines.append(f"Annotation Export - Submission {submission_id}")
                lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("=" * 60)
                lines.append("")

                for annot in annotations:
                    annot_id, line_num, category, comment, student_response, reviewer_id, created_at = annot
                    lines.append(f"Line {line_num} [{category.upper()}] (by {reviewer_id}, {created_at[:10] if created_at else 'N/A'})")
                    lines.append(f"  {comment}")
                    if student_response:
                        lines.append(f"  Student reply: {student_response}")
                    lines.append("")

                lines.append("=" * 60)
                lines.append(f"Total annotations: {len(annotations)}")

                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))

            messagebox.showinfo("Export Complete", f"Annotations exported to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export annotations: {e}")
