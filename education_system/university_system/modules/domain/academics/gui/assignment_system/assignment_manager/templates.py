"""Assignment draft and template save/load operations"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class TemplatesMixin:
    """Assignment template and draft operations"""

    def save_assignment_draft(self):
        """Save current assignment as draft"""
        try:
            # Validate basic fields
            if not self.title_var.get().strip():
                messagebox.showerror("Error", "Please enter a title before saving draft")
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create assignment_drafts table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                draft_name TEXT NOT NULL,
                draft_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Collect form data
            draft_data = {
                'module': self.module_var.get(),
                'title': self.title_var.get(),
                'description': self.description_text.get(1.0, tk.END).strip(),
                'instructions': self.instructions_text.get(1.0, tk.END).strip(),
                'due_date': self.due_date_var.get(),
                'due_time': self.due_time_var.get(),
                'max_marks': self.max_marks_var.get(),
                'file_types': self.file_types_var.get(),
                'max_size': self.max_size_var.get(),
                'assignment_type': self.assignment_type_var.get(),
                'group_min': self.group_min_var.get(),
                'group_max': self.group_max_var.get(),
                'allow_late': self.allow_late_var.get(),
                'late_penalty': self.late_penalty_var.get(),
                'auto_release': self.auto_release_var.get(),
                'peer_review': self.peer_review_var.get(),
            }

            # Add new fields if they exist
            if hasattr(self, 'assessment_type_var'):
                draft_data['assessment_type'] = self.assessment_type_var.get()
            if hasattr(self, 'grading_method_var'):
                draft_data['grading_method'] = self.grading_method_var.get()
            if hasattr(self, 'visibility_var'):
                draft_data['visibility'] = self.visibility_var.get()

            draft_name = f"Draft - {self.title_var.get()[:30]} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            cursor.execute('''
            INSERT INTO assignment_drafts (user_id, draft_name, draft_data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (self.auth.current_user['id'], draft_name, json.dumps(draft_data)))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Draft saved successfully as:\n{draft_name}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save draft: {e}")


    def load_assignment_template(self):
        """Load an assignment template or draft"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get templates and drafts
            cursor.execute('''
            SELECT id, draft_name, draft_data, created_at
            FROM assignment_drafts
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 20
            ''', (self.auth.current_user['id'],))

            templates = cursor.fetchall()
            conn.close()

            if not templates:
                messagebox.showinfo("No Templates", "No saved templates or drafts found")
                return

            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Load Template/Draft")
            dialog.geometry("600x400")
            dialog.transient(self.root)

            ttk.Label(dialog, text="Select a template or draft to load:",
                     font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

            # Templates listbox
            list_frame = ttk.Frame(dialog)
            list_frame.pack(fill='both', expand=True, padx=10, pady=5)

            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side='right', fill='y')

            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=15)
            listbox.pack(fill='both', expand=True)
            scrollbar.config(command=listbox.yview)

            template_map = {}
            for template in templates:
                tid, name, data, created = template
                listbox.insert(tk.END, name)
                template_map[name] = (tid, data)

            def load_selected():
                selection = listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a template")
                    return

                selected_name = listbox.get(selection[0])
                tid, data_json = template_map[selected_name]

                try:
                    data = json.loads(data_json)

                    # Load data into form
                    self.module_var.set(data.get('module', ''))
                    self.title_var.set(data.get('title', ''))
                    self.description_text.delete(1.0, tk.END)
                    self.description_text.insert(1.0, data.get('description', ''))
                    self.instructions_text.delete(1.0, tk.END)
                    self.instructions_text.insert(1.0, data.get('instructions', ''))
                    self.due_date_var.set(data.get('due_date', ''))
                    self.due_time_var.set(data.get('due_time', '23:59'))
                    self.max_marks_var.set(data.get('max_marks', '100'))
                    self.file_types_var.set(data.get('file_types', '.pdf,.docx,.txt'))
                    self.max_size_var.set(data.get('max_size', '10'))
                    self.assignment_type_var.set(data.get('assignment_type', 'individual'))
                    self.group_min_var.set(data.get('group_min', '2'))
                    self.group_max_var.set(data.get('group_max', '4'))
                    self.allow_late_var.set(data.get('allow_late', True))
                    self.late_penalty_var.set(data.get('late_penalty', '0'))
                    self.auto_release_var.set(data.get('auto_release', False))
                    self.peer_review_var.set(data.get('peer_review', False))

                    # Load new fields if they exist
                    if hasattr(self, 'assessment_type_var'):
                        self.assessment_type_var.set(data.get('assessment_type', 'essay'))
                    if hasattr(self, 'grading_method_var'):
                        self.grading_method_var.set(data.get('grading_method', 'points'))
                    if hasattr(self, 'visibility_var'):
                        self.visibility_var.set(data.get('visibility', 'draft'))

                    dialog.destroy()
                    messagebox.showinfo("Success", "Template loaded successfully")

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load template: {e}")

            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Load", command=load_selected).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {e}")


    def save_assignment_template(self):
        """Save current form as a reusable template"""
        try:
            if not self.title_var.get().strip():
                messagebox.showerror("Error", "Please enter a title before saving template")
                return

            # Ask for template name
            template_name = tk.simpledialog.askstring("Template Name",
                                                      "Enter a name for this template:",
                                                      initialfile=f"Template - {self.title_var.get()[:30]}")
            if not template_name:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                draft_name TEXT NOT NULL,
                draft_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            draft_data = {
                'module': self.module_var.get(),
                'title': self.title_var.get(),
                'description': self.description_text.get(1.0, tk.END).strip(),
                'instructions': self.instructions_text.get(1.0, tk.END).strip(),
                'max_marks': self.max_marks_var.get(),
                'file_types': self.file_types_var.get(),
                'max_size': self.max_size_var.get(),
                'assignment_type': self.assignment_type_var.get(),
                'group_min': self.group_min_var.get(),
                'group_max': self.group_max_var.get(),
                'allow_late': self.allow_late_var.get(),
                'late_penalty': self.late_penalty_var.get(),
                'auto_release': self.auto_release_var.get(),
                'peer_review': self.peer_review_var.get(),
            }

            if hasattr(self, 'assessment_type_var'):
                draft_data['assessment_type'] = self.assessment_type_var.get()
            if hasattr(self, 'grading_method_var'):
                draft_data['grading_method'] = self.grading_method_var.get()

            cursor.execute('''
            INSERT INTO assignment_drafts (user_id, draft_name, draft_data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (self.auth.current_user['id'], template_name, json.dumps(draft_data)))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Template '{template_name}' saved successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {e}")
