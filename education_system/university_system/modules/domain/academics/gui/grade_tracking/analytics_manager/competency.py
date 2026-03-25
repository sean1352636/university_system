"""Competency-based assessment methods for AnalyticsManager."""

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.scrolledtext as scrolledtext
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.constants import get_connection
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.utils import safe_grab_set


class CompetencyMixin:
    """Mixin providing competency management methods."""

    def _refresh_student_competencies(self, target_student_id=None):
        """Reload student competency assessments, optionally filtered by student ID."""
        tree = getattr(self, 'student_comp_tree', None)
        if not tree or not self._widget_exists(tree):
            return

        filter_id = None
        if target_student_id:
            filter_id = target_student_id
        elif hasattr(self, 'comp_student_filter_var'):
            selected = self.comp_student_filter_var.get()
            if selected and selected != 'All':
                filter_id = selected.split(' - ')[0].strip()

        try:
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            query = '''
            SELECT
                sc.id,
                sc.student_id,
                s.first_name,
                s.last_name,
                c.name,
                COALESCE(cl.level_name, 'Not Specified') AS level_name,
                COALESCE(cl.level_value, 0) AS level_value,
                COALESCE(sc.assessment_date, '') AS assessment_date,
                COALESCE(sc.evidence, '') AS evidence
            FROM student_competencies sc
            JOIN students s ON sc.student_id = s.student_id
            JOIN competencies c ON sc.competency_id = c.competency_id
            LEFT JOIN competency_levels cl ON sc.level_id = cl.level_id
            '''

            params = []
            if filter_id:
                query += ' WHERE sc.student_id = ?'
                params.append(filter_id)

            query += ' ORDER BY sc.assessment_date DESC, s.last_name, s.first_name'
            cursor.execute(query, params)
            rows = cursor.fetchall()

            for record in rows:
                record_id, student_id, first_name, last_name, comp_name, level_name, level_value, assess_date, evidence = record
                student_display = f"{student_id} - {first_name} {last_name}".strip()
                if level_name == 'Not Specified' and level_value:
                    level_display = f"Level {level_value}"
                elif level_value:
                    level_display = f"{level_name} (Level {level_value})"
                else:
                    level_display = level_name

                tree.insert(
                    '',
                    'end',
                    values=(
                        record_id,
                        student_display,
                        comp_name,
                        level_display,
                        assess_date,
                        evidence
                    )
                )

            conn.close()
            self.update_status(f"Loaded {len(rows)} competency assessment records")

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load competency assessments: {exc}")


    def add_competency_dialog(self):
        """Display dialog for creating a new competency."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Competency")
        dialog.geometry("480x360")
        safe_grab_set(dialog)

        ttk.Label(dialog, text="Competency Name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=8)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=40).grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Category:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=8)
        category_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=category_var, width=40).grid(row=1, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=10, pady=8)
        desc_text = scrolledtext.ScrolledText(dialog, width=35, height=8)
        desc_text.grid(row=2, column=1, padx=10, pady=8)

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, pady=15)

        def save_competency():
            name = name_var.get().strip()
            category = category_var.get().strip()
            description = desc_text.get('1.0', tk.END).strip()

            if not name:
                messagebox.showwarning("Validation", "Competency name is required.")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO competencies (name, description, category)
                    VALUES (?, ?, ?)
                    ''',
                    (name, description or None, category or None)
                )
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Competency '{name}' added successfully.")
                dialog.destroy()
                self.refresh_competencies()
                self.populate_filter_combos()

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to add competency: {exc}")

        ttk.Button(button_frame, text="Save", command=save_competency).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)


    def edit_competency_dialog(self):
        """Edit the selected competency."""
        tree = getattr(self, 'competency_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("No Selection", "Please select a competency to edit.")
            return

        selected_item = tree.selection()[0]
        values = tree.item(selected_item, 'values')
        competency_id = values[0]

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT name, description, category
                FROM competencies
                WHERE competency_id = ?
                ''',
                (competency_id,)
            )
            competency = cursor.fetchone()
            conn.close()

            if not competency:
                messagebox.showerror("Error", "Selected competency no longer exists.")
                return

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load competency: {exc}")
            return

        name_val, desc_val, category_val = competency

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Competency")
        dialog.geometry("480x360")
        safe_grab_set(dialog)

        ttk.Label(dialog, text="Competency Name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=8)
        name_var = tk.StringVar(value=name_val or "")
        ttk.Entry(dialog, textvariable=name_var, width=40).grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Category:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=8)
        category_var = tk.StringVar(value=category_val or "")
        ttk.Entry(dialog, textvariable=category_var, width=40).grid(row=1, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=10, pady=8)
        desc_text = scrolledtext.ScrolledText(dialog, width=35, height=8)
        desc_text.grid(row=2, column=1, padx=10, pady=8)
        desc_text.insert('1.0', desc_val or "")

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, pady=15)

        def update_competency():
            new_name = name_var.get().strip()
            new_category = category_var.get().strip()
            new_description = desc_text.get('1.0', tk.END).strip()

            if not new_name:
                messagebox.showwarning("Validation", "Competency name is required.")
                return

            try:
                conn_edit = get_connection()
                cursor_edit = conn_edit.cursor()
                cursor_edit.execute(
                    '''
                    UPDATE competencies
                    SET name = ?, description = ?, category = ?
                    WHERE competency_id = ?
                    ''',
                    (new_name, new_description or None, new_category or None, competency_id)
                )
                conn_edit.commit()
                conn_edit.close()

                messagebox.showinfo("Success", "Competency updated successfully.")
                dialog.destroy()
                self.refresh_competencies()
                self.populate_filter_combos()

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to update competency: {exc}")

        ttk.Button(button_frame, text="Save Changes", command=update_competency).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)


    def delete_competency(self):
        """Delete the selected competency and related records."""
        tree = getattr(self, 'competency_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("No Selection", "Please select a competency to delete.")
            return

        selected_item = tree.selection()[0]
        comp_id, comp_name = tree.item(selected_item, 'values')[:2]

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete competency '{comp_name}'?\n\n"
            "All related levels, mappings, and student records will also be removed."
        )
        if not confirm:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('DELETE FROM assessment_competencies WHERE competency_id = ?', (comp_id,))
            cursor.execute('DELETE FROM student_competencies WHERE competency_id = ?', (comp_id,))
            cursor.execute('DELETE FROM competency_levels WHERE competency_id = ?', (comp_id,))
            cursor.execute('DELETE FROM competencies WHERE competency_id = ?', (comp_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Competency '{comp_name}' deleted.")
            self.refresh_competencies()
            self.populate_filter_combos()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to delete competency: {exc}")


    def manage_competency_levels(self):
        """Open management dialog for competency levels."""
        tree = getattr(self, 'competency_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("No Selection", "Select a competency to manage levels.")
            return

        selected_item = tree.selection()[0]
        comp_id, comp_name = tree.item(selected_item, 'values')[:2]

        level_window = tk.Toplevel(self.root)
        level_window.title(f"Competency Levels - {comp_name}")
        level_window.geometry("600x420")
        safe_grab_set(level_window)

        columns = ('Level ID', 'Name', 'Value', 'Description')
        level_tree = ttk.Treeview(level_window, columns=columns, show='headings')
        for col in columns:
            level_tree.heading(col, text=col)
            anchor = 'w' if col == 'Description' else 'center'
            width = 260 if col == 'Description' else 100
            level_tree.column(col, width=width, anchor=anchor)
        level_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(level_window)
        btn_frame.pack(pady=5)

        def refresh_levels():
            try:
                for item in level_tree.get_children():
                    level_tree.delete(item)

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT level_id, level_name, level_value, COALESCE(description, '')
                    FROM competency_levels
                    WHERE competency_id = ?
                    ORDER BY level_value
                    ''',
                    (comp_id,)
                )
                rows = cursor.fetchall()
                conn.close()

                for level_id, level_name, level_value, description in rows:
                    level_tree.insert(
                        '',
                        'end',
                        values=(level_id, level_name, level_value, description)
                    )

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to load levels: {exc}")

        def add_level():
            dialog = tk.Toplevel(level_window)
            dialog.title("Add Level")
            dialog.geometry("360x260")
            safe_grab_set(dialog)

            ttk.Label(dialog, text="Level Name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=8)
            level_name_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=level_name_var, width=30).grid(row=0, column=1, padx=10, pady=8)

            ttk.Label(dialog, text="Value (numeric order):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=8)
            level_value_var = tk.StringVar(value="1")
            ttk.Entry(dialog, textvariable=level_value_var, width=10).grid(row=1, column=1, padx=10, pady=8, sticky=tk.W)

            ttk.Label(dialog, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=10, pady=8)
            desc_box = scrolledtext.ScrolledText(dialog, width=28, height=5)
            desc_box.grid(row=2, column=1, padx=10, pady=8)

            def save_level():
                name = level_name_var.get().strip()
                try:
                    value = int(level_value_var.get().strip())
                except ValueError:
                    messagebox.showwarning("Validation", "Level value must be an integer.")
                    return
                description = desc_box.get('1.0', tk.END).strip()

                if not name:
                    messagebox.showwarning("Validation", "Level name is required.")
                    return

                try:
                    conn_add = get_connection()
                    cursor_add = conn_add.cursor()
                    cursor_add.execute(
                        '''
                        INSERT INTO competency_levels (competency_id, level_name, level_value, description)
                        VALUES (?, ?, ?, ?)
                        ''',
                        (comp_id, name, value, description or None)
                    )
                    conn_add.commit()
                    conn_add.close()

                    dialog.destroy()
                    refresh_levels()
                    self.refresh_competencies()

                except sqlite3.Error as exc:
                    messagebox.showerror("Database Error", f"Failed to add level: {exc}")

            ttk.Button(dialog, text="Save", command=save_level).grid(row=3, column=0, columnspan=2, pady=12)

        def edit_level():
            selection = level_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Select a level to edit.")
                return

            level_id, level_name, level_value, description = level_tree.item(selection[0], 'values')

            dialog = tk.Toplevel(level_window)
            dialog.title("Edit Level")
            dialog.geometry("360x260")
            safe_grab_set(dialog)

            ttk.Label(dialog, text="Level Name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=8)
            level_name_var = tk.StringVar(value=level_name)
            ttk.Entry(dialog, textvariable=level_name_var, width=30).grid(row=0, column=1, padx=10, pady=8)

            ttk.Label(dialog, text="Value (numeric order):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=8)
            level_value_var = tk.StringVar(value=str(level_value))
            ttk.Entry(dialog, textvariable=level_value_var, width=10).grid(row=1, column=1, padx=10, pady=8, sticky=tk.W)

            ttk.Label(dialog, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=10, pady=8)
            desc_box = scrolledtext.ScrolledText(dialog, width=28, height=5)
            desc_box.grid(row=2, column=1, padx=10, pady=8)
            desc_box.insert('1.0', description or "")

            def save_changes():
                name = level_name_var.get().strip()
                try:
                    value = int(level_value_var.get().strip())
                except ValueError:
                    messagebox.showwarning("Validation", "Level value must be an integer.")
                    return
                desc_val = desc_box.get('1.0', tk.END).strip()

                if not name:
                    messagebox.showwarning("Validation", "Level name is required.")
                    return

                try:
                    conn_edit = get_connection()
                    cursor_edit = conn_edit.cursor()
                    cursor_edit.execute(
                        '''
                        UPDATE competency_levels
                        SET level_name = ?, level_value = ?, description = ?
                        WHERE level_id = ?
                        ''',
                        (name, value, desc_val or None, level_id)
                    )
                    conn_edit.commit()
                    conn_edit.close()

                    dialog.destroy()
                    refresh_levels()
                    self.refresh_competencies()

                except sqlite3.Error as exc:
                    messagebox.showerror("Database Error", f"Failed to update level: {exc}")

            ttk.Button(dialog, text="Save Changes", command=save_changes).grid(row=3, column=0, columnspan=2, pady=12)

        def delete_level():
            selection = level_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Select a level to delete.")
                return

            level_id, level_name = level_tree.item(selection[0], 'values')[:2]

            confirm_delete = messagebox.askyesno(
                "Confirm Delete",
                f"Delete level '{level_name}'?\n\n"
                "Student competency records referencing this level will also be removed."
            )
            if not confirm_delete:
                return

            try:
                conn_del = get_connection()
                cursor_del = conn_del.cursor()
                cursor_del.execute('DELETE FROM student_competencies WHERE level_id = ?', (level_id,))
                cursor_del.execute('DELETE FROM competency_levels WHERE level_id = ?', (level_id,))
                conn_del.commit()
                conn_del.close()

                refresh_levels()
                self.refresh_competencies()
                self._refresh_student_competencies()

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to delete level: {exc}")

        ttk.Button(btn_frame, text="Add Level", command=add_level).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Level", command=edit_level).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Level", command=delete_level).pack(side=tk.LEFT, padx=5)

        refresh_levels()


    def refresh_competencies(self):
        """Load competencies into the treeview."""
        tree = getattr(self, 'competency_tree', None)
        if not tree or not self._widget_exists(tree):
            return

        try:
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT
                    c.competency_id,
                    c.name,
                    COALESCE(c.category, 'Uncategorized') AS category,
                    COALESCE(c.description, ''),
                    COUNT(DISTINCT cl.level_id) AS level_count
                FROM competencies c
                LEFT JOIN competency_levels cl ON c.competency_id = cl.competency_id
                GROUP BY c.competency_id, c.name, c.category, c.description
                ORDER BY c.name
                '''
            )
            rows = cursor.fetchall()
            conn.close()

            for comp_id, name, category, description, level_count in rows:
                tree.insert(
                    '',
                    'end',
                    values=(comp_id, name, category, description, level_count)
                )

            self.update_status(f"Loaded {len(rows)} competencies")
            self._refresh_student_competencies()
            self.populate_filter_combos()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load competencies: {exc}")


    def map_assessment_competency_dialog(self):
        """Map an assessment to a competency."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Map Assessment to Competency")
        dialog.geometry("520x260")
        safe_grab_set(dialog)

        assessment_var = tk.StringVar()
        competency_var = tk.StringVar()
        weight_var = tk.StringVar(value="1.0")

        ttk.Label(dialog, text="Assessment:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        assessment_combo = ttk.Combobox(dialog, textvariable=assessment_var, width=45, state='readonly')
        assessment_combo.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(dialog, text="Competency:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        competency_combo = ttk.Combobox(dialog, textvariable=competency_var, width=45, state='readonly')
        competency_combo.grid(row=1, column=1, padx=10, pady=10)

        ttk.Label(dialog, text="Weight:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=10)
        ttk.Entry(dialog, textvariable=weight_var, width=10).grid(row=2, column=1, padx=10, pady=10, sticky=tk.W)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT assessment_id, assessment_name, module_code
                FROM assessments
                ORDER BY module_code, assessment_name
                '''
            )
            assessments = cursor.fetchall()
            assessment_options = {
                f"{a_id} - {a_name} ({module})": a_id for a_id, a_name, module in assessments
            }
            assessment_combo['values'] = list(assessment_options.keys())

            cursor.execute(
                '''
                SELECT competency_id, name
                FROM competencies
                ORDER BY name
                '''
            )
            competencies = cursor.fetchall()
            competency_options = {f"{c_id} - {name}": c_id for c_id, name in competencies}
            competency_combo['values'] = list(competency_options.keys())

            conn.close()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load data: {exc}")
            dialog.destroy()
            return

        def save_mapping():
            assessment_key = assessment_var.get()
            competency_key = competency_var.get()

            if assessment_key not in assessment_options or competency_key not in competency_options:
                messagebox.showwarning("Validation", "Please select both assessment and competency.")
                return

            try:
                weight = float(weight_var.get())
            except ValueError:
                messagebox.showwarning("Validation", "Weight must be a numeric value.")
                return

            assessment_id = assessment_options[assessment_key]
            competency_id = competency_options[competency_key]

            try:
                conn_map = get_connection()
                cursor_map = conn_map.cursor()

                cursor_map.execute(
                    '''
                    SELECT id FROM assessment_competencies
                    WHERE assessment_id = ? AND competency_id = ?
                    ''',
                    (assessment_id, competency_id)
                )
                existing = cursor_map.fetchone()

                if existing:
                    if messagebox.askyesno(
                        "Mapping Exists",
                        "Mapping already exists. Update weight instead?"
                    ):
                        cursor_map.execute(
                            '''
                            UPDATE assessment_competencies
                            SET weight = ?
                            WHERE id = ?
                            ''',
                            (weight, existing[0])
                        )
                        action_message = "Mapping weight updated."
                    else:
                        conn_map.close()
                        return
                else:
                    cursor_map.execute(
                        '''
                        INSERT INTO assessment_competencies (assessment_id, competency_id, weight)
                        VALUES (?, ?, ?)
                        ''',
                        (assessment_id, competency_id, weight)
                    )
                    action_message = "Mapping created."

                conn_map.commit()
                conn_map.close()

                messagebox.showinfo("Success", action_message)
                dialog.destroy()
                self.refresh_competency_mappings()

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to save mapping: {exc}")

        ttk.Button(dialog, text="Save Mapping", command=save_mapping).grid(row=3, column=0, columnspan=2, pady=15)


    def edit_competency_mapping(self):
        """Edit the selected assessment competency mapping."""
        tree = getattr(self, 'mapping_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("No Selection", "Select a mapping to edit.")
            return

        selected_item = tree.selection()[0]
        mapping_id, assessment_display, competency_display, weight_value, module_code = tree.item(selected_item, 'values')

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Mapping")
        dialog.geometry("520x260")
        safe_grab_set(dialog)

        assessment_var = tk.StringVar(value=assessment_display)
        competency_var = tk.StringVar(value=competency_display)
        weight_var = tk.StringVar(value=str(weight_value))

        ttk.Label(dialog, text="Assessment:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        assessment_combo = ttk.Combobox(dialog, textvariable=assessment_var, width=45, state='readonly')
        assessment_combo.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(dialog, text="Competency:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        competency_combo = ttk.Combobox(dialog, textvariable=competency_var, width=45, state='readonly')
        competency_combo.grid(row=1, column=1, padx=10, pady=10)

        ttk.Label(dialog, text="Weight:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=10)
        ttk.Entry(dialog, textvariable=weight_var, width=10).grid(row=2, column=1, padx=10, pady=10, sticky=tk.W)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT assessment_id, assessment_name, module_code
                FROM assessments
                ORDER BY module_code, assessment_name
                '''
            )
            assessments = cursor.fetchall()
            assessment_options = {
                f"{a_id} - {a_name} ({module})": a_id for a_id, a_name, module in assessments
            }
            assessment_combo['values'] = list(assessment_options.keys())

            cursor.execute(
                '''
                SELECT competency_id, name
                FROM competencies
                ORDER BY name
                '''
            )
            competencies = cursor.fetchall()
            competency_options = {f"{c_id} - {name}": c_id for c_id, name in competencies}
            competency_combo['values'] = list(competency_options.keys())

            conn.close()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load mapping data: {exc}")
            dialog.destroy()
            return

        def save_changes():
            assessment_key = assessment_var.get()
            competency_key = competency_var.get()

            if assessment_key not in assessment_options or competency_key not in competency_options:
                messagebox.showwarning("Validation", "Please select both assessment and competency.")
                return

            try:
                weight = float(weight_var.get())
            except ValueError:
                messagebox.showwarning("Validation", "Weight must be numeric.")
                return

            assessment_id = assessment_options[assessment_key]
            competency_id = competency_options[competency_key]

            try:
                conn_edit = get_connection()
                cursor_edit = conn_edit.cursor()

                cursor_edit.execute(
                    '''
                    SELECT id
                    FROM assessment_competencies
                    WHERE assessment_id = ? AND competency_id = ? AND id != ?
                    ''',
                    (assessment_id, competency_id, mapping_id)
                )
                duplicate = cursor_edit.fetchone()
                if duplicate:
                    messagebox.showwarning(
                        "Duplicate Mapping",
                        "Another mapping already links this assessment and competency."
                    )
                    conn_edit.close()
                    return

                cursor_edit.execute(
                    '''
                    UPDATE assessment_competencies
                    SET assessment_id = ?, competency_id = ?, weight = ?
                    WHERE id = ?
                    ''',
                    (assessment_id, competency_id, weight, mapping_id)
                )

                conn_edit.commit()
                conn_edit.close()

                messagebox.showinfo("Success", "Mapping updated successfully.")
                dialog.destroy()
                self.refresh_competency_mappings()

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to update mapping: {exc}")

        ttk.Button(dialog, text="Save Changes", command=save_changes).grid(row=3, column=0, columnspan=2, pady=15)


    def remove_competency_mapping(self):
        """Delete the selected competency mapping."""
        tree = getattr(self, 'mapping_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("No Selection", "Select a mapping to remove.")
            return

        mapping_id = tree.item(tree.selection()[0], 'values')[0]
        if not messagebox.askyesno("Confirm Delete", "Remove selected mapping?"):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM assessment_competencies WHERE id = ?', (mapping_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Mapping removed.")
            self.refresh_competency_mappings()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to remove mapping: {exc}")


    def refresh_competency_mappings(self):
        """Refresh the assessment-to-competency mapping list."""
        tree = getattr(self, 'mapping_tree', None)
        if not tree or not self._widget_exists(tree):
            return

        try:
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT
                    ac.id,
                    a.assessment_name,
                    c.name,
                    ac.weight,
                    a.module_code
                FROM assessment_competencies ac
                JOIN assessments a ON ac.assessment_id = a.assessment_id
                JOIN competencies c ON ac.competency_id = c.competency_id
                ORDER BY a.module_code, a.assessment_name
                '''
            )
            rows = cursor.fetchall()
            conn.close()

            for map_id, assessment_name, competency_name, weight, module_code in rows:
                tree.insert(
                    '',
                    'end',
                    values=(
                        map_id,
                        f"{assessment_name} ({module_code})",
                        competency_name,
                        weight,
                        module_code
                    )
                )

            self.update_status(f"Loaded {len(rows)} competency mappings")

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load mappings: {exc}")


    def record_student_competency_dialog(self):
        """Record a competency achievement for a student."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Student Competency")
        dialog.geometry("560x420")
        safe_grab_set(dialog)

        student_var = tk.StringVar()
        competency_var = tk.StringVar()
        level_var = tk.StringVar()
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(dialog, text="Student:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=8)
        student_combo = ttk.Combobox(dialog, textvariable=student_var, width=40, state='readonly')
        student_combo.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Competency:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=8)
        competency_combo = ttk.Combobox(dialog, textvariable=competency_var, width=40, state='readonly')
        competency_combo.grid(row=1, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Level:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=8)
        level_combo = ttk.Combobox(dialog, textvariable=level_var, width=40, state='readonly')
        level_combo.grid(row=2, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Assessment Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=8)
        ttk.Entry(dialog, textvariable=date_var, width=20).grid(row=3, column=1, padx=10, pady=8, sticky=tk.W)

        ttk.Label(dialog, text="Evidence / Notes:").grid(row=4, column=0, sticky=tk.NW, padx=10, pady=8)
        evidence_text = scrolledtext.ScrolledText(dialog, width=38, height=8)
        evidence_text.grid(row=4, column=1, padx=10, pady=8)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT student_id, first_name, last_name
                FROM students
                ORDER BY last_name, first_name
                '''
            )
            students = cursor.fetchall()
            student_options = {f"{sid} - {fname} {lname}".strip(): sid for sid, fname, lname in students}
            student_combo['values'] = list(student_options.keys())
            if student_combo['values']:
                student_var.set(student_combo['values'][0])

            cursor.execute(
                '''
                SELECT competency_id, name
                FROM competencies
                ORDER BY name
                '''
            )
            competencies = cursor.fetchall()
            competency_options = {f"{cid} - {name}": cid for cid, name in competencies}
            competency_combo['values'] = list(competency_options.keys())
            if competency_combo['values']:
                competency_var.set(competency_combo['values'][0])

            conn.close()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load students or competencies: {exc}")
            dialog.destroy()
            return

        def load_levels_for_competency(event=None):
            key = competency_var.get()
            competency_id = competency_options.get(key)
            if not competency_id:
                level_combo['values'] = []
                level_var.set('')
                return

            try:
                conn_levels = get_connection()
                cursor_levels = conn_levels.cursor()
                cursor_levels.execute(
                    '''
                    SELECT level_id, level_name, level_value
                    FROM competency_levels
                    WHERE competency_id = ?
                    ORDER BY level_value
                    ''',
                    (competency_id,)
                )
                levels = cursor_levels.fetchall()
                conn_levels.close()

                if levels:
                    level_options = {
                        f"{lid} - {lname} (Level {lvalue})": lid for lid, lname, lvalue in levels
                    }
                else:
                    level_options = {"No defined levels": None}

                level_combo['values'] = list(level_options.keys())
                level_combo.level_options = level_options  # attach for later lookup
                if levels:
                    level_var.set(level_combo['values'][0])
                else:
                    level_var.set("No defined levels")

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to load competency levels: {exc}")

        competency_combo.bind('<<ComboboxSelected>>', load_levels_for_competency)

        if competency_combo['values']:
            load_levels_for_competency()
        else:
            level_combo['values'] = []
            level_var.set('')

        def save_record():
            student_key = student_var.get()
            competency_key = competency_var.get()
            level_key = level_var.get()
            evidence = evidence_text.get('1.0', tk.END).strip()
            assessment_date = date_var.get().strip()

            student_id = student_options.get(student_key)
            competency_id = competency_options.get(competency_key)

            if not student_id or not competency_id:
                messagebox.showwarning("Validation", "Student and competency are required.")
                return

            level_id = None
            if hasattr(level_combo, 'level_options'):
                level_id = level_combo.level_options.get(level_key)

            if level_id is None:
                messagebox.showwarning(
                    "Validation",
                    "The selected competency has no levels defined. Please add competency levels first."
                )
                return

            if not assessment_date:
                assessment_date = datetime.now().strftime('%Y-%m-%d')

            try:
                datetime.strptime(assessment_date, '%Y-%m-%d')
            except ValueError:
                messagebox.showwarning("Validation", "Assessment date must be in YYYY-MM-DD format.")
                return

            try:
                conn_save = get_connection()
                cursor_save = conn_save.cursor()
                cursor_save.execute(
                    '''
                    INSERT INTO student_competencies (student_id, competency_id, level_id, assessment_date, evidence)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (student_id, competency_id, level_id, assessment_date, evidence or None)
                )
                conn_save.commit()
                conn_save.close()

                messagebox.showinfo("Success", "Competency record saved.")
                dialog.destroy()
                self._refresh_student_competencies()

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to save competency record: {exc}")

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(button_frame, text="Save Record", command=save_record).pack(side=tk.LEFT, padx=8)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=8)


    def edit_student_competency(self):
        """Edit a previously recorded student competency."""
        tree = getattr(self, 'student_comp_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("No Selection", "Select a student competency record to edit.")
            return

        record_id = tree.item(tree.selection()[0], 'values')[0]

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT student_id, competency_id, level_id, assessment_date, evidence
                FROM student_competencies
                WHERE id = ?
                ''',
                (record_id,)
            )
            record = cursor.fetchone()
            conn.close()

            if not record:
                messagebox.showerror("Error", "Selected competency record no longer exists.")
                return

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load competency record: {exc}")
            return

        student_id, competency_id, level_id, assessment_date, evidence = record

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Student Competency")
        dialog.geometry("560x420")
        safe_grab_set(dialog)

        student_var = tk.StringVar()
        competency_var = tk.StringVar()
        level_var = tk.StringVar()
        date_var = tk.StringVar(value=assessment_date or datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(dialog, text="Student:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=8)
        student_combo = ttk.Combobox(dialog, textvariable=student_var, width=40, state='readonly')
        student_combo.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Competency:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=8)
        competency_combo = ttk.Combobox(dialog, textvariable=competency_var, width=40, state='readonly')
        competency_combo.grid(row=1, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Level:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=8)
        level_combo = ttk.Combobox(dialog, textvariable=level_var, width=40, state='readonly')
        level_combo.grid(row=2, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Assessment Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=8)
        ttk.Entry(dialog, textvariable=date_var, width=20).grid(row=3, column=1, padx=10, pady=8, sticky=tk.W)

        ttk.Label(dialog, text="Evidence / Notes:").grid(row=4, column=0, sticky=tk.NW, padx=10, pady=8)
        evidence_text = scrolledtext.ScrolledText(dialog, width=38, height=8)
        evidence_text.grid(row=4, column=1, padx=10, pady=8)
        evidence_text.insert('1.0', evidence or "")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT student_id, first_name, last_name
                FROM students
                ORDER BY last_name, first_name
                '''
            )
            students = cursor.fetchall()
            student_options = {f"{sid} - {fname} {lname}".strip(): sid for sid, fname, lname in students}
            student_combo['values'] = list(student_options.keys())
            for display, sid in student_options.items():
                if sid == student_id:
                    student_var.set(display)
                    break

            cursor.execute(
                '''
                SELECT competency_id, name
                FROM competencies
                ORDER BY name
                '''
            )
            competencies = cursor.fetchall()
            competency_options = {f"{cid} - {name}": cid for cid, name in competencies}
            competency_combo['values'] = list(competency_options.keys())
            for display, cid in competency_options.items():
                if cid == competency_id:
                    competency_var.set(display)
                    break

            conn.close()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load supporting data: {exc}")
            dialog.destroy()
            return

        def load_levels(event=None):
            key = competency_var.get()
            selected_competency_id = competency_options.get(key)
            level_combo.level_options = {}
            if not selected_competency_id:
                level_combo['values'] = []
                level_var.set('')
                return

            try:
                conn_levels = get_connection()
                cursor_levels = conn_levels.cursor()
                cursor_levels.execute(
                    '''
                    SELECT level_id, level_name, level_value
                    FROM competency_levels
                    WHERE competency_id = ?
                    ORDER BY level_value
                    ''',
                    (selected_competency_id,)
                )
                levels = cursor_levels.fetchall()
                conn_levels.close()

                if levels:
                    level_options = {
                        f"{lid} - {lname} (Level {lvalue})": lid for lid, lname, lvalue in levels
                    }
                else:
                    level_options = {"No defined levels": None}

                level_combo['values'] = list(level_options.keys())
                level_combo.level_options = level_options

                # Select current level if possible
                if level_id:
                    for display, lid in level_options.items():
                        if lid == level_id:
                            level_var.set(display)
                            break
                    else:
                        level_var.set(level_combo['values'][0] if level_combo['values'] else '')
                else:
                    level_var.set(level_combo['values'][0] if level_combo['values'] else '')

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to load competency levels: {exc}")

        competency_combo.bind('<<ComboboxSelected>>', load_levels)
        load_levels()

        def save_changes():
            student_key = student_var.get()
            competency_key = competency_var.get()
            level_key = level_var.get()
            evidence_val = evidence_text.get('1.0', tk.END).strip()
            assessment_date_val = date_var.get().strip()

            student_id_val = student_options.get(student_key)
            competency_id_val = competency_options.get(competency_key)

            if not student_id_val or not competency_id_val:
                messagebox.showwarning("Validation", "Student and competency are required.")
                return

            level_id_val = None
            if hasattr(level_combo, 'level_options'):
                level_id_val = level_combo.level_options.get(level_key)

            if level_id_val is None:
                messagebox.showwarning(
                    "Validation",
                    "The selected competency has no levels defined. Please add competency levels first."
                )
                return

            if not assessment_date_val:
                assessment_date_val = datetime.now().strftime('%Y-%m-%d')

            try:
                datetime.strptime(assessment_date_val, '%Y-%m-%d')
            except ValueError:
                messagebox.showwarning("Validation", "Assessment date must be in YYYY-MM-DD format.")
                return

            try:
                conn_save = get_connection()
                cursor_save = conn_save.cursor()
                cursor_save.execute(
                    '''
                    UPDATE student_competencies
                    SET student_id = ?, competency_id = ?, level_id = ?, assessment_date = ?, evidence = ?
                    WHERE id = ?
                    ''',
                    (student_id_val, competency_id_val, level_id_val, assessment_date_val, evidence_val or None, record_id)
                )
                conn_save.commit()
                conn_save.close()

                messagebox.showinfo("Success", "Competency record updated.")
                dialog.destroy()
                self._refresh_student_competencies()

            except sqlite3.Error as exc:
                messagebox.showerror("Database Error", f"Failed to update record: {exc}")

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT, padx=8)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=8)


    def view_student_competency_profile(self):
        """Show a detailed competency profile for the selected student."""
        tree = getattr(self, 'student_comp_tree', None)
        student_id = None

        if tree and tree.selection():
            student_value = tree.item(tree.selection()[0], 'values')[1]
            student_id = student_value.split(' - ')[0].strip()
        elif hasattr(self, 'comp_student_filter_var'):
            selected = self.comp_student_filter_var.get()
            if selected and selected != 'All':
                student_id = selected.split(' - ')[0].strip()

        if not student_id:
            messagebox.showwarning("No Student", "Select a student record or choose a student from the filter.")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT first_name, middle_name, last_name, course
                FROM students
                WHERE student_id = ?
                ''',
                (student_id,)
            )
            student = cursor.fetchone()
            if not student:
                conn.close()
                messagebox.showerror("Error", "Student not found.")
                return

            first_name, middle_name, last_name, course = student
            full_name = " ".join(part for part in (first_name, middle_name, last_name) if part)

            cursor.execute(
                '''
                SELECT
                    c.name,
                    COALESCE(cl.level_name, 'Not Specified'),
                    COALESCE(cl.level_value, 0),
                    COALESCE(sc.assessment_date, ''),
                    COALESCE(sc.evidence, '')
                FROM student_competencies sc
                JOIN competencies c ON sc.competency_id = c.competency_id
                LEFT JOIN competency_levels cl ON sc.level_id = cl.level_id
                WHERE sc.student_id = ?
                ORDER BY sc.assessment_date DESC
                ''',
                (student_id,)
            )
            records = cursor.fetchall()
            conn.close()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load student profile: {exc}")
            return

        if not records:
            messagebox.showinfo("No Records", "No competency assessments recorded for this student.")
            return

        profile_window = tk.Toplevel(self.root)
        profile_window.title(f"Competency Profile - {full_name}")
        profile_window.geometry("620x480")
        safe_grab_set(profile_window)

        text_area = scrolledtext.ScrolledText(profile_window, width=70, height=25)
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        competencies_summary = {}
        for name, level_name, level_value, assess_date, evidence in records:
            summary = competencies_summary.setdefault(name, {"highest_level": (level_value, level_name), "records": []})
            if level_value > summary["highest_level"][0]:
                summary["highest_level"] = (level_value, level_name)
            summary["records"].append((level_name, level_value, assess_date, evidence))

        lines = [
            f"Student: {full_name} ({student_id})",
            f"Course: {course or 'N/A'}",
            f"Total Recorded Competencies: {len(records)}",
            "-" * 60,
        ]

        for competency_name, details in competencies_summary.items():
            highest_value, highest_name = details["highest_level"]
            level_display = (
                f"{highest_name} (Level {highest_value})" if highest_value else highest_name
            )
            lines.append(f"{competency_name}: Highest Recorded Level - {level_display}")
            for level_name, level_value, assess_date, evidence in details["records"]:
                detail_display = level_name
                if level_value:
                    detail_display = f"{level_name} (Level {level_value})"
                lines.append(f"  • {assess_date or 'Date N/A'} - {detail_display}")
                if evidence:
                    lines.append(f"    Evidence: {evidence}")
            lines.append("")

        text_area.insert('1.0', "\n".join(lines))
        text_area.config(state='disabled')


    def generate_competency_report_dialog(self):
        """Generate tailored competency reports into the preview pane."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Generate Competency Report")
        dialog.geometry("500x320")
        safe_grab_set(dialog)

        report_type_var = tk.StringVar(value="all")

        ttk.Label(dialog, text="Report Type:").pack(anchor=tk.W, padx=10, pady=5)
        ttk.Radiobutton(dialog, text="All Competency Activity", variable=report_type_var, value="all").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(dialog, text="By Student", variable=report_type_var, value="student").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(dialog, text="By Competency", variable=report_type_var, value="competency").pack(anchor=tk.W, padx=20)

        selector_frame = ttk.Frame(dialog)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text="Student:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        student_var = tk.StringVar()
        student_combo = ttk.Combobox(selector_frame, textvariable=student_var, width=35, state='readonly')
        student_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(selector_frame, text="Competency:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        competency_var = tk.StringVar()
        competency_combo = ttk.Combobox(selector_frame, textvariable=competency_var, width=35, state='readonly')
        competency_combo.grid(row=1, column=1, padx=5, pady=5)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT student_id, first_name, last_name
                FROM students
                ORDER BY last_name, first_name
                '''
            )
            students = cursor.fetchall()
            student_options = {f"{sid} - {fname} {lname}".strip(): sid for sid, fname, lname in students}
            student_combo['values'] = list(student_options.keys())

            cursor.execute(
                '''
                SELECT competency_id, name
                FROM competencies
                ORDER BY name
                '''
            )
            competencies = cursor.fetchall()
            competency_options = {f"{cid} - {name}": cid for cid, name in competencies}
            competency_combo['values'] = list(competency_options.keys())

            conn.close()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load report options: {exc}")
            dialog.destroy()
            return

        def run_report():
            report_type = report_type_var.get()

            if report_type == "all":
                dialog.destroy()
                self.generate_competency_profile()
                return

            if report_type == "student":
                student_key = student_var.get()
                student_id = student_options.get(student_key)
                if not student_id:
                    messagebox.showwarning("Validation", "Select a student for the report.")
                    return
                success = self._generate_student_competency_report(student_id)
                if success:
                    dialog.destroy()
                return

            if report_type == "competency":
                competency_key = competency_var.get()
                competency_id = competency_options.get(competency_key)
                if not competency_id:
                    messagebox.showwarning("Validation", "Select a competency for the report.")
                    return
                success = self._generate_competency_focus_report(competency_id)
                if success:
                    dialog.destroy()

        ttk.Button(dialog, text="Generate Report", command=run_report).pack(pady=10)
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack()


    def _generate_student_competency_report(self, student_id):
        """Generate a competency report for a specific student."""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT first_name, middle_name, last_name, course
                FROM students
                WHERE student_id = ?
                ''',
                (student_id,)
            )
            student = cursor.fetchone()
            if not student:
                conn.close()
                messagebox.showerror("Error", "Student not found.")
                return False

            first_name, middle_name, last_name, course = student
            full_name = " ".join(part for part in (first_name, middle_name, last_name) if part)

            cursor.execute(
                '''
                SELECT
                    c.name,
                    COALESCE(cl.level_name, 'Not Specified'),
                    COALESCE(cl.level_value, 0),
                    COALESCE(sc.assessment_date, ''),
                    COALESCE(sc.evidence, '')
                FROM student_competencies sc
                JOIN competencies c ON sc.competency_id = c.competency_id
                LEFT JOIN competency_levels cl ON sc.level_id = cl.level_id
                WHERE sc.student_id = ?
                ORDER BY sc.assessment_date DESC
                ''',
                (student_id,)
            )
            rows = cursor.fetchall()

            conn.close()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to build report: {exc}")
            return False

        if not rows:
            messagebox.showinfo("No Records", "No competency assessments recorded for this student.")
            return False

        total_records = len(rows)
        distinct_competencies = len({row[0] for row in rows})
        dated_records = [row for row in rows if row[3]]
        latest_date = max(row[3] for row in dated_records) if dated_records else "N/A"

        numeric_levels = [row[2] for row in rows if row[2]]
        average_level = (sum(numeric_levels) / len(numeric_levels)) if numeric_levels else None

        overview_lines = [
            f"Student: {full_name} ({student_id})",
            f"Course: {course or 'N/A'}",
            f"Total Competency Records: {total_records}",
            f"Distinct Competencies Documented: {distinct_competencies}",
            f"Latest Assessment Date: {latest_date}",
            f"Average Recorded Level: {average_level:.2f}" if average_level is not None else "Average Recorded Level: N/A"
        ]

        competency_summary = {}
        for name, level_name, level_value, assess_date, evidence in rows:
            entry = competency_summary.setdefault(name, {"highest": (level_value, level_name), "latest": assess_date})
            if level_value > entry["highest"][0]:
                entry["highest"] = (level_value, level_name)
            if assess_date and (not entry["latest"] or assess_date > entry["latest"]):
                entry["latest"] = assess_date

        competency_lines = []
        for comp_name, data in sorted(competency_summary.items()):
            level_value, level_name = data["highest"]
            level_display = level_name if level_value == 0 else f"{level_name} (Level {level_value})"
            competency_lines.append(
                f"{comp_name}: Highest Level {level_display}, Last Assessed {data['latest'] or 'N/A'}"
            )

        recent_lines = []
        for name, level_name, level_value, assess_date, evidence in rows[:10]:
            level_display = level_name if level_value == 0 else f"{level_name} (Level {level_value})"
            line = f"{assess_date or 'Date N/A'} - {name}: {level_display}"
            if evidence:
                line += f" | Evidence: {evidence}"
            recent_lines.append(line)

        sections = [
            ("Student Overview", overview_lines),
            ("Competency Progress Highlights", competency_lines),
            ("Recent Assessments (Max 10)", recent_lines)
        ]

        footer = "Use this report to plan follow-up assessments and celebrate areas of strong competency achievement."
        self._display_report(f"Student Competency Report - {full_name}", sections, footer)
        return True


    def _generate_competency_focus_report(self, competency_id):
        """Generate a report focused on a single competency across students."""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT name, description, category
                FROM competencies
                WHERE competency_id = ?
                ''',
                (competency_id,)
            )
            competency = cursor.fetchone()
            if not competency:
                conn.close()
                messagebox.showerror("Error", "Competency not found.")
                return False

            name, description, category = competency

            cursor.execute(
                '''
                SELECT
                    sc.student_id,
                    s.first_name,
                    s.last_name,
                    COALESCE(cl.level_name, 'Not Specified'),
                    COALESCE(cl.level_value, 0),
                    COALESCE(sc.assessment_date, ''),
                    COALESCE(sc.evidence, '')
                FROM student_competencies sc
                JOIN students s ON sc.student_id = s.student_id
                LEFT JOIN competency_levels cl ON sc.level_id = cl.level_id
                WHERE sc.competency_id = ?
                ORDER BY cl.level_value DESC, sc.assessment_date DESC
                ''',
                (competency_id,)
            )
            rows = cursor.fetchall()

            conn.close()

        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to build report: {exc}")
            return False

        if not rows:
            messagebox.showinfo("No Records", "No student assessments recorded for this competency.")
            return False

        total_students = len({row[0] for row in rows})
        total_records = len(rows)
        level_values = [row[4] for row in rows if row[4]]
        average_level = (sum(level_values) / len(level_values)) if level_values else None

        overview_lines = [
            f"Competency: {name}",
            f"Category: {category or 'Uncategorized'}",
            f"Description: {description or 'N/A'}",
            f"Students Assessed: {total_students}",
            f"Total Records: {total_records}",
            f"Average Recorded Level: {average_level:.2f}" if average_level is not None else "Average Recorded Level: N/A"
        ]

        top_performers = []
        seen_students = set()
        for student_id, first_name, last_name, level_name, level_value, assess_date, _ in rows:
            if student_id in seen_students:
                continue
            seen_students.add(student_id)
            level_display = level_name if level_value == 0 else f"{level_name} (Level {level_value})"
            top_performers.append(
                f"{first_name} {last_name} ({student_id}) - {level_display} on {assess_date or 'Date N/A'}"
            )
            if len(top_performers) == 10:
                break

        activity_lines = []
        for student_id, first_name, last_name, level_name, level_value, assess_date, evidence in rows[:12]:
            level_display = level_name if level_value == 0 else f"{level_name} (Level {level_value})"
            entry = f"{assess_date or 'Date N/A'} - {first_name} {last_name} ({student_id}): {level_display}"
            if evidence:
                entry += f" | Evidence: {evidence}"
            activity_lines.append(entry)

        sections = [
            ("Competency Overview", overview_lines),
            ("Top Recorded Performances", top_performers),
            ("Recent Activity (Max 12 Records)", activity_lines)
        ]

        footer = "Leverage high performers as exemplars and consider support plans for students with limited evidence."
        self._display_report(f"Competency Report - {name}", sections, footer)
        return True


    def filter_student_competencies(self, event):
        """Filter student competencies"""
        self._refresh_student_competencies()
