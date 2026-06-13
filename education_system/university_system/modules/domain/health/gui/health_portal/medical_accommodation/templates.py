# templates.py
# Template management mixin and dialog classes for AccommodationGUI.

from education_system.university_system.modules.domain.health.gui.health_portal.medical_accommodation._common import (
    tk, ttk, messagebox, simpledialog,
    datetime, timedelta, json, sqlite3, Path,
    CLI_AVAILABLE, TEMPLATES_TABLE, get_connection, logger,
)

if CLI_AVAILABLE:
    from education_system.university_system.modules.domain.health.gui.health_portal.medical_accommodation._common import (
        get_accommodation_types, cli_check_conflict,
        log_action, cli_notify_student,
    )

from education_system.university_system.modules.domain.health.gui.health_portal.medical_accommodation.utils import resolve_user_identifier, check_conflict


class TemplateMixin:
    """Template management methods for AccommodationGUI."""

    def import_medical_templates(self):
        """Import medical templates from JSON files into the database"""
        try:
            from education_system.university_system.core import paths

            medical_templates_dir = paths.MEDICAL_TEMPLATES_DIR

            if not medical_templates_dir.exists():
                messagebox.showerror("Error", f"Medical templates directory not found: {medical_templates_dir}")
                return

            # Find all JSON files in the medical templates directory
            json_files = list(medical_templates_dir.glob("*.json"))

            if not json_files:
                messagebox.showinfo("Import", "No medical template JSON files found in the directory.")
                return

            imported_count = 0
            skipped_count = 0
            error_count = 0

            with get_connection() as conn:
                cursor = conn.cursor()

                for json_file in json_files:
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            template_data = json.load(f)

                        template_name = template_data.get('template_name', json_file.stem)
                        accommodation_type = template_data.get('accommodation_type', 'Medical')
                        description = template_data.get('description', '')
                        duration_days = template_data.get('duration_days', 365)

                        cursor.execute("SELECT COUNT(*) FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (template_name,))
                        if cursor.fetchone()[0] > 0:
                            skipped_count += 1
                            continue

                        cursor.execute(
                            "INSERT INTO [" + TEMPLATES_TABLE + "]"
                            " (name, accommodation_type, description, start_offset_days, duration_days, created_by, created_at)"
                            " VALUES (?, ?, ?, ?, ?, ?, ?)", (
                            template_name,
                            accommodation_type,
                            description,
                            0,
                            duration_days,
                            'System',
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        ))

                        imported_count += 1

                    except Exception as e:
                        error_count += 1
                        print(f"Error importing {json_file.name}: {e}")
                        continue

                conn.commit()

            message = f"Import complete!\n\n"
            message += f"\u2713 Imported: {imported_count} templates\n"
            if skipped_count > 0:
                message += f"\u2298 Skipped (already exist): {skipped_count} templates\n"
            if error_count > 0:
                message += f"\u2717 Errors: {error_count} templates\n"

            messagebox.showinfo("Import Medical Templates", message)
            self.refresh_templates()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to import medical templates: {str(e)}")

    def show_templates_usage_dialog(self):
        """Show dialog for templates usage statistics"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, COUNT(*) as usage_count"
                    " FROM accommodations a"
                    " JOIN [" + TEMPLATES_TABLE + "] t ON a.notes LIKE '%Applied from template: ' || t.name || '%'"
                    " GROUP BY t.name"
                    " ORDER BY usage_count DESC"
                )
                usage_stats = cursor.fetchall()

            dialog = tk.Toplevel(self.root)
            dialog.title("Template Usage Statistics")
            dialog.geometry("500x400")
            dialog.transient(self.root)

            tree = ttk.Treeview(dialog, columns=('Template', 'Usage Count'), show='headings')
            tree.heading('Template', text='Template Name')
            tree.heading('Usage Count', text='Times Used')
            tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            for template_name, count in usage_stats:
                tree.insert('', 'end', values=(template_name, count))

            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template usage: {str(e)}")

    def save_template_dialog(self):
        """Show dialog to save new template"""
        dialog = TemplateDialog(self.root, "Save Template")
        if dialog.result:
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM [" + TEMPLATES_TABLE + "] WHERE name = ?",
                                 (dialog.result['name'],))
                    if cursor.fetchone():
                        if not messagebox.askyesno("Template Exists",
                            f"Template '{dialog.result['name']}' already exists. Overwrite?"):
                            return

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                user = resolve_user_identifier(auth_instance=self.auth)

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO [" + TEMPLATES_TABLE + "]"
                        " (name, accommodation_type, description, start_offset_days,"
                        " duration_days, created_by, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                        dialog.result['name'],
                        dialog.result['accommodation_type'],
                        dialog.result['description'],
                        dialog.result['start_offset_days'],
                        dialog.result['duration_days'],
                        user, now, now
                    ))
                    conn.commit()

                log_action('save_template', None, f"Saved template: {dialog.result['name']}")

                messagebox.showinfo("Success", f"Template '{dialog.result['name']}' saved successfully")
                self.refresh_templates()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save template: {str(e)}")

    def apply_template_dialog(self):
        """Show dialog to apply template"""
        dialog = ApplyTemplateDialog(self.root)
        if dialog.result:
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT accommodation_type, description, start_offset_days, duration_days"
                        " FROM [" + TEMPLATES_TABLE + "] WHERE name = ?",
                        (dialog.result['template_name'],))

                    template = cursor.fetchone()
                    if not template:
                        messagebox.showerror("Error", "Template not found")
                        return

                    typ, desc, offset, duration = template

                    start_date = datetime.now() + timedelta(days=offset)
                    end_date = start_date + timedelta(days=duration)

                    if check_conflict(dialog.result['student_id'], typ,
                                    start_date.strftime('%Y-%m-%d'),
                                    end_date.strftime('%Y-%m-%d')):
                        if not messagebox.askyesno("Conflict",
                            "This accommodation overlaps with an existing record. Continue anyway?"):
                            return

                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    notes = f"Applied from template: {dialog.result['template_name']}"

                    cursor.execute('''
                        INSERT INTO accommodations
                        (student_id, accommodation_type, description, start_date, end_date,
                         status, notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        dialog.result['student_id'],
                        typ, desc,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d'),
                        'active', notes, now, now
                    ))

                    aid = cursor.lastrowid
                    conn.commit()

                log_action('apply_template', aid,
                         f"Applied template {dialog.result['template_name']} to student {dialog.result['student_id']}")

                cli_notify_student(dialog.result['student_id'], 'Accommodation Template Applied',
                             f"Template '{dialog.result['template_name']}' for {typ} has been applied.")

                messagebox.showinfo("Success", f"Template applied successfully to student {dialog.result['student_id']}")
                self.refresh_data()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to apply template: {str(e)}")

    def apply_template_with_data(self, template_data):
        """Apply template with provided data"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT accommodation_type, description, start_offset_days, duration_days"
                    " FROM [" + TEMPLATES_TABLE + "] WHERE name = ?",
                    (template_data['template_name'],))

                template = cursor.fetchone()
                if not template:
                    messagebox.showerror("Error", "Template not found")
                    return

                typ, desc, offset, duration = template

                start_date = datetime.now() + timedelta(days=offset)
                end_date = start_date + timedelta(days=duration)

                if check_conflict(template_data['student_id'], typ,
                                start_date.strftime('%Y-%m-%d'),
                                end_date.strftime('%Y-%m-%d')):
                    if not messagebox.askyesno("Conflict",
                        "This accommodation overlaps with an existing record. Continue anyway?"):
                        return

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                notes = f"Applied from template: {template_data['template_name']}"

                cursor.execute('''
                    INSERT INTO accommodations
                    (student_id, accommodation_type, description, start_date, end_date,
                     status, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    template_data['student_id'],
                    typ, desc,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    'active', notes, now, now
                ))

                conn.commit()
                messagebox.showinfo("Success", "Template applied successfully")
                self.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply template: {str(e)}")

    def edit_template_dialog(self):
        """Edit selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to edit")
            return

        template_name = self.templates_tree.item(selection[0])['values'][0]

        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (template_name,))
                template_data = cursor.fetchone()

            if not template_data:
                messagebox.showerror("Error", "Template not found")
                return

            dialog = TemplateDialog(self.root, "Edit Template", template_data)
            if dialog.result:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE [" + TEMPLATES_TABLE + "] SET"
                        " accommodation_type = ?, description = ?, start_offset_days = ?,"
                        " duration_days = ?, updated_at = ?"
                        " WHERE name = ?", (
                        dialog.result['accommodation_type'],
                        dialog.result['description'],
                        dialog.result['start_offset_days'],
                        dialog.result['duration_days'],
                        now,
                        template_name
                    ))
                    conn.commit()

                messagebox.showinfo("Success", f"Template '{template_name}' updated successfully")
                self.refresh_templates()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit template: {str(e)}")

    def delete_template_dialog(self):
        """Delete selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete")
            return

        template_name = self.templates_tree.item(selection[0])['values'][0]

        if not messagebox.askyesno("Confirm Deletion",
            f"Are you sure you want to delete template '{template_name}'?"):
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (template_name,))
                conn.commit()

            messagebox.showinfo("Success", f"Template '{template_name}' deleted successfully")
            self.refresh_templates()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete template: {str(e)}")

    def manage_templates_dialog(self):
        """Show templates management dialog"""
        TemplateManagerDialog(self.root, self)


# --- Dialog Classes ---

class TemplateDialog:
    """Dialog for creating/editing templates"""

    def __init__(self, parent, title, current_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)

        self.create_widgets(current_data)

        self.dialog.update_idletasks()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        self.dialog.wait_window()

    def create_widgets(self, current_data):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Template Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar(value=current_data['name'] if current_data else '')
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=5, sticky='ew')

        ttk.Label(main_frame, text="Accommodation Type:").grid(row=1, column=0, sticky='w', pady=5)
        self.type_var = tk.StringVar(value=current_data['accommodation_type'] if current_data else '')
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=28)
        if CLI_AVAILABLE:
            type_combo['values'] = get_accommodation_types()
        type_combo.grid(row=1, column=1, pady=5, sticky='ew')

        ttk.Label(main_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.description_text = tk.Text(main_frame, height=3, width=30)
        if current_data and current_data['description']:
            self.description_text.insert(tk.END, current_data['description'])
        self.description_text.grid(row=2, column=1, pady=5, sticky='ew')

        ttk.Label(main_frame, text="Start Offset (days):").grid(row=3, column=0, sticky='w', pady=5)
        self.offset_var = tk.StringVar(value=str(current_data['start_offset_days']) if current_data else '0')
        ttk.Entry(main_frame, textvariable=self.offset_var, width=30).grid(row=3, column=1, pady=5, sticky='ew')

        ttk.Label(main_frame, text="Duration (days):").grid(row=4, column=0, sticky='w', pady=5)
        self.duration_var = tk.StringVar(value=str(current_data['duration_days']) if current_data else '365')
        ttk.Entry(main_frame, textvariable=self.duration_var, width=30).grid(row=4, column=1, pady=5, sticky='ew')

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def save(self):
        """Save the template"""
        if not self.name_var.get().strip():
            messagebox.showerror("Error", "Template name is required")
            return

        if not self.type_var.get().strip():
            messagebox.showerror("Error", "Accommodation type is required")
            return

        try:
            offset = int(self.offset_var.get())
            if offset < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Start offset must be a non-negative number")
            return

        try:
            duration = int(self.duration_var.get())
            if duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Duration must be a positive number")
            return

        self.result = {
            'name': self.name_var.get().strip(),
            'accommodation_type': self.type_var.get().strip(),
            'description': self.description_text.get(1.0, tk.END).strip() or None,
            'start_offset_days': offset,
            'duration_days': duration
        }

        self.dialog.destroy()

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class ApplyTemplateDialog:
    """Dialog for applying templates"""

    def __init__(self, parent):
        self.result = None
        self.student_map = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Apply Template")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)

        self.create_widgets()

        self.dialog.update_idletasks()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        self.dialog.wait_window()

    def _load_students(self):
        """Load students for dropdown."""
        students = []
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT student_id, first_name, last_name FROM students ORDER BY last_name, first_name"
                )
                for row in cursor.fetchall():
                    sid, first, last = row
                    label = f"{sid} - {(first or '')} {(last or '')}".strip()
                    students.append(label)
                    self.student_map[label] = sid
        except Exception:
            pass
        return students

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Student:").grid(row=0, column=0, sticky='w', pady=5)
        self.student_id_var = tk.StringVar()
        student_combo = ttk.Combobox(main_frame, textvariable=self.student_id_var, width=30)
        student_combo['values'] = self._load_students()
        student_combo.grid(row=0, column=1, pady=5, sticky='ew')

        ttk.Label(main_frame, text="Template:").grid(row=1, column=0, sticky='w', pady=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(main_frame, textvariable=self.template_var, width=28)
        self.template_combo.grid(row=1, column=1, pady=5, sticky='ew')

        self.load_templates()

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Apply", command=self.apply).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def load_templates(self):
        """Load available templates"""
        if not CLI_AVAILABLE:
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM [" + TEMPLATES_TABLE + "] ORDER BY name")
                templates = [row[0] for row in cursor.fetchall()]
                self.template_combo['values'] = templates
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")

    def _get_student_id(self):
        """Extract student ID from dropdown selection or raw input."""
        raw = self.student_id_var.get().strip()
        if raw in self.student_map:
            return self.student_map[raw]
        return raw

    def apply(self):
        """Apply the template"""
        student_id = self._get_student_id()
        if not student_id:
            messagebox.showerror("Error", "Student is required")
            return

        if not self.template_var.get().strip():
            messagebox.showerror("Error", "Please select a template")
            return

        if CLI_AVAILABLE:
            from education_system.university_system.modules.domain.health.gui.health_portal.medical_accommodation._common import validate_student_id
            if not validate_student_id(student_id):
                messagebox.showerror("Error", "Student ID not found in the system")
                return

        self.result = {
            'student_id': student_id,
            'template_name': self.template_var.get().strip()
        }

        self.dialog.destroy()

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class TemplateManagerDialog:
    """Dialog for managing templates"""

    def __init__(self, parent, gui_parent):
        self.gui_parent = gui_parent

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Template Manager")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_templates()

    def create_widgets(self):
        """Create template manager widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        list_frame = ttk.LabelFrame(main_frame, text="Templates")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.template_tree = ttk.Treeview(list_frame, columns=(
            'Name', 'Type', 'Description', 'Duration', 'Created By'
        ), show='headings')

        columns = {
            'Name': 150,
            'Type': 150,
            'Description': 200,
            'Duration': 100,
            'Created By': 120
        }

        for col, width in columns.items():
            self.template_tree.heading(col, text=col)
            self.template_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.template_tree.yview)
        self.template_tree.configure(yscrollcommand=scrollbar.set)

        self.template_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="New Template", command=self.new_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Apply Template", command=self.apply_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_templates).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_templates(self):
        """Load templates"""
        if not CLI_AVAILABLE:
            return

        for item in self.template_tree.get_children():
            self.template_tree.delete(item)

        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, accommodation_type, description, duration_days, created_by"
                    " FROM [" + TEMPLATES_TABLE + "]"
                    " ORDER BY name"
                )

                templates = cursor.fetchall()

                for template in templates:
                    self.template_tree.insert('', 'end', values=(
                        template['name'],
                        template['accommodation_type'],
                        template['description'] or 'N/A',
                        f"{template['duration_days']} days" if template['duration_days'] else 'N/A',
                        template['created_by'] or 'N/A'
                    ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")

    def new_template(self):
        """Create new template"""
        dialog = TemplateDialog(self.dialog, "New Template")
        if dialog.result:
            self.save_template(dialog.result)

    def edit_template(self):
        """Edit selected template"""
        selection = self.template_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to edit")
            return

        template_name = self.template_tree.item(selection[0])['values'][0]

        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (template_name,))
                template_data = cursor.fetchone()

            if template_data:
                dialog = TemplateDialog(self.dialog, "Edit Template", template_data)
                if dialog.result:
                    self.update_template(template_name, dialog.result)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit template: {str(e)}")

    def delete_template(self):
        """Delete selected template"""
        selection = self.template_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete")
            return

        template_name = self.template_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Delete template '{template_name}'?"):
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (template_name,))
                    conn.commit()

                messagebox.showinfo("Success", f"Template '{template_name}' deleted")
                self.load_templates()
                self.gui_parent.refresh_templates()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {str(e)}")

    def apply_template(self):
        """Apply selected template"""
        selection = self.template_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to apply")
            return

        template_name = self.template_tree.item(selection[0])['values'][0]

        student_id = simpledialog.askstring("Apply Template", "Enter Student ID:")
        if student_id:
            dialog = ApplyTemplateDialog(self.dialog)
            if dialog.result:
                dialog.result['template_name'] = template_name
                self.gui_parent.apply_template_with_data(dialog.result)

    def save_template(self, template_data):
        """Save new template"""
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user = resolve_user_identifier(auth_instance=getattr(self.gui_parent, 'auth', None))

            description = template_data.get('description')
            if description is not None and not isinstance(description, str):
                description = json.dumps(description, default=str)

            duration_days = template_data.get('duration_days')
            start_offset_days = template_data.get('start_offset_days')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO [" + TEMPLATES_TABLE + "]"
                    " (name, accommodation_type, description, start_offset_days,"
                    " duration_days, created_by, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                    template_data['name'],
                    template_data['accommodation_type'],
                    description,
                    int(start_offset_days) if start_offset_days is not None else None,
                    int(duration_days) if duration_days is not None else None,
                    user, now, now
                ))
                conn.commit()

            messagebox.showinfo("Success", f"Template '{template_data['name']}' saved")
            self.load_templates()
            self.gui_parent.refresh_templates()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")

    def update_template(self, template_name, template_data):
        """Update existing template"""
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            description = template_data.get('description')
            if description is not None and not isinstance(description, str):
                description = json.dumps(description, default=str)
            duration_days = template_data.get('duration_days')
            start_offset_days = template_data.get('start_offset_days')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE [" + TEMPLATES_TABLE + "] SET"
                    " accommodation_type = ?, description = ?, start_offset_days = ?,"
                    " duration_days = ?, updated_at = ?"
                    " WHERE name = ?", (
                    template_data['accommodation_type'],
                    description,
                    int(start_offset_days) if start_offset_days is not None else None,
                    int(duration_days) if duration_days is not None else None,
                    now,
                    template_name
                ))
                conn.commit()

            messagebox.showinfo("Success", f"Template '{template_name}' updated")
            self.load_templates()
            self.gui_parent.refresh_templates()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update template: {str(e)}")
