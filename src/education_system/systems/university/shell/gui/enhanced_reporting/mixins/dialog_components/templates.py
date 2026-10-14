"""Templates dialogs extracted from DialogsMixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ._shared import *  # noqa: F401,F403


class TemplateDialogsMixin:
    def show_advanced_template_creation_dialog(self):
        """Show advanced template creation dialog matching CLI functionality"""
        try:
            template_window = tk.Toplevel(self.root)
            template_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.windows.advanced_template_creation', default="Advanced Template Creation"))
            template_window.geometry("800x700")
            template_window.transient(self.root)

            # Create notebook for different template aspects
            template_notebook = ttk.Notebook(template_window)
            template_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Basic Info Tab
            basic_frame = ttk.Frame(template_notebook)
            template_notebook.add(basic_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.tabs.basic_info', default="Basic Info"))

            basic_info_frame = ttk.LabelFrame(basic_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.template_information', default="Template Information"), padding="10")
            basic_info_frame.pack(fill=tk.X, padx=10, pady=10)
            basic_info_frame.columnconfigure(1, weight=1)

            ttk.Label(basic_info_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.name', default="Name:*")).grid(row=0, column=0, sticky=tk.W, pady=5)
            name_var = tk.StringVar()
            ttk.Entry(basic_info_frame, textvariable=name_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            ttk.Label(basic_info_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.description', default="Description:")).grid(row=1, column=0, sticky=tk.W, pady=5)
            desc_var = tk.StringVar()
            ttk.Entry(basic_info_frame, textvariable=desc_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Security and Visualization
            security_frame = ttk.LabelFrame(basic_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.security_visualization', default="Security & Visualization"), padding="10")
            security_frame.pack(fill=tk.X, padx=10, pady=10)
            security_frame.columnconfigure(1, weight=1)

            ttk.Label(security_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.security_level', default="Security Level:")).grid(row=0, column=0, sticky=tk.W, pady=5)
            security_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.values.normal', default="normal"))
            security_combo = ttk.Combobox(security_frame, textvariable=security_var,
                                         values=["normal", "confidential", "restricted"], state="readonly")
            security_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            ttk.Label(security_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.visualization_type', default="Visualization Type:")).grid(row=1, column=0, sticky=tk.W, pady=5)
            viz_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.values.standard', default="standard"))
            viz_combo = ttk.Combobox(security_frame, textvariable=viz_var,
                                    values=["standard", "advanced", "interactive"], state="readonly")
            viz_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Sections Tab
            sections_frame = ttk.Frame(template_notebook)
            template_notebook.add(sections_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.tabs.sections', default="Sections"))

            sections_info = ttk.LabelFrame(sections_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.available_report_sections', default="Available Report Sections"), padding="10")
            sections_info.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Create checkboxes for all available sections
            section_vars = {}
            available_sections = [
                "student_overview", "course_distribution", "gender_distribution",
                "age_distribution", "module_popularity", "registration_trends",
                "grade_distribution", "attendance_summary", "data_quality_report",
                "predictive_analytics", "correlation_analysis", "anomaly_detection",
                "performance_benchmarks", "trend_analysis"
            ]

            # Create scrollable frame for sections
            canvas = tk.Canvas(sections_info)
            scrollbar = ttk.Scrollbar(sections_info, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            for i, section in enumerate(available_sections):
                var = tk.BooleanVar()
                section_vars[section] = var
                section_name = section.replace('_', ' ').title()
                ttk.Checkbutton(scrollable_frame, text=section_name, variable=var).grid(
                    row=i // 2, column=i % 2, sticky=tk.W, padx=10, pady=2)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Filters Tab
            filters_frame = ttk.Frame(template_notebook)
            template_notebook.add(filters_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.tabs.filters', default="Filters"))

            filters_info = ttk.LabelFrame(filters_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.data_filters', default="Data Filters"), padding="10")
            filters_info.pack(fill=tk.X, padx=10, pady=10)
            filters_info.columnconfigure(1, weight=1)

            ttk.Label(filters_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.course_filter', default="Course Filter:")).grid(row=0, column=0, sticky=tk.W, pady=5)
            course_var = tk.StringVar()
            course_combo = ttk.Combobox(filters_info, textvariable=course_var,
                                       values=["", "CS", "DS"], state="readonly")
            course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            ttk.Label(filters_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.date_range_days', default="Date Range (days):")).grid(row=1, column=0, sticky=tk.W, pady=5)
            date_range_var = tk.StringVar(value="30")
            ttk.Entry(filters_info, textvariable=date_range_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

            # Advanced Tab
            advanced_frame = ttk.Frame(template_notebook)
            template_notebook.add(advanced_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.tabs.advanced', default="Advanced"))

            advanced_info = ttk.LabelFrame(advanced_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.advanced_options', default="Advanced Options"), padding="10")
            advanced_info.pack(fill=tk.X, padx=10, pady=10)

            enable_caching_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(advanced_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.buttons.enable_caching_for_faster_generation', default="Enable caching for faster generation"),
                           variable=enable_caching_var).pack(anchor=tk.W, pady=2)

            enable_comparison_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(advanced_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.buttons.include_period_over_period_comparison', default="Include period-over-period comparison"),
                           variable=enable_comparison_var).pack(anchor=tk.W, pady=2)

            enable_export_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(advanced_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.buttons.allow_multiple_export_formats', default="Allow multiple export formats"),
                           variable=enable_export_var).pack(anchor=tk.W, pady=2)

            def create_advanced_template():
                try:
                    name = name_var.get().strip()
                    if not name:
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.validation_error', default="Validation Error"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.template_name_is_required', default="Template name is required"))
                        return

                    if get_template(name):
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.template_exists', default="Template Exists"), f"Template '{name}' already exists")
                        return

                    # Get selected sections
                    selected_sections = [section for section, var in section_vars.items() if var.get()]
                    if not selected_sections:
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.validation_error', default="Validation Error"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.at_least_one_section_must_be_selected', default="At least one section must be selected"))
                        return

                    # Build filters
                    filters = {}
                    if course_var.get():
                        filters['course'] = course_var.get()

                    try:
                        date_range = int(date_range_var.get())
                        if date_range > 0:
                            filters['date_range_days'] = date_range
                    except ValueError:
                        pass

                    # Build advanced options
                    advanced_options = {
                        'enable_caching': enable_caching_var.get(),
                        'enable_comparison': enable_comparison_var.get(),
                        'enable_export': enable_export_var.get()
                    }

                    # Create template
                    template_data = {
                        'name': name,
                        'description': desc_var.get().strip(),
                        'sections': selected_sections,
                        'filters': filters,
                        'security_level': security_var.get(),
                        'visualization_type': viz_var.get(),
                        'advanced_options': advanced_options,
                        'created_at': datetime.now().isoformat(),
                        'version': '1.0'
                    }

                    if ENHANCED_AVAILABLE:
                        templates = load_templates()
                        templates.append(template_data)

                        os.makedirs(CONFIG.get('templates_dir', str(paths.UNIVERSITY_REPORT_TEMPLATES_DIR)), exist_ok=True)
                        with open(os.path.join(CONFIG.get('templates_dir', str(paths.UNIVERSITY_REPORT_TEMPLATES_DIR)), "templates.json"), 'w') as f:
                            json.dump(templates, f, indent=4)

                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.success', default="Success"), f"Advanced template '{name}' created successfully!")
                    template_window.destroy()
                    self.refresh_data()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.error', default="Error"), f"Failed to create template: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(template_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.buttons.create_template', default="Create Template"), command=create_advanced_template,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.buttons.cancel', default="Cancel"), command=template_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.template_creation_error', default="Template Creation Error"), f"Failed to open template creation dialog: {str(e)}")

    def show_template_comparison_dialog(self):
        """Compare multiple templates side by side"""
        try:
            compare_window = tk.Toplevel(self.root)
            compare_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.windows.template_comparison', default="Template Comparison"))
            compare_window.geometry("900x600")
            compare_window.transient(self.root)

            templates = load_templates() if ENHANCED_AVAILABLE else []
            if len(templates) < 2:
                messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.insufficient_templates', default="Insufficient Templates"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.need_at_least_2_templates_to_compare', default="Need at least 2 templates to compare"))
                compare_window.destroy()
                return

            # Template selection frame
            selection_frame = ttk.LabelFrame(compare_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.select_templates_to_compare', default="Select Templates to Compare"), padding="10")
            selection_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(selection_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.template_1', default="Template 1:")).pack(side=tk.LEFT)
            template1_var = tk.StringVar()
            template1_combo = ttk.Combobox(selection_frame, textvariable=template1_var,
                                          values=[t['name'] for t in templates], state="readonly")
            template1_combo.pack(side=tk.LEFT, padx=(5, 20))

            ttk.Label(selection_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.template_2', default="Template 2:")).pack(side=tk.LEFT)
            template2_var = tk.StringVar()
            template2_combo = ttk.Combobox(selection_frame, textvariable=template2_var,
                                          values=[t['name'] for t in templates], state="readonly")
            template2_combo.pack(side=tk.LEFT, padx=5)

            # Comparison display
            comparison_frame = ttk.LabelFrame(compare_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.comparison_results', default="Comparison Results"), padding="10")
            comparison_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            comparison_text = ScrolledText(comparison_frame, wrap=tk.WORD)
            comparison_text.pack(fill=tk.BOTH, expand=True)

            def compare_templates():
                name1 = template1_var.get()
                name2 = template2_var.get()

                if not name1 or not name2:
                    messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.selection_required', default="Selection Required"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.please_select_both_templates', default="Please select both templates"))
                    return

                if name1 == name2:
                    messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.same_template', default="Same Template"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.please_select_different_templates', default="Please select different templates"))
                    return

                template1 = next((t for t in templates if t['name'] == name1), None)
                template2 = next((t for t in templates if t['name'] == name2), None)

                comparison = f"Template Comparison: {name1} vs {name2}\n"
                comparison += "=" * 60 + "\n\n"

                # Compare basic properties
                comparison += "BASIC PROPERTIES:\n"
                comparison += f"Name: {template1['name']} | {template2['name']}\n"
                comparison += f"Description: {template1.get('description', 'None')} | {template2.get('description', 'None')}\n"
                comparison += f"Security Level: {template1.get('security_level', 'normal')} | {template2.get('security_level', 'normal')}\n"
                comparison += f"Visualization: {template1.get('visualization_type', 'standard')} | {template2.get('visualization_type', 'standard')}\n"
                comparison += f"Version: {template1.get('version', '1.0')} | {template2.get('version', '1.0')}\n\n"

                # Compare sections
                sections1 = set(template1.get('sections', []))
                sections2 = set(template2.get('sections', []))

                comparison += "SECTIONS COMPARISON:\n"
                comparison += f"Total Sections: {len(sections1)} | {len(sections2)}\n"

                common_sections = sections1.intersection(sections2)
                only_in_1 = sections1 - sections2
                only_in_2 = sections2 - sections1

                if common_sections:
                    comparison += f"Common Sections ({len(common_sections)}): {', '.join(sorted(common_sections))}\n"
                if only_in_1:
                    comparison += f"Only in {name1}: {', '.join(sorted(only_in_1))}\n"
                if only_in_2:
                    comparison += f"Only in {name2}: {', '.join(sorted(only_in_2))}\n"

                # Compare filters
                filters1 = template1.get('filters', {})
                filters2 = template2.get('filters', {})

                comparison += "\nFILTERS:\n"
                comparison += f"{name1}: {filters1 if filters1 else 'None'}\n"
                comparison += f"{name2}: {filters2 if filters2 else 'None'}\n"

                comparison_text.delete(1.0, tk.END)
                comparison_text.insert(1.0, comparison)

            ttk.Button(selection_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.buttons.compare', default="Compare"), command=compare_templates).pack(side=tk.RIGHT, padx=(20, 0))

            ttk.Button(compare_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.buttons.close', default="Close"), command=compare_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.comparison_error', default="Comparison Error"), f"Failed to open comparison dialog: {str(e)}")

    def show_template_versioning_dialog(self):
        """Show template version history and management"""
        try:
            version_window = tk.Toplevel(self.root)
            version_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.windows.template_version_management', default="Template Version Management"))
            version_window.geometry("700x500")
            version_window.transient(self.root)

            # Template selection
            selection_frame = ttk.LabelFrame(version_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.select_template', default="Select Template"), padding="10")
            selection_frame.pack(fill=tk.X, padx=10, pady=10)

            templates = load_templates() if ENHANCED_AVAILABLE else []
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(selection_frame, textvariable=template_var,
                                         values=[t['name'] for t in templates], state="readonly")
            template_combo.pack(fill=tk.X)

            # Version history display
            history_frame = ttk.LabelFrame(version_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.labels.version_history', default="Version History"), padding="10")
            history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            history_text = ScrolledText(history_frame, wrap=tk.WORD)
            history_text.pack(fill=tk.BOTH, expand=True)

            def show_version_info():
                template_name = template_var.get()
                if not template_name:
                    return

                template = next((t for t in templates if t['name'] == template_name), None)
                if not template:
                    return

                version_info = f"Version Information for: {template_name}\n"
                version_info += "=" * 50 + "\n\n"
                version_info += f"Current Version: {template.get('version', '1.0')}\n"
                version_info += f"Created: {template.get('created_at', 'Unknown')}\n"
                version_info += f"Last Modified: {template.get('modified_at', 'Unknown')}\n\n"

                version_info += "Template Details:\n"
                version_info += f"- Sections: {len(template.get('sections', []))}\n"
                version_info += f"- Security Level: {template.get('security_level', 'normal')}\n"
                version_info += f"- Visualization Type: {template.get('visualization_type', 'standard')}\n"
                version_info += f"- Filters Applied: {len(template.get('filters', {}))}\n"

                history_text.delete(1.0, tk.END)
                history_text.insert(1.0, version_info)

            template_combo.bind('<<ComboboxSelected>>', lambda e: show_version_info())

            ttk.Button(version_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.buttons.close', default="Close"), command=version_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.templates.dialogs.version_error', default="Version Error"), f"Failed to open version dialog: {str(e)}")
