"""Template management methods mixin for the enhanced reporting GUI."""

from ..standalone.constants import (
    tk, ttk, filedialog, messagebox, simpledialog,
    ScrolledText,
    os, json, logging, datetime,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
    _t,
    load_templates, save_template, save_template_dict,
    delete_template_from_db as _service_delete_template_from_db,
    get_template,
    ReportTemplate,
)


class TemplatesMixin:
    """Mixin providing template management methods."""

    def load_templates(self):
        """Load templates into the GUI"""
        if not ENHANCED_AVAILABLE:
            return

        try:
            templates = load_templates()

            # Update template listbox
            self._schedule_on_ui_thread(lambda: self._update_template_listbox(templates))

            # Update template combos
            template_names = [t['name'] for t in templates]
            self._schedule_on_ui_thread(lambda: self._update_template_combos(template_names))

        except Exception as e:
            logging.error(f"Error loading templates: {str(e)}")

    def _update_template_listbox(self, templates):
        """Update template listbox in main thread"""
        self.template_listbox.delete(0, tk.END)
        self.templates_data = templates

        for template in templates:
            display_text = f"{template['name']} ({template.get('version', '1.0')})"
            self.template_listbox.insert(tk.END, display_text)

    def _update_template_combos(self, template_names):
        """Update template comboboxes in main thread"""
        self.template_combo['values'] = template_names
        self.schedule_template_combo['values'] = template_names

        if template_names:
            self.template_combo.set(template_names[0])
            self.schedule_template_combo.set(template_names[0])

    def refresh_templates(self):
        """Refresh templates list"""
        self.update_status("Refreshing templates...")
        try:
            self.load_templates()
            self.update_overview_cards()
            self.update_status("Templates refreshed successfully")
            messagebox.showinfo("Success", "Templates refreshed successfully!")
        except Exception as e:
            logging.error(f"Error refreshing templates: {e}")
            self.update_status(f"Error refreshing templates: {str(e)}", "error")
            messagebox.showerror("Error", f"Failed to refresh templates: {str(e)}")

    def import_template_dialog(self):
        """Import template from JSON file"""
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Import Template"
            )

            if file_path:
                with open(file_path, 'r') as f:
                    template_data = json.load(f)

                # Validate template structure
                required_fields = ['name', 'sections']
                if not all(field in template_data for field in required_fields):
                    messagebox.showerror("Invalid Template", "Template file is missing required fields")
                    return

                # Check if template already exists
                existing_template = get_template(template_data['name'])
                if existing_template:
                    if not messagebox.askyesno("Template Exists",
                                             f"Template '{template_data['name']}' already exists. Overwrite?"):
                        return

                # Import template
                if ENHANCED_AVAILABLE:
                    save_template_dict(template_data)

                self.refresh_data()
                messagebox.showinfo("Success", f"Template '{template_data['name']}' imported successfully!")

        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import template: {str(e)}")

    def on_template_select(self, event):
        """Handle template selection"""
        selection = self.template_listbox.curselection()
        if not selection or not hasattr(self, 'templates_data'):
            return

        template_data = self.templates_data[selection[0]]
        self.display_template_details(template_data)

    def display_template_details(self, template_data):
        """Display template details in the text widget"""
        self.template_details.delete(1.0, tk.END)

        details = f"""Template Details:

Name: {template_data['name']}
Description: {template_data.get('description', 'No description')}
Version: {template_data.get('version', '1.0')}
Created: {template_data.get('created_at', 'Unknown')}
Security Level: {template_data.get('security_level', 'normal').title()}
Visualization Type: {template_data.get('visualization_type', 'standard').title()}

Sections ({len(template_data.get('sections', []))} total):
"""

        for section in template_data.get('sections', []):
            details += f"  • {section.replace('_', ' ').title()}\n"

        if template_data.get('filters'):
            details += f"\nFilters:\n"
            for key, value in template_data['filters'].items():
                details += f"  • {key}: {value}\n"

        self.template_details.insert(1.0, details)

    def create_template_dialog(self):
        """Open template creation dialog"""
        from ..core import TemplateDialog
        dialog = TemplateDialog(self.root, title="Create New Template")
        if dialog.result:
            self.refresh_data()

    def edit_template_dialog(self):
        """Open template editing dialog"""
        from ..core import TemplateDialog
        selection = self.template_listbox.curselection()
        if not selection or not hasattr(self, 'templates_data'):
            messagebox.showwarning("No Selection", "Please select a template to edit.")
            return

        template_data = self.templates_data[selection[0]]
        dialog = TemplateDialog(self.root, title="Edit Template", template_data=template_data)
        if dialog.result:
            self.refresh_data()

    def delete_template(self):
        """Delete selected template"""
        selection = self.template_listbox.curselection()
        if not selection or not hasattr(self, 'templates_data'):
            messagebox.showwarning("No Selection", "Please select a template to delete.")
            return

        template_data = self.templates_data[selection[0]]

        if messagebox.askyesno("Confirm Delete",
                              f"Are you sure you want to delete template '{template_data['name']}'?"):
            try:
                if ENHANCED_AVAILABLE:
                    _service_delete_template_from_db(template_data['name'])

                self.refresh_data()
                messagebox.showinfo("Success", "Template deleted successfully!")

            except Exception as e:
                logging.error(f"Failed to delete template: {e}")
                messagebox.showerror("Error", f"Failed to delete template: {str(e)}")

    def export_template(self):
        """Export selected template"""
        selection = self.template_listbox.curselection()
        if not selection or not hasattr(self, 'templates_data'):
            messagebox.showwarning("No Selection", "Please select a template to export.")
            return

        template_data = self.templates_data[selection[0]]

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{template_data['name']}_template.json"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(template_data, f, indent=4)
                messagebox.showinfo("Success", f"Template exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export template: {str(e)}")

    def duplicate_template(self):
        """Duplicate selected template"""
        selection = self.template_listbox.curselection()
        if not selection or not hasattr(self, 'templates_data'):
            messagebox.showwarning("No Selection", "Please select a template to duplicate.")
            return

        template_data = self.templates_data[selection[0]].copy()

        # Get new name
        new_name = simpledialog.askstring("Duplicate Template",
                                         "Enter name for duplicated template:",
                                         initialvalue=f"{template_data['name']} Copy")

        if new_name:
            template_data['name'] = new_name
            template_data['created_at'] = datetime.now().isoformat()
            template_data['version'] = "1.0"

            try:
                if ENHANCED_AVAILABLE:
                    save_template_dict(template_data)

                self.refresh_data()
                messagebox.showinfo("Success", "Template duplicated successfully!")

            except Exception as e:
                logging.error(f"Failed to duplicate template: {e}")
                messagebox.showerror("Error", f"Failed to duplicate template: {str(e)}")

    def preview_template(self):
        """Preview selected template"""
        selection = self.template_listbox.curselection()
        if not selection or not hasattr(self, 'templates_data'):
            messagebox.showwarning("No Selection", "Please select a template to preview.")
            return

        template_data = self.templates_data[selection[0]]

        # Create preview window
        preview_window = tk.Toplevel(self.root)
        preview_window.title(f"Template Preview: {template_data['name']}")
        preview_window.geometry("600x500")

        preview_text = ScrolledText(preview_window, wrap=tk.WORD)
        preview_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Generate preview content
        preview_content = f"""Template Preview: {template_data['name']}

This template will generate a report containing the following sections:

"""

        for i, section in enumerate(template_data.get('sections', []), 1):
            section_name = section.replace('_', ' ').title()
            preview_content += f"{i}. {section_name}\n"

            # Add section description
            section_descriptions = {
                'student_overview': '   Overview of total students, courses, and key metrics',
                'course_distribution': '   Distribution of students across different courses',
                'gender_distribution': '   Breakdown of students by gender',
                'age_distribution': '   Age demographics of student population',
                'registration_trends': '   Student registration patterns over time',
                'module_popularity': '   Most popular modules among students',
                'grade_distribution': '   Distribution of student grades',
                'attendance_summary': '   Student attendance statistics',
                'data_quality_report': '   Assessment of data completeness and accuracy',
                'predictive_analytics': '   AI-powered insights and predictions',
                'correlation_analysis': '   Statistical relationships between variables',
                'anomaly_detection': '   Identification of unusual patterns'
            }

            if section in section_descriptions:
                preview_content += f"{section_descriptions[section]}\n"
            preview_content += "\n"

        if template_data.get('filters'):
            preview_content += "Applied Filters:\n"
            for key, value in template_data['filters'].items():
                preview_content += f"  • {key}: {value}\n"

        preview_content += f"""
Report Configuration:
  • Security Level: {template_data.get('security_level', 'normal').title()}
  • Visualization Type: {template_data.get('visualization_type', 'standard').title()}
  • Template Version: {template_data.get('version', '1.0')}
"""

        preview_text.insert(1.0, preview_content)
        preview_text.config(state=tk.DISABLED)

    def save_template_method(self, template):
        """Save a report template to database (GUI wrapper)"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return False

            save_template(template)
            self.update_status(f"Template '{template.name}' saved successfully", "success")
            self.refresh_data()
            return True
        except Exception as e:
            logging.error(f"Error saving template: {e}")
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")
            return False

    def save_template_dict_method(self, template_data):
        """Save template dictionary to database (GUI wrapper)"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return False

            save_template_dict(template_data)
            self.update_status(f"Template '{template_data.get('name')}' saved successfully", "success")
            self.refresh_data()
            return True
        except Exception as e:
            logging.error(f"Error saving template: {e}")
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")
            return False

    def view_templates_menu(self):
        """View and manage templates"""
        try:
            # This will open the existing templates dialog
            self.show_templates_dialog()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show templates: {str(e)}")

    def to_dict_report_template(self, template):
        """Convert report template to dictionary"""
        try:
            return {
                'name': getattr(template, 'name', ''),
                'description': getattr(template, 'description', ''),
                'sections': getattr(template, 'sections', []),
                'format': getattr(template, 'format', 'pdf'),
                'version': getattr(template, 'version', '1.0'),
                'created_at': getattr(template, 'created_at', datetime.now().isoformat())
            }
        except Exception as e:
            logging.error(f"Error converting template to dict: {str(e)}")
            return {}

    def create_advanced_template_menu(self):
        """Show advanced template creation dialog"""
        try:
            self.create_template()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create template: {str(e)}")

    def delete_template_from_db(self, template_name):
        """Delete template from database"""
        try:
            if not ENHANCED_AVAILABLE:
                return False

            _service_delete_template_from_db(template_name)
            self.update_status(f"Template '{template_name}' deleted", "success")
            self.refresh_data()
            return True
        except Exception as e:
            logging.error(f"Error deleting template: {str(e)}")
            messagebox.showerror("Error", f"Failed to delete template: {str(e)}")
            return False

    def delete_template_menu(self):
        """Show delete template dialog"""
        try:
            templates = load_templates()
            if not templates:
                messagebox.showinfo("No Templates", "No templates available to delete")
                return

            # Create selection dialog
            delete_window = tk.Toplevel(self.root)
            delete_window.title("Delete Template")
            delete_window.geometry("500x400")
            delete_window.transient(self.root)

            ttk.Label(delete_window, text="Select Template to Delete",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Listbox for templates
            listbox_frame = ttk.Frame(delete_window)
            listbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            scrollbar = ttk.Scrollbar(listbox_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            template_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
            template_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=template_listbox.yview)

            for template in templates:
                template_listbox.insert(tk.END, template.get('name', 'Unnamed'))

            def delete_selected():
                selection = template_listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a template to delete")
                    return

                template_name = template_listbox.get(selection[0])
                if messagebox.askyesno("Confirm Delete", f"Delete template '{template_name}'?"):
                    if self.delete_template_from_db(template_name):
                        messagebox.showinfo("Success", "Template deleted successfully")
                        delete_window.destroy()

            # Buttons
            button_frame = ttk.Frame(delete_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Delete", command=delete_selected).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=delete_window.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show delete dialog: {str(e)}")
