"""Standalone dialog classes for the Student Analytics GUI."""
from education_system.systems.university.interfaces.gui.shell.student_analytics._imports import (
    tk, ttk, messagebox, datetime, _t, CONFIG,
)


class FilterDialog:
    """Advanced filters dialog"""

    def __init__(self, parent, analytics):
        self.analytics = analytics
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("analytics.dialogs.advanced_filters"))
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_filter_interface()

    def create_filter_interface(self):
        """Create the filter interface"""
        # Age range
        age_frame = ttk.LabelFrame(self.dialog, text=_t("analytics.filters.age_range"), padding=10)
        age_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(age_frame, text=_t("analytics.filters.min_age")).grid(row=0, column=0, sticky='w')
        self.min_age = ttk.Entry(age_frame, width=10)
        self.min_age.grid(row=0, column=1, padx=5)

        ttk.Label(age_frame, text=_t("analytics.filters.max_age")).grid(row=0, column=2, sticky='w', padx=(20,0))
        self.max_age = ttk.Entry(age_frame, width=10)
        self.max_age.grid(row=0, column=3, padx=5)

        # GPA range
        gpa_frame = ttk.LabelFrame(self.dialog, text=_t("analytics.filters.gpa_range"), padding=10)
        gpa_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(gpa_frame, text=_t("analytics.filters.min_gpa")).grid(row=0, column=0, sticky='w')
        self.min_gpa = ttk.Entry(gpa_frame, width=10)
        self.min_gpa.grid(row=0, column=1, padx=5)

        ttk.Label(gpa_frame, text=_t("analytics.filters.max_gpa")).grid(row=0, column=2, sticky='w', padx=(20,0))
        self.max_gpa = ttk.Entry(gpa_frame, width=10)
        self.max_gpa.grid(row=0, column=3, padx=5)

        # Course selection
        course_frame = ttk.LabelFrame(self.dialog, text=_t("analytics.filters.course_selection"), padding=10)
        course_frame.pack(fill='x', padx=10, pady=5)

        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(course_frame, textvariable=self.course_var)
        self.course_combo.pack(fill='x')

        # Load courses
        try:
            students_df = self.analytics.get_all_students()
            courses = [_t("analytics.filters.all_courses")] + list(students_df['course'].unique())
            self.course_combo['values'] = courses
            self.course_combo.set(_t("analytics.filters.all_courses"))
        except Exception:
            self.course_combo['values'] = [_t("analytics.filters.all_courses")]
            self.course_combo.set(_t("analytics.filters.all_courses"))

        # Gender selection
        gender_frame = ttk.LabelFrame(self.dialog, text=_t("analytics.filters.gender"), padding=10)
        gender_frame.pack(fill='x', padx=10, pady=5)

        self.gender_var = tk.StringVar()
        self.gender_combo = ttk.Combobox(gender_frame, textvariable=self.gender_var)
        self.gender_combo['values'] = [_t("common.all"), _t("common.male"), _t("common.female"), _t("common.other")]
        self.gender_combo.set(_t("common.all"))
        self.gender_combo.pack(fill='x')

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill='x', padx=10, pady=20)

        ttk.Button(button_frame, text=_t("analytics.btn.apply_filters"),
                  command=self.apply_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("common.clear_all"),
                  command=self.clear_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"),
                  command=self.dialog.destroy).pack(side='right', padx=5)

    def apply_filters(self):
        """Apply the selected filters"""
        filters = {}

        # Age range
        if self.min_age.get() and self.max_age.get():
            try:
                min_age = int(self.min_age.get())
                max_age = int(self.max_age.get())
                filters['age_range'] = [min_age, max_age]
            except ValueError:
                messagebox.showerror(_t("analytics.dialogs.invalid_input"),
                                    _t("analytics.error.invalid_age_values"))
                return

        # GPA range
        if self.min_gpa.get() and self.max_gpa.get():
            try:
                min_gpa = float(self.min_gpa.get())
                max_gpa = float(self.max_gpa.get())
                filters['gpa_range'] = [min_gpa, max_gpa]
            except ValueError:
                messagebox.showerror(_t("analytics.dialogs.invalid_input"),
                                    _t("analytics.error.invalid_gpa_values"))
                return

        # Course selection
        if self.course_var.get() != _t("analytics.filters.all_courses"):
            filters['course'] = self.course_var.get()

        # Gender selection
        if self.gender_var.get() != _t("common.all"):
            filters['gender'] = self.gender_var.get()

        # Apply filters to analytics
        self.analytics.custom_filters.update(filters)

        messagebox.showinfo(_t("analytics.dialogs.filters_applied"),
                           _t("analytics.messages.filters_applied", count=len(filters)))
        self.dialog.destroy()

    def clear_filters(self):
        """Clear all filter inputs"""
        self.min_age.delete(0, 'end')
        self.max_age.delete(0, 'end')
        self.min_gpa.delete(0, 'end')
        self.max_gpa.delete(0, 'end')
        self.course_combo.set('All Courses')
        self.gender_combo.set('All')


