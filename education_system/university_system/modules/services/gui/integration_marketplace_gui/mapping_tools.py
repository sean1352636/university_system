"""Data mapping tool methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.i18n import get_text as _t

logger = logging.getLogger(__name__)


class MappingToolsMixin:
    """Mixin providing data mapping tool methods."""

    def auto_detect_mappings(self):
        """Automatically suggest field mappings based on names"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Auto-Detect Field Mappings")
            dialog.geometry("700x600")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Auto-Detect Field Mappings",
                     style='Title.TLabel').pack(pady=10)

            # Input frame
            input_frame = ttk.LabelFrame(dialog, text="Input Fields", padding=10)
            input_frame.pack(fill='x', padx=10, pady=5)

            ttk.Label(input_frame, text="Source Fields (comma-separated):").pack(anchor='w')
            source_var = tk.StringVar(value="student_id, first_name, last_name, email, phone")
            ttk.Entry(input_frame, textvariable=source_var, width=70).pack(fill='x', pady=5)

            ttk.Label(input_frame, text="Target Fields (comma-separated):").pack(anchor='w')
            target_var = tk.StringVar(value="id, firstName, lastName, emailAddress, phoneNumber")
            ttk.Entry(input_frame, textvariable=target_var, width=70).pack(fill='x', pady=5)

            # Results frame
            results_frame = ttk.LabelFrame(dialog, text="Suggested Mappings", padding=10)
            results_frame.pack(fill='both', expand=True, padx=10, pady=5)

            columns = ('source', 'target', 'confidence', 'match_type')
            tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)

            for col in columns:
                tree.heading(col, text=col.replace('_', ' ').title())
                tree.column(col, width=150)

            tree.pack(fill='both', expand=True)

            def detect_mappings():
                for item in tree.get_children():
                    tree.delete(item)

                source_fields = [f.strip() for f in source_var.get().split(',')]
                target_fields = [f.strip() for f in target_var.get().split(',')]

                # Normalize for comparison
                def normalize(name):
                    return re.sub(r'[^a-z0-9]', '', name.lower())

                source_normalized = {normalize(f): f for f in source_fields}
                target_normalized = {normalize(f): f for f in target_fields}

                suggestions = []

                # Exact matches
                for src_norm, src_orig in source_normalized.items():
                    if src_norm in target_normalized:
                        suggestions.append({
                            'source': src_orig,
                            'target': target_normalized[src_norm],
                            'confidence': 1.0,
                            'match_type': 'exact'
                        })

                # Common mappings
                common_mappings = {
                    'firstname': ['first_name', 'fname', 'givenname'],
                    'lastname': ['last_name', 'lname', 'surname', 'familyname'],
                    'email': ['emailaddress', 'mail', 'e_mail'],
                    'phone': ['phonenumber', 'tel', 'telephone', 'mobile'],
                    'id': ['identifier', 'uuid', 'key', 'studentid'],
                }

                for src_norm, src_orig in source_normalized.items():
                    for base, alternatives in common_mappings.items():
                        all_names = [base] + alternatives
                        if src_norm in all_names:
                            for tgt_norm, tgt_orig in target_normalized.items():
                                if tgt_norm in all_names:
                                    if not any(s['source'] == src_orig and s['target'] == tgt_orig for s in suggestions):
                                        suggestions.append({
                                            'source': src_orig,
                                            'target': tgt_orig,
                                            'confidence': 0.8,
                                            'match_type': 'semantic'
                                        })

                for suggestion in sorted(suggestions, key=lambda x: -x['confidence']):
                    tree.insert('', 'end', values=(
                        suggestion['source'],
                        suggestion['target'],
                        f"{suggestion['confidence'] * 100:.0f}%",
                        suggestion['match_type']
                    ))

                if not suggestions:
                    messagebox.showinfo("Auto-Detect", "No matching field mappings detected")

            ttk.Button(dialog, text="Detect Mappings", command=detect_mappings).pack(pady=10)
            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=5)

        except Exception as e:
            logger.error(f"Error in auto-detect mappings: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to auto-detect mappings: {e}")

    def preview_transformation(self):
        """Preview transformation rule output on sample data"""
        try:
            selected = self.mappings_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select a mapping to preview transformation")
                return

            mapping_id = self.mappings_tree.item(selected[0])['values'][0]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT transformation_rule, source_field, target_field
                    FROM integration_data_mappings
                    WHERE mapping_id = ?
                ''', (mapping_id,))
                mapping = cursor.fetchone()

            if not mapping:
                messagebox.showerror(_t("common.error"), "Mapping not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.preview_transformation"))
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Preview Transformation",
                     style='Title.TLabel').pack(pady=10)

            ttk.Label(dialog, text=f"Source Field: {mapping[1]}").pack(anchor='w', padx=10)
            ttk.Label(dialog, text=f"Target Field: {mapping[2]}").pack(anchor='w', padx=10)
            ttk.Label(dialog, text=f"Rule: {mapping[0] or 'Direct copy'}").pack(anchor='w', padx=10, pady=5)

            ttk.Label(dialog, text="Sample Input Value:").pack(anchor='w', padx=10, pady=5)
            input_var = tk.StringVar(value="  John Doe  ")
            ttk.Entry(dialog, textvariable=input_var, width=40).pack(padx=10)

            result_frame = ttk.LabelFrame(dialog, text="Transformation Result", padding=10)
            result_frame.pack(fill='both', expand=True, padx=10, pady=10)

            result_label = ttk.Label(result_frame, text="", font=('Arial', 12))
            result_label.pack(pady=20)

            def apply_transformation():
                sample_input = input_var.get()
                rule = mapping[0]

                if not rule:
                    output = sample_input
                    method = "Direct copy (no transformation)"
                elif rule.upper().startswith('UPPER'):
                    output = sample_input.upper()
                    method = "UPPER function"
                elif rule.upper().startswith('LOWER'):
                    output = sample_input.lower()
                    method = "LOWER function"
                elif rule.upper().startswith('TRIM'):
                    output = sample_input.strip()
                    method = "TRIM function"
                else:
                    output = sample_input
                    method = "Unknown rule - used direct copy"

                result_label.config(text=f"Input: '{sample_input}'\n\nOutput: '{output}'\n\nMethod: {method}")

            ttk.Button(dialog, text=_t("integration_marketplace.mappings.preview"), command=apply_transformation).pack(pady=10)
            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=5)

        except Exception as e:
            logger.error(f"Error previewing transformation: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to preview transformation: {e}")

    def duplicate_mapping_set(self):
        """Clone an existing mapping configuration"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Duplicate Mapping Set")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Duplicate Mapping Set",
                     style='Title.TLabel').pack(pady=10)

            # Get installed integrations
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ii.install_id, ic.integration_name
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE ii.status = 'active'
                ''')
                integrations = cursor.fetchall()

            ttk.Label(dialog, text="Source Integration:").pack(anchor='w', padx=10, pady=5)
            source_var = tk.StringVar()
            source_combo = ttk.Combobox(dialog, textvariable=source_var,
                                       values=[f"{i[0]}: {i[1]}" for i in integrations],
                                       width=40, state='readonly')
            source_combo.pack(padx=10, pady=5)

            ttk.Label(dialog, text="Target Integration:").pack(anchor='w', padx=10, pady=5)
            target_var = tk.StringVar()
            target_combo = ttk.Combobox(dialog, textvariable=target_var,
                                       values=[f"{i[0]}: {i[1]}" for i in integrations],
                                       width=40, state='readonly')
            target_combo.pack(padx=10, pady=5)

            def duplicate():
                if not source_var.get() or not target_var.get():
                    messagebox.showwarning(_t("common.warning"), "Please select both source and target integrations")
                    return

                source_id = int(source_var.get().split(':')[0])
                target_id = int(target_var.get().split(':')[0])

                if source_id == target_id:
                    messagebox.showwarning(_t("common.warning"), "Source and target must be different")
                    return

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT source_field, target_field, transformation_rule, is_active
                        FROM integration_data_mappings
                        WHERE install_id = ?
                    ''', (source_id,))
                    mappings = cursor.fetchall()

                if not mappings:
                    messagebox.showinfo(_t("common.info"), "No mappings found in source integration")
                    return

                copied_count = 0
                with transaction() as conn:
                    cursor = conn.cursor()
                    for mapping in mappings:
                        cursor.execute('''
                            INSERT INTO integration_data_mappings
                            (install_id, source_field, target_field, transformation_rule, is_active)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (target_id, mapping[0], mapping[1], mapping[2], mapping[3]))
                        copied_count += 1

                log_activity('duplicate', 'mapping_set', target_id,
                            details={'source_id': source_id, 'mappings_copied': copied_count})

                messagebox.showinfo(_t("common.success"), f"Copied {copied_count} mapping(s) to target integration")
                dialog.destroy()
                self.load_mappings()

            ttk.Button(dialog, text="Duplicate Mappings", command=duplicate).pack(pady=20)

        except Exception as e:
            logger.error(f"Error duplicating mapping set: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to duplicate mappings: {e}")

    def import_mappings_from_template(self):
        """Import standard mapping templates"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to import mappings to")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.import_template"))
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Import Template to: {integration_name}",
                     style='Title.TLabel').pack(pady=10)

            templates = {
                'student_basic': [
                    ('student_id', 'id', None),
                    ('first_name', 'firstName', 'TRIM'),
                    ('last_name', 'lastName', 'TRIM'),
                    ('email', 'emailAddress', 'LOWER'),
                    ('enrollment_date', 'enrolledAt', None)
                ],
                'course_basic': [
                    ('course_id', 'id', None),
                    ('course_name', 'title', None),
                    ('course_code', 'code', 'UPPER'),
                    ('credits', 'creditHours', None)
                ],
                'grade_basic': [
                    ('grade_id', 'id', None),
                    ('student_id', 'studentId', None),
                    ('course_id', 'courseId', None),
                    ('grade', 'letterGrade', 'UPPER'),
                    ('points', 'gradePoints', None)
                ]
            }

            ttk.Label(dialog, text="Select Template:").pack(anchor='w', padx=10, pady=5)
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(dialog, textvariable=template_var,
                                         values=list(templates.keys()),
                                         width=30, state='readonly')
            template_combo.pack(padx=10, pady=5)

            # Preview frame
            preview_frame = ttk.LabelFrame(dialog, text="Template Preview", padding=10)
            preview_frame.pack(fill='both', expand=True, padx=10, pady=5)

            preview_text = scrolledtext.ScrolledText(preview_frame, height=10)
            preview_text.pack(fill='both', expand=True)

            def show_preview(event=None):
                template_name = template_var.get()
                if template_name in templates:
                    preview_text.delete('1.0', 'end')
                    preview_text.insert('end', f"Template: {template_name}\n\n")
                    preview_text.insert('end', f"{'Source':<20} {'Target':<20} {'Transform'}\n")
                    preview_text.insert('end', "-" * 50 + "\n")
                    for src, tgt, transform in templates[template_name]:
                        preview_text.insert('end', f"{src:<20} {tgt:<20} {transform or 'None'}\n")

            template_combo.bind('<<ComboboxSelected>>', show_preview)

            def import_template():
                template_name = template_var.get()
                if not template_name:
                    messagebox.showwarning(_t("common.warning"), "Please select a template")
                    return

                mappings = templates[template_name]
                imported_count = 0

                with transaction() as conn:
                    cursor = conn.cursor()
                    for src, tgt, transform in mappings:
                        cursor.execute('''
                            INSERT INTO integration_data_mappings
                            (install_id, source_field, target_field, transformation_rule, is_active)
                            VALUES (?, ?, ?, ?, 1)
                        ''', (install_id, src, tgt, transform))
                        imported_count += 1

                log_activity('import', 'mapping_template', install_id,
                            details={'template': template_name, 'mappings_created': imported_count})

                messagebox.showinfo(_t("common.success"), f"Imported {imported_count} mapping(s) from '{template_name}'")
                dialog.destroy()
                self.load_mappings()

            ttk.Button(dialog, text="Import Template", command=import_template).pack(pady=10)

        except Exception as e:
            logger.error(f"Error importing mapping template: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to import template: {e}")