class CustomReportDialog:
    """Custom report builder dialog"""

    def __init__(self, parent, analytics):
        self.analytics = analytics
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("analytics.dialogs.custom_report"))
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.selected_components = []
        self.create_report_interface()

    def create_report_interface(self):
        """Create the custom report interface"""
        # Title
        title_label = ttk.Label(self.dialog, text=_t("analytics.dialogs.custom_report"),
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Report name
        name_frame = ttk.Frame(self.dialog)
        name_frame.pack(fill='x', padx=20, pady=5)

        ttk.Label(name_frame, text=_t("analytics.labels.report_name")).pack(side='left')
        self.report_name = ttk.Entry(name_frame, width=30)
        self.report_name.pack(side='left', padx=10)
        self.report_name.insert(0, f"Custom_Report_{datetime.now().strftime('%Y%m%d')}")

        # Component selection
        components_frame = ttk.LabelFrame(self.dialog, text=_t("analytics.labels.select_components"), padding=10)
        components_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Create scrollable frame for components
        canvas = tk.Canvas(components_frame)
        scrollbar = ttk.Scrollbar(components_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Component checkboxes
        self.component_vars = {}
        components = [
            ('demographics', _t("analytics.components.demographics"), _t("analytics.components.demographics_desc")),
            ('grades', _t("analytics.components.grades"), _t("analytics.components.grades_desc")),
            ('modules', _t("analytics.components.modules"), _t("analytics.components.modules_desc")),
            ('trends', _t("analytics.components.trends"), _t("analytics.components.trends_desc")),
            ('engagement', _t("analytics.components.engagement"), _t("analytics.components.engagement_desc")),
            ('risk', _t("analytics.components.risk"), _t("analytics.components.risk_desc")),
            ('cohorts', _t("analytics.components.cohorts"), _t("analytics.components.cohorts_desc")),
            ('correlations', _t("analytics.components.correlations"), _t("analytics.components.correlations_desc"))
        ]

        for i, (key, title, description) in enumerate(components):
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', pady=2)

            var = tk.BooleanVar()
            self.component_vars[key] = var

            cb = ttk.Checkbutton(frame, text=title, variable=var)
            cb.pack(side='left')

            desc_label = ttk.Label(frame, text=f"- {description}", foreground='gray')
            desc_label.pack(side='left', padx=10)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Options
        options_frame = ttk.LabelFrame(self.dialog, text=_t("analytics.labels.report_options"), padding=10)
        options_frame.pack(fill='x', padx=20, pady=5)

        self.include_summary = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text=_t("analytics.labels.include_summary"),
                       variable=self.include_summary).pack(anchor='w')

        self.include_recommendations = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text=_t("analytics.labels.include_recommendations"),
                       variable=self.include_recommendations).pack(anchor='w')

        # Format selection
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill='x', pady=5)

        ttk.Label(format_frame, text=_t("analytics.labels.output_format")).pack(side='left')
        self.format_var = tk.StringVar(value='PDF')
        format_combo = ttk.Combobox(format_frame, textvariable=self.format_var,
                                   values=['PDF', 'HTML', 'Word'], state='readonly')
        format_combo.pack(side='left', padx=10)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill='x', padx=20, pady=20)

        ttk.Button(button_frame, text=_t("analytics.btn.generate_report"),
                  command=self.generate_report).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("common.select_all"),
                  command=self.select_all).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("common.clear_all"),
                  command=self.clear_all).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"),
                  command=self.dialog.destroy).pack(side='right', padx=5)

    def select_all(self):
        """Select all components"""
        for var in self.component_vars.values():
            var.set(True)

    def clear_all(self):
        """Clear all component selections"""
        for var in self.component_vars.values():
            var.set(False)

    def generate_report(self):
        """Generate the custom report"""
        # Get selected components
        selected = [key for key, var in self.component_vars.items() if var.get()]

        if not selected:
            messagebox.showwarning(_t("analytics.dialogs.no_components"),
                                 _t("analytics.error.select_component"))
            return

        report_name = self.report_name.get()
        if not report_name:
            messagebox.showwarning(_t("analytics.dialogs.no_report_name"),
                                  _t("analytics.error.enter_report_name"))
            return

        # Close dialog and generate report
        self.dialog.destroy()

        # Start report generation in thread
        def generate():
            try:
                print(f"\nGenerating custom report: {report_name}")
                print(f"Selected components: {', '.join(selected)}")
                print(f"Include summary: {self.include_summary.get()}")
                print(f"Format: {self.format_var.get()}")

                # Generate selected analyses
                analysis_map = {
                    'demographics': self.analytics.analyze_student_demographics,
                    'grades': self.analytics.analyze_grade_distribution,
                    'modules': self.analytics.analyze_module_popularity,
                    'trends': self.analytics.analyze_performance_trends,
                    'engagement': self.analytics.analyze_engagement,
                    'risk': self.analytics.analyze_academic_risk,
                    'cohorts': self.analytics.analyze_cohorts,
                    'correlations': self.analytics.analyze_correlations
                }

                for component in selected:
                    if component in analysis_map:
                        print(f"\nGenerating {component}...")
                        analysis_map[component]()

                print(f"\nCustom report '{report_name}' generated successfully!")

                # Show completion message in main thread
                messagebox.showinfo(_t("analytics.dialogs.report_generated"),
                                   _t("analytics.messages.report_generated", name=report_name))

            except Exception as e:
                import traceback
                error_msg = f"{_t('analytics.error.generate_report', error=str(e))}\n\n{traceback.format_exc()}"
                print(error_msg)
                messagebox.showerror(_t("analytics.dialogs.report_error"), error_msg)

        # Run in main thread instead of daemon thread
        generate()


class ConfigDialog:
    """Configuration settings dialog"""

    def __init__(self, parent, analytics):
        self.analytics = analytics
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("analytics.dialogs.configuration"))
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_config_interface()

    def create_config_interface(self):
        """Create the configuration interface"""
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # General settings tab
        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text=_t("analytics.tabs.general"))

        # Plot settings
        plot_frame = ttk.LabelFrame(general_tab, text=_t("analytics.labels.plot_settings"), padding=10)
        plot_frame.pack(fill='x', pady=5)

        ttk.Label(plot_frame, text=_t("analytics.labels.figure_width")).grid(row=0, column=0, sticky='w')
        self.fig_width = ttk.Entry(plot_frame, width=10)
        self.fig_width.grid(row=0, column=1, padx=5)
        self.fig_width.insert(0, str(CONFIG['figure_size'][0]))

        ttk.Label(plot_frame, text=_t("analytics.labels.figure_height")).grid(row=0, column=2, sticky='w', padx=(20,0))
        self.fig_height = ttk.Entry(plot_frame, width=10)
        self.fig_height.grid(row=0, column=3, padx=5)
        self.fig_height.insert(0, str(CONFIG['figure_size'][1]))

        ttk.Label(plot_frame, text=_t("analytics.labels.dpi")).grid(row=1, column=0, sticky='w', pady=5)
        self.dpi = ttk.Entry(plot_frame, width=10)
        self.dpi.grid(row=1, column=1, padx=5, pady=5)
        self.dpi.insert(0, str(CONFIG['dpi']))

        # Export settings
        export_frame = ttk.LabelFrame(general_tab, text=_t("analytics.labels.export_settings"), padding=10)
        export_frame.pack(fill='x', pady=5)

        ttk.Label(export_frame, text=_t("analytics.labels.default_export_formats")).pack(anchor='w')

        self.format_vars = {}
        formats = ['png', 'pdf', 'svg', 'excel']
        for fmt in formats:
            var = tk.BooleanVar(value=fmt in CONFIG['export_formats'])
            self.format_vars[fmt] = var
            ttk.Checkbutton(export_frame, text=fmt.upper(), variable=var).pack(anchor='w')

        # Email settings tab
        email_tab = ttk.Frame(notebook)
        notebook.add(email_tab, text=_t("common.email"))

        email_frame = ttk.LabelFrame(email_tab, text=_t("analytics.labels.email_configuration"), padding=10)
        email_frame.pack(fill='both', expand=True, pady=5)

        ttk.Label(email_frame, text=_t("analytics.labels.sender_email")).grid(row=0, column=0, sticky='w', pady=5)
        self.sender_email = ttk.Entry(email_frame, width=30)
        self.sender_email.grid(row=0, column=1, padx=5, pady=5)
        self.sender_email.insert(0, CONFIG['email_config']['sender_email'])

        ttk.Label(email_frame, text=_t("analytics.labels.smtp_server")).grid(row=1, column=0, sticky='w', pady=5)
        self.smtp_server = ttk.Entry(email_frame, width=30)
        self.smtp_server.grid(row=1, column=1, padx=5, pady=5)
        self.smtp_server.insert(0, CONFIG['email_config']['smtp_server'])

        ttk.Label(email_frame, text=_t("analytics.labels.smtp_port")).grid(row=2, column=0, sticky='w', pady=5)
        self.smtp_port = ttk.Entry(email_frame, width=30)
        self.smtp_port.grid(row=2, column=1, padx=5, pady=5)
        self.smtp_port.insert(0, str(CONFIG['email_config']['smtp_port']))

        ttk.Label(email_frame, text=_t("common.password")).grid(row=3, column=0, sticky='w', pady=5)
        self.password = ttk.Entry(email_frame, width=30, show='*')
        self.password.grid(row=3, column=1, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text=_t("common.save_settings"),
                  command=self.save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("analytics.btn.reset_defaults"),
                  command=self.reset_defaults).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"),
                  command=self.dialog.destroy).pack(side='right', padx=5)

    def save_settings(self):
        """Save the configuration settings"""
        try:
            # Update plot settings
            CONFIG['figure_size'] = (int(self.fig_width.get()), int(self.fig_height.get()))
            CONFIG['dpi'] = int(self.dpi.get())

            # Update export formats
            CONFIG['export_formats'] = [fmt for fmt, var in self.format_vars.items() if var.get()]

            # Update email settings
            CONFIG['email_config']['sender_email'] = self.sender_email.get()
            CONFIG['email_config']['smtp_server'] = self.smtp_server.get()
            CONFIG['email_config']['smtp_port'] = int(self.smtp_port.get())
            if self.password.get():
                CONFIG['email_config']['sender_password'] = self.password.get()

            messagebox.showinfo(_t("analytics.dialogs.settings_saved"),
                               _t("analytics.messages.settings_saved"))
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("analytics.dialogs.invalid_input"),
                                _t("analytics.error.check_input_values"))
        except Exception as e:
            messagebox.showerror(_t("common.error"),
                                _t("analytics.error.save_settings", error=str(e)))

    def reset_defaults(self):
        """Reset settings to defaults"""
        # Reset plot settings
        self.fig_width.delete(0, 'end')
        self.fig_width.insert(0, '15')
        self.fig_height.delete(0, 'end')
        self.fig_height.insert(0, '10')
        self.dpi.delete(0, 'end')
        self.dpi.insert(0, '300')

        # Reset export formats
        default_formats = ['png', 'pdf', 'svg', 'excel']
        for fmt, var in self.format_vars.items():
            var.set(fmt in default_formats)

        # Reset email settings
        self.sender_email.delete(0, 'end')
        self.smtp_server.delete(0, 'end')
        self.smtp_server.insert(0, 'smtp.gmail.com')
        self.smtp_port.delete(0, 'end')
        self.smtp_port.insert(0, '587')
        self.password.delete(0, 'end')
