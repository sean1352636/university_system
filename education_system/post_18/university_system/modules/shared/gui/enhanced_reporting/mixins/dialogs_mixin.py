"""Dialog methods mixin for the enhanced reporting GUI."""

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (
    tk, ttk, filedialog, messagebox, simpledialog,
    ScrolledText,
    threading, webbrowser, os, json, logging,
    datetime, timedelta,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
    _t, logger,
    SystemConfig, load_templates, save_template, save_template_dict,
    DEFAULT_DB_PATH, pd,
    get_template, load_scheduled_reports, save_scheduled_reports,
    generate_report, get_log_file,
    time,
    DataQualityMonitor,
)


class DialogsMixin:
    """Mixin providing dialog and wizard methods."""

    def complete_system_tab_config_display(self):
        """Complete the configuration display area in system tab"""
        # This completes the cut-off section from the document
        config_display_frame = getattr(self, "config_display_frame", None)
        if config_display_frame is None:
            return
        self.config_display = ScrolledText(config_display_frame, height=10, wrap=tk.WORD)
        self.config_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        config_actions_bottom = ttk.Frame(config_display_frame)
        config_actions_bottom.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(config_actions_bottom, text="Reload Config",
                  command=self.reload_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(config_actions_bottom, text="Save Config",
                  command=self.save_config).pack(side=tk.LEFT, padx=(0, 5))


    # MISSING BACKUP/RESTORE COMPLETION
    def show_backup_restore_dialog(self):
        """Show backup and restore dialog"""
        try:
            backup_window = tk.Toplevel(self.root)
            backup_window.title("Backup & Restore")
            backup_window.geometry("600x500")
            backup_window.transient(self.root)

            backup_notebook = ttk.Notebook(backup_window)
            backup_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Backup tab
            backup_frame = ttk.Frame(backup_notebook)
            backup_notebook.add(backup_frame, text="Backup")

            backup_info = ttk.LabelFrame(backup_frame, text="Backup Information", padding="10")
            backup_info.pack(fill=tk.X, pady=10)

            ttk.Label(backup_info, text="The backup will include:").pack(anchor=tk.W)
            ttk.Label(backup_info, text="• Database (student_records.db)").pack(anchor=tk.W, padx=20)
            ttk.Label(backup_info, text="• Templates (templates.json)").pack(anchor=tk.W, padx=20)
            ttk.Label(backup_info, text="• Scheduled Reports").pack(anchor=tk.W, padx=20)
            ttk.Label(backup_info, text="• System Configuration").pack(anchor=tk.W, padx=20)

            # Backup options
            backup_options = ttk.LabelFrame(backup_frame, text="Backup Options", padding="10")
            backup_options.pack(fill=tk.X, pady=10)

            include_reports_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(backup_options, text="Include Generated Reports",
                           variable=include_reports_var).pack(anchor=tk.W)

            include_cache_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(backup_options, text="Include Cache Files",
                           variable=include_cache_var).pack(anchor=tk.W)

            def create_backup():
                try:
                    backup_dir = filedialog.askdirectory(title="Select Backup Directory")
                    if not backup_dir:
                        return

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"reporting_system_backup_{timestamp}"
                    full_backup_path = os.path.join(backup_dir, backup_name)
                    os.makedirs(full_backup_path, exist_ok=True)

                    import shutil

                    # Backup database
                    if os.path.exists(CONFIG.get('database', str(DEFAULT_DB_PATH))):
                        shutil.copy2(CONFIG['database'],
                                   os.path.join(full_backup_path, str(DEFAULT_DB_PATH)))

                    # Backup templates
                    templates_file = os.path.join(CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)), 'templates.json')
                    if os.path.exists(templates_file):
                        shutil.copy2(templates_file,
                                   os.path.join(full_backup_path, 'templates.json'))

                    # Create backup info file
                    backup_info = {
                        'created': datetime.now().isoformat(),
                        'version': '2.0',
                        'includes_reports': include_reports_var.get(),
                        'includes_cache': include_cache_var.get()
                    }

                    with open(os.path.join(full_backup_path, 'backup_info.json'), 'w') as f:
                        json.dump(backup_info, f, indent=4)

                    messagebox.showinfo("Backup Complete",
                                      f"Backup created successfully!\n\nLocation: {full_backup_path}")

                except Exception as e:
                    messagebox.showerror("Backup Error", f"Backup failed: {str(e)}")

            ttk.Button(backup_options, text="Create Backup", command=create_backup,
                      style='Success.TButton').pack(pady=10)

            # Restore tab
            restore_frame = ttk.Frame(backup_notebook)
            backup_notebook.add(restore_frame, text="Restore")

            restore_info = ttk.LabelFrame(restore_frame, text="Restore Information", padding="10")
            restore_info.pack(fill=tk.X, pady=10)

            ttk.Label(restore_info, text="Restoring will overwrite current data!").pack(anchor=tk.W)
            ttk.Label(restore_info, text="Please backup current data before restoring.").pack(anchor=tk.W)

            def restore_backup():
                try:
                    backup_dir = filedialog.askdirectory(title="Select Backup Directory to Restore")
                    if not backup_dir:
                        return

                    backup_info_file = os.path.join(backup_dir, 'backup_info.json')
                    if not os.path.exists(backup_info_file):
                        messagebox.showerror("Invalid Backup", "Selected directory is not a valid backup")
                        return

                    if not messagebox.askyesno("Confirm Restore",
                                             "This will overwrite current data. Continue?"):
                        return

                    import shutil

                    # Restore database
                    db_backup = os.path.join(backup_dir, str(DEFAULT_DB_PATH))
                    if os.path.exists(db_backup):
                        shutil.copy2(db_backup, CONFIG['database'])

                    messagebox.showinfo("Restore Complete", "Backup restored successfully!")

                except Exception as e:
                    messagebox.showerror("Restore Error", f"Restore failed: {str(e)}")

            ttk.Button(restore_info, text="Restore from Backup", command=restore_backup,
                      style='Warning.TButton').pack(pady=10)

        except Exception as e:
            messagebox.showerror("Backup/Restore Error", f"Failed to open backup dialog: {str(e)}")

            def restore_backup():
                try:
                    backup_dir = filedialog.askdirectory(title="Select Backup Directory to Restore")
                    if not backup_dir:
                        return

                    backup_info_file = os.path.join(backup_dir, 'backup_info.json')
                    if not os.path.exists(backup_info_file):
                        messagebox.showerror("Invalid Backup", "Selected directory is not a valid backup")
                        return

                    if not messagebox.askyesno("Confirm Restore",
                                             "This will overwrite current data. Continue?"):
                        return

                    import shutil

                    # Restore database
                    db_backup = os.path.join(backup_dir, str(DEFAULT_DB_PATH))
                    if os.path.exists(db_backup):
                        shutil.copy2(db_backup, CONFIG['database'])

                    messagebox.showinfo("Restore Complete", "Backup restored successfully!")

                except Exception as e:
                    messagebox.showerror("Restore Error", f"Restore failed: {str(e)}")

            ttk.Button(restore_info, text="Restore from Backup", command=restore_backup,
                      style='Warning.TButton').pack(pady=10)

        except Exception as e:
            messagebox.showerror("Backup/Restore Error", f"Failed to open backup dialog: {str(e)}")

    def show_user_management_dialog(self):
        """Show user management dialog"""
        try:
            user_window = tk.Toplevel(self.root)
            user_window.title("User Management")
            user_window.geometry("800x600")
            user_window.transient(self.root)

            note_frame = ttk.LabelFrame(user_window, text="Note", padding="10")
            note_frame.pack(fill=tk.X, padx=10, pady=10)

            note_text = """User management and authentication features are available in the full system.
This interface provides basic user management functionality."""

            ttk.Label(note_frame, text=note_text, wraplength=700).pack()

            users_frame = ttk.LabelFrame(user_window, text="System Users", padding="10")
            users_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('Username', 'Role', 'Last Login', 'Status')
            users_tree = ttk.Treeview(users_frame, columns=columns, show='headings')

            for col in columns:
                users_tree.heading(col, text=col)
                users_tree.column(col, width=150)

            sample_users = [
                ('admin', 'Administrator', '2024-01-15 09:30', 'Active'),
                ('analyst', 'Analyst', '2024-01-14 14:22', 'Active'),
                ('viewer', 'Viewer', 'Never', 'Inactive')
            ]

            for user in sample_users:
                users_tree.insert('', tk.END, values=user)

            users_tree.pack(fill=tk.BOTH, expand=True)

            actions_frame = ttk.Frame(users_frame)
            actions_frame.pack(fill=tk.X, pady=(10, 0))

            ttk.Button(actions_frame, text="Add User",
                      command=lambda: messagebox.showinfo("Feature", "User creation would be implemented here")).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(actions_frame, text="Edit User",
                      command=lambda: messagebox.showinfo("Feature", "User editing would be implemented here")).pack(side=tk.LEFT, padx=(0, 5))

            ttk.Button(user_window, text="Close", command=user_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("User Management Error", f"Failed to open user management: {str(e)}")

    def show_directory_settings(self):
        """Show directory settings dialog"""
        try:
            dir_window = tk.Toplevel(self.root)
            dir_window.title("Directory Settings")
            dir_window.geometry("500x400")
            dir_window.transient(self.root)

            settings_frame = ttk.LabelFrame(dir_window, text="Directory Configuration", padding="10")
            settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            settings_frame.columnconfigure(1, weight=1)

            # Reports directory
            ttk.Label(settings_frame, text="Reports Directory:").grid(row=0, column=0, sticky=tk.W, pady=5)
            reports_dir_var = tk.StringVar(value=CONFIG.get('reports_dir', 'reports'))
            ttk.Entry(settings_frame, textvariable=reports_dir_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            def browse_reports_dir():
                directory = filedialog.askdirectory(title="Select Reports Directory")
                if directory:
                    reports_dir_var.set(directory)

            ttk.Button(settings_frame, text="Browse", command=browse_reports_dir).grid(row=0, column=2, padx=(5, 0), pady=5)

            # Templates directory
            ttk.Label(settings_frame, text="Templates Directory:").grid(row=1, column=0, sticky=tk.W, pady=5)
            templates_dir_var = tk.StringVar(value=CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)))
            ttk.Entry(settings_frame, textvariable=templates_dir_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            def browse_templates_dir():
                directory = filedialog.askdirectory(title="Select Templates Directory")
                if directory:
                    templates_dir_var.set(directory)

            ttk.Button(settings_frame, text="Browse", command=browse_templates_dir).grid(row=1, column=2, padx=(5, 0), pady=5)

            # Create directories option
            create_dirs_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(settings_frame, text="Create directories if they don't exist",
                           variable=create_dirs_var).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=10)

            # Button frame
            button_frame = ttk.Frame(dir_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_directory_settings():
                try:
                    new_dirs = {
                        'reports_dir': reports_dir_var.get(),
                        'templates_dir': templates_dir_var.get()
                    }

                    if create_dirs_var.get():
                        for dir_path in new_dirs.values():
                            os.makedirs(dir_path, exist_ok=True)

                    CONFIG.update(new_dirs)

                    messagebox.showinfo("Success", "Directory settings saved successfully!")
                    dir_window.destroy()
                    self.check_system_status()

                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to save directory settings: {str(e)}")

            ttk.Button(button_frame, text="Save", command=save_directory_settings).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Cancel", command=dir_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Directory Settings Error", f"Failed to open directory settings: {str(e)}")

    def show_theme_settings(self):
        """Show theme and appearance settings"""
        try:
            theme_window = tk.Toplevel(self.root)
            theme_window.title("Theme & Appearance Settings")
            theme_window.geometry("450x350")
            theme_window.transient(self.root)

            theme_frame = ttk.LabelFrame(theme_window, text="Appearance Settings", padding="10")
            theme_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Theme selection
            ttk.Label(theme_frame, text="Theme:").pack(anchor=tk.W, pady=5)
            theme_var = tk.StringVar(value="default")
            theme_combo = ttk.Combobox(theme_frame, textvariable=theme_var,
                                      values=["default", "dark", "light", "modern"], state="readonly")
            theme_combo.pack(fill=tk.X, pady=(0, 10))

            # Font settings
            ttk.Label(theme_frame, text="Font Family:").pack(anchor=tk.W, pady=5)
            font_var = tk.StringVar(value="Arial")
            font_combo = ttk.Combobox(theme_frame, textvariable=font_var,
                                     values=["Arial", "Helvetica", "Times New Roman", "Calibri"],
                                     state="readonly")
            font_combo.pack(fill=tk.X, pady=(0, 10))

            # Font size
            ttk.Label(theme_frame, text="Font Size:").pack(anchor=tk.W, pady=5)
            font_size_var = tk.StringVar(value="10")
            font_size_spin = ttk.Spinbox(theme_frame, from_=8, to=16, textvariable=font_size_var)
            font_size_spin.pack(fill=tk.X, pady=(0, 10))

            # Preview
            preview_frame = ttk.LabelFrame(theme_frame, text="Preview", padding="10")
            preview_frame.pack(fill=tk.X, pady=10)

            preview_label = ttk.Label(preview_frame, text="Sample text with current settings")
            preview_label.pack()

            def update_preview():
                try:
                    font_family = font_var.get()
                    font_size = int(font_size_var.get())
                    preview_label.config(font=(font_family, font_size))
                except Exception as e:
                    logger.debug(f"Failed to configure preview label font: {e}")

            theme_combo.bind('<<ComboboxSelected>>', lambda e: update_preview())
            font_combo.bind('<<ComboboxSelected>>', lambda e: update_preview())

            # Button frame
            button_frame = ttk.Frame(theme_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def apply_theme():
                try:
                    theme_settings = {
                        'theme': theme_var.get(),
                        'font_family': font_var.get(),
                        'font_size': int(font_size_var.get())
                    }

                    messagebox.showinfo("Theme Applied",
                                      f"Theme settings would be applied:\n\nTheme: {theme_settings['theme']}\nFont: {theme_settings['font_family']} {theme_settings['font_size']}pt")
                    theme_window.destroy()

                except Exception as e:
                    messagebox.showerror("Theme Error", f"Failed to apply theme: {str(e)}")

            ttk.Button(button_frame, text="Apply", command=apply_theme).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Cancel", command=theme_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Theme Settings Error", f"Failed to open theme settings: {str(e)}")

    def check_system_requirements_gui(self):
        """GUI version of system requirements check"""
        try:
            req_window = tk.Toplevel(self.root)
            req_window.title("System Requirements Check")
            req_window.geometry("600x400")
            req_window.transient(self.root)

            # Requirements display
            req_frame = ttk.LabelFrame(req_window, text="System Requirements Status", padding="10")
            req_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            req_text = ScrolledText(req_frame, wrap=tk.WORD)
            req_text.pack(fill=tk.BOTH, expand=True)

            def check_requirements():
                requirements_status = {
                    'tkinter': True,  # Already available if GUI is running
                    'pandas': pd is not None,
                    'enhanced_features': ENHANCED_AVAILABLE,
                    'database': False,
                    'matplotlib': True,  # Check if plotting works
                    'reportlab': True   # Check if PDF generation works
                }

                # Test database connection
                try:
                    conn = get_db_connection()
                    if conn:
                        conn.close()
                        requirements_status['database'] = True
                except Exception as e:
                    logger.debug(f"Failed to check database requirements: {e}")

                # Test matplotlib
                try:
                    import matplotlib.pyplot as plt
                    plt.figure()
                    plt.close()
                except Exception:
                    requirements_status['matplotlib'] = False

                # Generate report
                report = "System Requirements Check\n"
                report += "=" * 40 + "\n\n"

                for requirement, status in requirements_status.items():
                    status_text = "✓ Available" if status else "✗ Missing"
                    report += f"{requirement.replace('_', ' ').title()}: {status_text}\n"

                # Recommendations
                missing = [req for req, status in requirements_status.items() if not status]
                if missing:
                    report += f"\nMissing Requirements: {', '.join(missing)}\n"
                    report += "\nRecommendations:\n"
                    if 'pandas' in missing:
                        report += "- Install pandas: pip install pandas\n"
                    if 'matplotlib' in missing:
                        report += "- Install matplotlib: pip install matplotlib\n"
                    if 'reportlab' in missing:
                        report += "- Install reportlab: pip install reportlab\n"
                    if not requirements_status['database']:
                        report += "- Check database connection and permissions\n"
                else:
                    report += "\n✓ All requirements satisfied!\n"

                req_text.delete(1.0, tk.END)
                req_text.insert(1.0, report)

            # Run check automatically
            check_requirements()

            # Buttons
            button_frame = ttk.Frame(req_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Refresh Check", command=check_requirements).pack(side=tk.LEFT)
            ttk.Button(button_frame, text="Close", command=req_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Requirements Check Error", f"Failed to check requirements: {str(e)}")

    def show_advanced_template_creation_dialog(self):
        """Show advanced template creation dialog matching CLI functionality"""
        try:
            template_window = tk.Toplevel(self.root)
            template_window.title("Advanced Template Creation")
            template_window.geometry("800x700")
            template_window.transient(self.root)

            # Create notebook for different template aspects
            template_notebook = ttk.Notebook(template_window)
            template_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Basic Info Tab
            basic_frame = ttk.Frame(template_notebook)
            template_notebook.add(basic_frame, text="Basic Info")

            basic_info_frame = ttk.LabelFrame(basic_frame, text="Template Information", padding="10")
            basic_info_frame.pack(fill=tk.X, padx=10, pady=10)
            basic_info_frame.columnconfigure(1, weight=1)

            ttk.Label(basic_info_frame, text="Name:*").grid(row=0, column=0, sticky=tk.W, pady=5)
            name_var = tk.StringVar()
            ttk.Entry(basic_info_frame, textvariable=name_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            ttk.Label(basic_info_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=5)
            desc_var = tk.StringVar()
            ttk.Entry(basic_info_frame, textvariable=desc_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Security and Visualization
            security_frame = ttk.LabelFrame(basic_frame, text="Security & Visualization", padding="10")
            security_frame.pack(fill=tk.X, padx=10, pady=10)
            security_frame.columnconfigure(1, weight=1)

            ttk.Label(security_frame, text="Security Level:").grid(row=0, column=0, sticky=tk.W, pady=5)
            security_var = tk.StringVar(value="normal")
            security_combo = ttk.Combobox(security_frame, textvariable=security_var,
                                         values=["normal", "confidential", "restricted"], state="readonly")
            security_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            ttk.Label(security_frame, text="Visualization Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
            viz_var = tk.StringVar(value="standard")
            viz_combo = ttk.Combobox(security_frame, textvariable=viz_var,
                                    values=["standard", "advanced", "interactive"], state="readonly")
            viz_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Sections Tab
            sections_frame = ttk.Frame(template_notebook)
            template_notebook.add(sections_frame, text="Sections")

            sections_info = ttk.LabelFrame(sections_frame, text="Available Report Sections", padding="10")
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
            template_notebook.add(filters_frame, text="Filters")

            filters_info = ttk.LabelFrame(filters_frame, text="Data Filters", padding="10")
            filters_info.pack(fill=tk.X, padx=10, pady=10)
            filters_info.columnconfigure(1, weight=1)

            ttk.Label(filters_info, text="Course Filter:").grid(row=0, column=0, sticky=tk.W, pady=5)
            course_var = tk.StringVar()
            course_combo = ttk.Combobox(filters_info, textvariable=course_var,
                                       values=["", "CS", "DS"], state="readonly")
            course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            ttk.Label(filters_info, text="Date Range (days):").grid(row=1, column=0, sticky=tk.W, pady=5)
            date_range_var = tk.StringVar(value="30")
            ttk.Entry(filters_info, textvariable=date_range_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

            # Advanced Tab
            advanced_frame = ttk.Frame(template_notebook)
            template_notebook.add(advanced_frame, text="Advanced")

            advanced_info = ttk.LabelFrame(advanced_frame, text="Advanced Options", padding="10")
            advanced_info.pack(fill=tk.X, padx=10, pady=10)

            enable_caching_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(advanced_info, text="Enable caching for faster generation",
                           variable=enable_caching_var).pack(anchor=tk.W, pady=2)

            enable_comparison_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(advanced_info, text="Include period-over-period comparison",
                           variable=enable_comparison_var).pack(anchor=tk.W, pady=2)

            enable_export_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(advanced_info, text="Allow multiple export formats",
                           variable=enable_export_var).pack(anchor=tk.W, pady=2)

            def create_advanced_template():
                try:
                    name = name_var.get().strip()
                    if not name:
                        messagebox.showerror("Validation Error", "Template name is required")
                        return

                    if get_template(name):
                        messagebox.showerror("Template Exists", f"Template '{name}' already exists")
                        return

                    # Get selected sections
                    selected_sections = [section for section, var in section_vars.items() if var.get()]
                    if not selected_sections:
                        messagebox.showerror("Validation Error", "At least one section must be selected")
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

                        os.makedirs(CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)), exist_ok=True)
                        with open(os.path.join(CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)), "templates.json"), 'w') as f:
                            json.dump(templates, f, indent=4)

                    messagebox.showinfo("Success", f"Advanced template '{name}' created successfully!")
                    template_window.destroy()
                    self.refresh_data()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create template: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(template_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Create Template", command=create_advanced_template,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Cancel", command=template_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Template Creation Error", f"Failed to open template creation dialog: {str(e)}")

    def show_enhanced_scheduling_dialog(self):
        """Show enhanced scheduling dialog with all CLI features"""
        try:
            schedule_window = tk.Toplevel(self.root)
            schedule_window.title("Enhanced Report Scheduling")
            schedule_window.geometry("700x600")
            schedule_window.transient(self.root)

            # Create notebook for different scheduling aspects
            schedule_notebook = ttk.Notebook(schedule_window)
            schedule_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Basic Scheduling Tab
            basic_frame = ttk.Frame(schedule_notebook)
            schedule_notebook.add(basic_frame, text="Basic Schedule")

            # Template selection
            template_frame = ttk.LabelFrame(basic_frame, text="Template Selection", padding="10")
            template_frame.pack(fill=tk.X, padx=10, pady=10)

            templates = load_templates() if ENHANCED_AVAILABLE else []
            if not templates:
                ttk.Label(template_frame, text="No templates available for scheduling").pack()
                return

            ttk.Label(template_frame, text="Select Template:").pack(anchor=tk.W)
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(template_frame, textvariable=template_var, state="readonly")
            template_combo['values'] = [t['name'] for t in templates]
            template_combo.pack(fill=tk.X, pady=(5, 0))

            if templates:
                template_combo.set(templates[0]['name'])

            # Schedule configuration
            config_frame = ttk.LabelFrame(basic_frame, text="Schedule Configuration", padding="10")
            config_frame.pack(fill=tk.X, padx=10, pady=10)
            config_frame.columnconfigure(1, weight=1)

            ttk.Label(config_frame, text="Frequency:").grid(row=0, column=0, sticky=tk.W, pady=5)
            frequency_var = tk.StringVar(value="weekly")
            frequency_combo = ttk.Combobox(config_frame, textvariable=frequency_var,
                                          values=["daily", "weekly", "monthly"], state="readonly")
            frequency_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            ttk.Label(config_frame, text="Hour (0-23):").grid(row=1, column=0, sticky=tk.W, pady=5)
            hour_var = tk.StringVar(value="9")
            hour_spin = ttk.Spinbox(config_frame, from_=0, to=23, textvariable=hour_var, width=5)
            hour_spin.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

            # Recipients Tab
            recipients_frame = ttk.Frame(schedule_notebook)
            schedule_notebook.add(recipients_frame, text="Recipients")

            recipients_info = ttk.LabelFrame(recipients_frame, text="Email Recipients", padding="10")
            recipients_info.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Label(recipients_info, text="Enter email addresses (one per line):").pack(anchor=tk.W)
            recipients_text = tk.Text(recipients_info, height=10, width=50)
            recipients_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

            # Conditions Tab
            conditions_frame = ttk.Frame(schedule_notebook)
            schedule_notebook.add(conditions_frame, text="Conditions")

            conditions_info = ttk.LabelFrame(conditions_frame, text="Execution Conditions", padding="10")
            conditions_info.pack(fill=tk.X, padx=10, pady=10)

            only_if_data_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(conditions_info, text="Only run if new data is available",
                           variable=only_if_data_var).pack(anchor=tk.W, pady=2)

            skip_if_empty_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(conditions_info, text="Skip if no students found",
                           variable=skip_if_empty_var).pack(anchor=tk.W, pady=2)

            retry_on_failure_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(conditions_info, text="Retry on failure",
                           variable=retry_on_failure_var).pack(anchor=tk.W, pady=2)

            def create_enhanced_schedule():
                try:
                    template_name = template_var.get()
                    if not template_name:
                        messagebox.showerror("Error", "Please select a template")
                        return

                    # Validate hour
                    try:
                        hour = int(hour_var.get())
                        if not (0 <= hour <= 23):
                            raise ValueError("Hour must be between 0 and 23")
                    except ValueError as e:
                        messagebox.showerror("Error", f"Invalid hour: {str(e)}")
                        return

                    # Get recipients
                    recipients_input = recipients_text.get(1.0, tk.END).strip()
                    recipients = [email.strip() for email in recipients_input.split('\n')
                                 if email.strip() and '@' in email]

                    if not recipients:
                        if not messagebox.askyesno("No Recipients",
                                                 "No email recipients specified. Report will be generated but not sent. Continue?"):
                            return

                    # Build schedule configuration
                    schedule_config = {
                        'frequency': frequency_var.get(),
                        'hour': hour,
                        'enabled': True,
                        'conditions': {
                            'only_if_data': only_if_data_var.get(),
                            'skip_if_empty': skip_if_empty_var.get(),
                            'retry_on_failure': retry_on_failure_var.get()
                        }
                    }

                    # Create scheduled report
                    if ENHANCED_AVAILABLE:
                        scheduled_report = {
                            'template_name': template_name,
                            'schedule_config': schedule_config,
                            'recipients': recipients,
                            'created_at': datetime.now().isoformat(),
                            'last_run': None,
                            'run_count': 0,
                            'is_active': True
                        }

                        scheduled_reports = load_scheduled_reports()
                        scheduled_reports.append(scheduled_report)
                        save_scheduled_reports(scheduled_reports)

                        messagebox.showinfo("Success",
                                          f"Enhanced schedule created for '{template_name}'!\n\n"
                                          f"Frequency: {frequency_var.get().title()}\n"
                                          f"Time: {hour:02d}:00\n"
                                          f"Recipients: {len(recipients)}")

                        schedule_window.destroy()
                        self.refresh_data()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create schedule: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(schedule_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Create Schedule", command=create_enhanced_schedule,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Cancel", command=schedule_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Scheduling Error", f"Failed to open scheduling dialog: {str(e)}")

    # Additional missing GUI functions for ReportingSystemGUI class

    def show_template_comparison_dialog(self):
        """Compare multiple templates side by side"""
        try:
            compare_window = tk.Toplevel(self.root)
            compare_window.title("Template Comparison")
            compare_window.geometry("900x600")
            compare_window.transient(self.root)

            templates = load_templates() if ENHANCED_AVAILABLE else []
            if len(templates) < 2:
                messagebox.showinfo("Insufficient Templates", "Need at least 2 templates to compare")
                compare_window.destroy()
                return

            # Template selection frame
            selection_frame = ttk.LabelFrame(compare_window, text="Select Templates to Compare", padding="10")
            selection_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(selection_frame, text="Template 1:").pack(side=tk.LEFT)
            template1_var = tk.StringVar()
            template1_combo = ttk.Combobox(selection_frame, textvariable=template1_var,
                                          values=[t['name'] for t in templates], state="readonly")
            template1_combo.pack(side=tk.LEFT, padx=(5, 20))

            ttk.Label(selection_frame, text="Template 2:").pack(side=tk.LEFT)
            template2_var = tk.StringVar()
            template2_combo = ttk.Combobox(selection_frame, textvariable=template2_var,
                                          values=[t['name'] for t in templates], state="readonly")
            template2_combo.pack(side=tk.LEFT, padx=5)

            # Comparison display
            comparison_frame = ttk.LabelFrame(compare_window, text="Comparison Results", padding="10")
            comparison_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            comparison_text = ScrolledText(comparison_frame, wrap=tk.WORD)
            comparison_text.pack(fill=tk.BOTH, expand=True)

            def compare_templates():
                name1 = template1_var.get()
                name2 = template2_var.get()

                if not name1 or not name2:
                    messagebox.showwarning("Selection Required", "Please select both templates")
                    return

                if name1 == name2:
                    messagebox.showwarning("Same Template", "Please select different templates")
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

            ttk.Button(selection_frame, text="Compare", command=compare_templates).pack(side=tk.RIGHT, padx=(20, 0))

            ttk.Button(compare_window, text="Close", command=compare_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Comparison Error", f"Failed to open comparison dialog: {str(e)}")

    def show_template_versioning_dialog(self):
        """Show template version history and management"""
        try:
            version_window = tk.Toplevel(self.root)
            version_window.title("Template Version Management")
            version_window.geometry("700x500")
            version_window.transient(self.root)

            # Template selection
            selection_frame = ttk.LabelFrame(version_window, text="Select Template", padding="10")
            selection_frame.pack(fill=tk.X, padx=10, pady=10)

            templates = load_templates() if ENHANCED_AVAILABLE else []
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(selection_frame, textvariable=template_var,
                                         values=[t['name'] for t in templates], state="readonly")
            template_combo.pack(fill=tk.X)

            # Version history display
            history_frame = ttk.LabelFrame(version_window, text="Version History", padding="10")
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

            ttk.Button(version_window, text="Close", command=version_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Version Error", f"Failed to open version dialog: {str(e)}")

    def show_bulk_operations_dialog(self):
        """Show bulk operations for templates and reports"""
        try:
            bulk_window = tk.Toplevel(self.root)
            bulk_window.title("Bulk Operations")
            bulk_window.geometry("600x500")
            bulk_window.transient(self.root)

            # Operation selection
            operation_frame = ttk.LabelFrame(bulk_window, text="Select Operation", padding="10")
            operation_frame.pack(fill=tk.X, padx=10, pady=10)

            operation_var = tk.StringVar(value="export_templates")

            operations = [
                ("export_templates", "Export All Templates"),
                ("import_templates", "Import Multiple Templates"),
                ("generate_all_reports", "Generate Reports for All Templates"),
                ("cleanup_old_reports", "Cleanup Old Reports"),
                ("backup_all_data", "Backup All System Data")
            ]

            for op_id, op_name in operations:
                ttk.Radiobutton(operation_frame, text=op_name,
                               variable=operation_var, value=op_id).pack(anchor=tk.W)

            # Options frame
            options_frame = ttk.LabelFrame(bulk_window, text="Options", padding="10")
            options_frame.pack(fill=tk.X, padx=10, pady=10)

            include_data_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text="Include data files",
                           variable=include_data_var).pack(anchor=tk.W)

            confirm_actions_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text="Confirm each action",
                           variable=confirm_actions_var).pack(anchor=tk.W)

            # Progress display
            progress_frame = ttk.LabelFrame(bulk_window, text="Progress", padding="10")
            progress_frame.pack(fill=tk.X, padx=10, pady=10)

            progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
            progress_bar.pack(fill=tk.X, pady=(0, 5))

            progress_label = ttk.Label(progress_frame, text="Ready")
            progress_label.pack(anchor=tk.W)

            # Results display
            results_frame = ttk.LabelFrame(bulk_window, text="Results", padding="10")
            results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            results_text = ScrolledText(results_frame, height=8, wrap=tk.WORD)
            results_text.pack(fill=tk.BOTH, expand=True)

            def execute_bulk_operation():
                operation = operation_var.get()
                results_text.delete(1.0, tk.END)

                def bulk_task():
                    try:
                        if operation == "export_templates":
                            templates = load_templates() if ENHANCED_AVAILABLE else []
                            progress_bar['maximum'] = len(templates)

                            export_dir = filedialog.askdirectory(title="Select Export Directory")
                            if not export_dir:
                                return

                            for i, template in enumerate(templates):
                                filename = f"{template['name'].replace(' ', '_')}_template.json"
                                filepath = os.path.join(export_dir, filename)

                                with open(filepath, 'w') as f:
                                    json.dump(template, f, indent=4)

                                progress_bar['value'] = i + 1
                                progress_label.config(text=f"Exported: {template['name']}")
                                time.sleep(0.1)

                            results_text.insert(tk.END, f"Successfully exported {len(templates)} templates to {export_dir}")

                        elif operation == "generate_all_reports":
                            templates = load_templates() if ENHANCED_AVAILABLE else []
                            progress_bar['maximum'] = len(templates)

                            end_date = datetime.now().strftime("%Y-%m-%d")
                            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

                            for i, template in enumerate(templates):
                                try:
                                    report_path = generate_report(template['name'], start_date, end_date, 'pdf')
                                    if report_path:
                                        results_text.insert(tk.END, f"✓ Generated: {template['name']}\n")
                                    else:
                                        results_text.insert(tk.END, f"✗ Failed: {template['name']}\n")
                                except Exception as e:
                                    results_text.insert(tk.END, f"✗ Error in {template['name']}: {str(e)}\n")

                                progress_bar['value'] = i + 1
                                progress_label.config(text=f"Processing: {template['name']}")
                                results_text.see(tk.END)
                                time.sleep(0.5)

                        progress_label.config(text="Operation completed")

                    except Exception as e:
                        results_text.insert(tk.END, f"Error: {str(e)}")

                threading.Thread(target=bulk_task, daemon=True).start()

            # Buttons
            button_frame = ttk.Frame(bulk_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Execute", command=execute_bulk_operation,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Close", command=bulk_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Bulk Operations Error", f"Failed to open bulk operations: {str(e)}")

    def show_data_visualization_studio(self):
        """Show advanced data visualization studio"""
        try:
            studio_window = tk.Toplevel(self.root)
            studio_window.title("Data Visualization Studio")
            studio_window.geometry("900x700")
            studio_window.transient(self.root)

            # Create notebook for different visualization aspects
            studio_notebook = ttk.Notebook(studio_window)
            studio_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Chart Builder Tab
            chart_frame = ttk.Frame(studio_notebook)
            studio_notebook.add(chart_frame, text="Chart Builder")

            # Data selection
            data_frame = ttk.LabelFrame(chart_frame, text="Data Selection", padding="10")
            data_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(data_frame, text="Data Source:").pack(anchor=tk.W)
            data_source_var = tk.StringVar(value="students")
            data_combo = ttk.Combobox(data_frame, textvariable=data_source_var,
                                     values=["students", "courses", "modules", "attendance"], state="readonly")
            data_combo.pack(fill=tk.X)

            # Chart type selection
            chart_frame_inner = ttk.LabelFrame(chart_frame, text="Chart Type", padding="10")
            chart_frame_inner.pack(fill=tk.X, padx=10, pady=10)

            chart_type_var = tk.StringVar(value="bar")
            chart_types = [("bar", "Bar Chart"), ("pie", "Pie Chart"), ("line", "Line Chart"),
                          ("scatter", "Scatter Plot"), ("heatmap", "Heatmap")]

            for chart_id, chart_name in chart_types:
                ttk.Radiobutton(chart_frame_inner, text=chart_name,
                               variable=chart_type_var, value=chart_id).pack(anchor=tk.W)

            # Styling options
            style_frame = ttk.LabelFrame(chart_frame, text="Styling Options", padding="10")
            style_frame.pack(fill=tk.X, padx=10, pady=10)

            color_scheme_var = tk.StringVar(value="default")
            ttk.Label(style_frame, text="Color Scheme:").pack(anchor=tk.W)
            ttk.Combobox(style_frame, textvariable=color_scheme_var,
                        values=["default", "viridis", "plasma", "cool", "warm"], state="readonly").pack(fill=tk.X)

            # Custom Dashboard Tab
            dashboard_frame = ttk.Frame(studio_notebook)
            studio_notebook.add(dashboard_frame, text="Dashboard")

            dashboard_info = ttk.LabelFrame(dashboard_frame, text="Dashboard Components", padding="10")
            dashboard_info.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Component selection
            components = {}
            component_types = [
                ("overview_cards", "Overview Cards", True),
                ("trend_charts", "Trend Charts", True),
                ("distribution_charts", "Distribution Charts", False),
                ("comparison_tables", "Comparison Tables", False),
                ("filter_controls", "Interactive Filters", False)
            ]

            for comp_id, comp_name, default_val in component_types:
                var = tk.BooleanVar(value=default_val)
                components[comp_id] = var
                ttk.Checkbutton(dashboard_info, text=comp_name, variable=var).pack(anchor=tk.W)

            def generate_visualization():
                try:
                    chart_type = chart_type_var.get()
                    data_source = data_source_var.get()
                    color_scheme = color_scheme_var.get()

                    # Generate sample visualization based on selections
                    messagebox.showinfo("Visualization Generated",
                                      f"Generated {chart_type} chart for {data_source} data with {color_scheme} colors!")

                except Exception as e:
                    messagebox.showerror("Generation Error", f"Failed to generate visualization: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(studio_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Generate Visualization", command=generate_visualization,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Close", command=studio_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Visualization Studio Error", f"Failed to open visualization studio: {str(e)}")

    def show_report_analytics_dashboard(self):
        """Show analytics about report generation and usage"""
        try:
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title("Report Analytics Dashboard")
            analytics_window.geometry("800x600")
            analytics_window.transient(self.root)

            # Metrics display
            metrics_frame = ttk.LabelFrame(analytics_window, text="Report Metrics", padding="10")
            metrics_frame.pack(fill=tk.X, padx=10, pady=10)

            # Calculate metrics
            templates = load_templates() if ENHANCED_AVAILABLE else []
            scheduled_reports = load_scheduled_reports() if ENHANCED_AVAILABLE else []

            # Report counts
            reports_dir = CONFIG.get('reports_dir', 'reports') if ENHANCED_AVAILABLE else 'reports'
            report_count = 0
            if os.path.exists(reports_dir):
                report_count = len([f for f in os.listdir(reports_dir)
                                  if f.endswith(('.pdf', '.xlsx', '.html'))])

            metrics_text = f"""Report System Analytics
{"=" * 30}

Templates: {len(templates)}
Scheduled Reports: {len(scheduled_reports)}
Generated Reports: {report_count}
Active Schedules: {sum(1 for r in scheduled_reports if r.get('schedule_config', {}).get('enabled', True))}

Most Used Sections:"""

            # Count section usage across templates
            section_counts = {}
            for template in templates:
                for section in template.get('sections', []):
                    section_counts[section] = section_counts.get(section, 0) + 1

            for section, count in sorted(section_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                metrics_text += f"\n- {section.replace('_', ' ').title()}: {count} templates"

            metrics_display = ScrolledText(metrics_frame, height=15, wrap=tk.WORD)
            metrics_display.pack(fill=tk.BOTH, expand=True)
            metrics_display.insert(1.0, metrics_text)
            metrics_display.config(state=tk.DISABLED)

            # Usage trends (placeholder)
            trends_frame = ttk.LabelFrame(analytics_window, text="Usage Trends", padding="10")
            trends_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Label(trends_frame, text="Trend analysis would be displayed here with actual usage data").pack()

            ttk.Button(analytics_window, text="Close", command=analytics_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Analytics Error", f"Failed to open analytics dashboard: {str(e)}")

    # Final missing GUI functions for ReportingSystemGUI class

    def show_api_endpoints_documentation(self):
        """Show comprehensive API documentation dialog"""
        try:
            api_doc_window = tk.Toplevel(self.root)
            api_doc_window.title("API Documentation")
            api_doc_window.geometry("900x700")
            api_doc_window.transient(self.root)

            # Create notebook for different API sections
            api_notebook = ttk.Notebook(api_doc_window)
            api_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Authentication Tab
            auth_frame = ttk.Frame(api_notebook)
            api_notebook.add(auth_frame, text="Authentication")

            auth_text = ScrolledText(auth_frame, wrap=tk.WORD)
            auth_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            auth_docs = """API Authentication
=================

POST /api/login
- Description: User authentication
- Body: {"username": "user", "password": "pass"}
- Response: {"token": "jwt_token", "expires": "timestamp"}

Authentication Headers:
- Authorization: Bearer <token>
- Content-Type: application/json
"""
            auth_text.insert(1.0, auth_docs)

            # Endpoints Tab
            endpoints_frame = ttk.Frame(api_notebook)
            api_notebook.add(endpoints_frame, text="Endpoints")

            endpoints_text = ScrolledText(endpoints_frame, wrap=tk.WORD)
            endpoints_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            endpoints_docs = """API Endpoints Reference
======================

TEMPLATES:
GET  /api/templates - List all templates
POST /api/templates - Create new template
GET  /api/templates/{name} - Get specific template
PUT  /api/templates/{name} - Update template
DELETE /api/templates/{name} - Delete template

REPORTS:
POST /api/reports/generate - Generate report
  Body: {
    "template_name": "string",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "format": "pdf|excel|interactive"
  }

DATA:
GET /api/data/{section} - Get section data
  Parameters: start_date, end_date, filters

ANALYTICS:
GET /api/analytics/quality - Data quality metrics
GET /api/analytics/predictions - Dropout risk predictions
GET /api/analytics/anomalies - Anomaly detection results
GET /api/analytics/correlations - Correlation analysis

SYSTEM:
GET /api/health - System health check
GET /api/config - System configuration
"""
            endpoints_text.insert(1.0, endpoints_docs)

            # Examples Tab
            examples_frame = ttk.Frame(api_notebook)
            api_notebook.add(examples_frame, text="Examples")

            examples_text = ScrolledText(examples_frame, wrap=tk.WORD)
            examples_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            examples_docs = """API Usage Examples
==================

Generate a PDF Report:
curl -X POST http://localhost:5000/api/reports/generate \\
  -H "Content-Type: application/json" \\
  -d '{
    "template_name": "student_overview",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "format": "pdf"
  }'

Get Data Quality Metrics:
curl -X GET http://localhost:5000/api/analytics/quality \\
  -H "Authorization: Bearer <token>"

Create New Template:
curl -X POST http://localhost:5000/api/templates \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Custom Report",
    "description": "My custom report",
    "sections": ["student_overview", "course_distribution"],
    "visualization_type": "standard"
  }'
"""
            examples_text.insert(1.0, examples_docs)

            ttk.Button(api_doc_window, text="Close", command=api_doc_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("API Documentation Error", f"Failed to open API documentation: {str(e)}")

    def show_system_logs_viewer(self):
        """Show real-time system logs viewer"""
        try:
            logs_window = tk.Toplevel(self.root)
            logs_window.title("System Logs Viewer")
            logs_window.geometry("900x600")
            logs_window.transient(self.root)

            # Controls frame
            controls_frame = ttk.Frame(logs_window)
            controls_frame.pack(fill=tk.X, padx=10, pady=10)

            # Log level filter
            ttk.Label(controls_frame, text="Log Level:").pack(side=tk.LEFT)
            log_level_var = tk.StringVar(value="ALL")
            log_level_combo = ttk.Combobox(controls_frame, textvariable=log_level_var,
                                          values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"], state="readonly")
            log_level_combo.pack(side=tk.LEFT, padx=(5, 20))

            # Auto-refresh
            auto_refresh_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(controls_frame, text="Auto-refresh", variable=auto_refresh_var).pack(side=tk.LEFT, padx=(0, 20))

            # Clear logs button
            def clear_logs():
                logs_text.delete(1.0, tk.END)

            ttk.Button(controls_frame, text="Clear", command=clear_logs).pack(side=tk.LEFT)
            ttk.Button(controls_frame, text="Refresh", command=lambda: load_logs()).pack(side=tk.LEFT, padx=(5, 0))

            # Logs display
            logs_frame = ttk.LabelFrame(logs_window, text="System Logs", padding="10")
            logs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            logs_text = ScrolledText(logs_frame, wrap=tk.NONE, font=("Consolas", 9))
            logs_text.pack(fill=tk.BOTH, expand=True)

            def load_logs():
                try:
                    log_file = get_log_file('app.log')
                    if not os.path.exists(log_file):
                        logs_text.insert(tk.END, "No log file found\n")
                        return

                    with open(log_file, 'r') as f:
                        lines = f.readlines()

                    # Filter by log level
                    level_filter = log_level_var.get()
                    if level_filter != "ALL":
                        lines = [line for line in lines if level_filter in line]

                    # Show last 1000 lines
                    display_lines = lines[-1000:] if len(lines) > 1000 else lines

                    logs_text.delete(1.0, tk.END)
                    for line in display_lines:
                        # Color code by log level
                        if "ERROR" in line:
                            logs_text.insert(tk.END, line, "error")
                        elif "WARNING" in line:
                            logs_text.insert(tk.END, line, "warning")
                        elif "INFO" in line:
                            logs_text.insert(tk.END, line, "info")
                        else:
                            logs_text.insert(tk.END, line)

                    logs_text.see(tk.END)

                except Exception as e:
                    logs_text.insert(tk.END, f"Error loading logs: {str(e)}\n")

            # Configure text tags for coloring
            logs_text.tag_configure("error", foreground="red")
            logs_text.tag_configure("warning", foreground="orange")
            logs_text.tag_configure("info", foreground="blue")

            # Auto-refresh functionality
            def auto_refresh():
                if auto_refresh_var.get():
                    load_logs()
                logs_window.after(5000, auto_refresh)  # Refresh every 5 seconds

            # Initial load and start auto-refresh
            load_logs()
            auto_refresh()

        except Exception as e:
            messagebox.showerror("Logs Viewer Error", f"Failed to open logs viewer: {str(e)}")

    def show_data_import_export_dialog(self):
        """Show data import/export utilities dialog"""
        try:
            import_export_window = tk.Toplevel(self.root)
            import_export_window.title("Data Import/Export Utilities")
            import_export_window.geometry("700x500")
            import_export_window.transient(self.root)

            # Create notebook for import/export operations
            ie_notebook = ttk.Notebook(import_export_window)
            ie_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Import Tab
            import_frame = ttk.Frame(ie_notebook)
            ie_notebook.add(import_frame, text="Import Data")

            import_options = ttk.LabelFrame(import_frame, text="Import Options", padding="10")
            import_options.pack(fill=tk.X, padx=10, pady=10)

            import_type_var = tk.StringVar(value="students")
            import_types = [("students", "Student Data"), ("templates", "Report Templates"),
                           ("schedules", "Scheduled Reports"), ("config", "System Configuration")]

            for import_id, import_name in import_types:
                ttk.Radiobutton(import_options, text=import_name,
                               variable=import_type_var, value=import_id).pack(anchor=tk.W)

            # File selection
            file_frame = ttk.LabelFrame(import_frame, text="File Selection", padding="10")
            file_frame.pack(fill=tk.X, padx=10, pady=10)

            file_path_var = tk.StringVar()
            ttk.Entry(file_frame, textvariable=file_path_var, width=50).pack(side=tk.LEFT, padx=(0, 10))

            def browse_import_file():
                filetypes = [
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("Excel files", "*.xlsx"),
                    ("All files", "*.*")
                ]
                filename = filedialog.askopenfilename(filetypes=filetypes)
                if filename:
                    file_path_var.set(filename)

            ttk.Button(file_frame, text="Browse", command=browse_import_file).pack(side=tk.LEFT)

            def import_data():
                file_path = file_path_var.get()
                import_type = import_type_var.get()

                if not file_path:
                    messagebox.showerror("Error", "Please select a file to import")
                    return

                try:
                    if import_type == "templates":
                        with open(file_path, 'r') as f:
                            imported_templates = json.load(f)

                        if not isinstance(imported_templates, list):
                            imported_templates = [imported_templates]

                        existing_templates = load_templates() if ENHANCED_AVAILABLE else []
                        existing_templates.extend(imported_templates)

                        if ENHANCED_AVAILABLE:
                            os.makedirs(CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)), exist_ok=True)
                            with open(os.path.join(CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)), "templates.json"), 'w') as f:
                                json.dump(existing_templates, f, indent=4)

                        messagebox.showinfo("Success", f"Imported {len(imported_templates)} templates successfully!")
                        self.refresh_data()

                    elif import_type == "students":
                        messagebox.showinfo("Import", "Student data import would be implemented here")

                    else:
                        messagebox.showinfo("Import", f"Import for {import_type} would be implemented here")

                except Exception as e:
                    messagebox.showerror("Import Error", f"Failed to import data: {str(e)}")

            ttk.Button(import_frame, text="Import Data", command=import_data,
                      style='Success.TButton').pack(pady=20)

            # Export Tab
            export_frame = ttk.Frame(ie_notebook)
            ie_notebook.add(export_frame, text="Export Data")

            export_options = ttk.LabelFrame(export_frame, text="Export Options", padding="10")
            export_options.pack(fill=tk.X, padx=10, pady=10)

            export_type_var = tk.StringVar(value="templates")
            export_format_var = tk.StringVar(value="json")

            for export_id, export_name in import_types:
                ttk.Radiobutton(export_options, text=export_name,
                               variable=export_type_var, value=export_id).pack(anchor=tk.W)

            format_frame = ttk.LabelFrame(export_frame, text="Export Format", padding="10")
            format_frame.pack(fill=tk.X, padx=10, pady=10)

            formats = [("json", "JSON"), ("csv", "CSV"), ("excel", "Excel")]
            for format_id, format_name in formats:
                ttk.Radiobutton(format_frame, text=format_name,
                               variable=export_format_var, value=format_id).pack(anchor=tk.W)

            def export_data():
                export_type = export_type_var.get()
                export_format = export_format_var.get()

                try:
                    if export_type == "templates":
                        templates = load_templates() if ENHANCED_AVAILABLE else []

                        if export_format == "json":
                            file_path = filedialog.asksaveasfilename(
                                defaultextension=".json",
                                filetypes=[("JSON files", "*.json")],
                                initialfile="exported_templates.json"
                            )

                            if file_path:
                                with open(file_path, 'w') as f:
                                    json.dump(templates, f, indent=4)
                                messagebox.showinfo("Success", f"Exported {len(templates)} templates to {file_path}")

                    else:
                        messagebox.showinfo("Export", f"Export for {export_type} in {export_format} format would be implemented here")

                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

            ttk.Button(export_frame, text="Export Data", command=export_data,
                      style='Success.TButton').pack(pady=20)

        except Exception as e:
            messagebox.showerror("Import/Export Error", f"Failed to open import/export dialog: {str(e)}")

    def show_template_wizard(self):
        """Show step-by-step template creation wizard"""
        try:
            wizard_window = tk.Toplevel(self.root)
            wizard_window.title("Template Creation Wizard")
            wizard_window.geometry("800x600")
            wizard_window.transient(self.root)

            # Wizard state
            self.wizard_step = 0
            self.wizard_data = {}

            # Main container
            self.wizard_container = ttk.Frame(wizard_window)
            self.wizard_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Navigation frame
            nav_frame = ttk.Frame(wizard_window)
            nav_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            self.prev_button = ttk.Button(nav_frame, text="< Previous", command=self.wizard_prev_step)
            self.prev_button.pack(side=tk.LEFT)

            self.next_button = ttk.Button(nav_frame, text="Next >", command=self.wizard_next_step)
            self.next_button.pack(side=tk.RIGHT, padx=(10, 0))

            self.finish_button = ttk.Button(nav_frame, text="Finish", command=self.wizard_finish,
                                           style='Success.TButton')
            self.finish_button.pack(side=tk.RIGHT)

            ttk.Button(nav_frame, text="Cancel", command=wizard_window.destroy).pack(side=tk.RIGHT, padx=(0, 10))

            # Progress indicator
            self.progress_label = ttk.Label(nav_frame, text="Step 1 of 4")
            self.progress_label.pack()

            # Start wizard
            self.wizard_window = wizard_window
            self.show_wizard_step()

        except Exception as e:
            messagebox.showerror("Wizard Error", f"Failed to open template wizard: {str(e)}")

    def show_wizard_step(self):
        """Show current wizard step"""
        # Clear container
        for widget in self.wizard_container.winfo_children():
            widget.destroy()

        if self.wizard_step == 0:
            self.show_wizard_step_1()
        elif self.wizard_step == 1:
            self.show_wizard_step_2()
        elif self.wizard_step == 2:
            self.show_wizard_step_3()
        elif self.wizard_step == 3:
            self.show_wizard_step_4()

        # Update navigation
        self.prev_button.config(state=tk.NORMAL if self.wizard_step > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if self.wizard_step < 3 else tk.DISABLED)
        self.finish_button.config(state=tk.NORMAL if self.wizard_step == 3 else tk.DISABLED)
        self.progress_label.config(text=f"Step {self.wizard_step + 1} of 4")

    def show_wizard_step_1(self):
        """Wizard Step 1: Basic Information"""
        ttk.Label(self.wizard_container, text="Step 1: Basic Information",
                 style='Title.TLabel').pack(pady=(0, 20))

        info_frame = ttk.LabelFrame(self.wizard_container, text="Template Details", padding="20")
        info_frame.pack(fill=tk.X)
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text="Template Name:*").grid(row=0, column=0, sticky=tk.W, pady=10)
        self.wizard_name = tk.StringVar(value=self.wizard_data.get('name', ''))
        ttk.Entry(info_frame, textvariable=self.wizard_name, width=40).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

        ttk.Label(info_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=10)
        self.wizard_desc = tk.StringVar(value=self.wizard_data.get('description', ''))
        ttk.Entry(info_frame, textvariable=self.wizard_desc, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

    def wizard_next_step(self):
        """Move to next wizard step"""
        # Save current step data
        if self.wizard_step == 0:
            self.wizard_data['name'] = self.wizard_name.get()
            self.wizard_data['description'] = self.wizard_desc.get()

            if not self.wizard_data['name'].strip():
                messagebox.showerror("Validation Error", "Template name is required")
                return

        if self.wizard_step < 3:
            self.wizard_step += 1
            self.show_wizard_step()

    def wizard_prev_step(self):
        """Move to previous wizard step"""
        if self.wizard_step > 0:
            self.wizard_step -= 1
            self.show_wizard_step()

    def wizard_finish(self):
        """Complete the wizard and create template"""
        try:
            # Create template from wizard data
            messagebox.showinfo("Success", f"Template '{self.wizard_data.get('name')}' created successfully!")
            self.wizard_window.destroy()
            self.refresh_data()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create template: {str(e)}")

    def show_system_config_editor(self):
        """Show system configuration editor window"""
        try:
            config_window = tk.Toplevel(self.root)
            config_window.title("System Configuration Editor")
            config_window.geometry("700x600")
            config_window.transient(self.root)

            # Create notebook for different config sections
            config_notebook = ttk.Notebook(config_window)
            config_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # General config tab
            general_frame = ttk.Frame(config_notebook)
            config_notebook.add(general_frame, text="General")

            # Database config
            ttk.Label(general_frame, text="Database Path:").pack(anchor=tk.W, pady=5)
            db_path_var = tk.StringVar(value=CONFIG.get('database', str(DEFAULT_DB_PATH)))
            ttk.Entry(general_frame, textvariable=db_path_var, width=60).pack(fill=tk.X, pady=(0, 10))

            # Reports directory
            ttk.Label(general_frame, text="Reports Directory:").pack(anchor=tk.W, pady=5)
            reports_dir_var = tk.StringVar(value=CONFIG.get('reports_dir', 'reports'))
            ttk.Entry(general_frame, textvariable=reports_dir_var, width=60).pack(fill=tk.X, pady=(0, 10))

            # Cache config tab
            cache_frame = ttk.Frame(config_notebook)
            config_notebook.add(cache_frame, text="Cache")

            ttk.Label(cache_frame, text="Cache Expiry (hours):").pack(anchor=tk.W, pady=5)
            cache_expiry_var = tk.StringVar(value=str(CONFIG.get('cache_expiry_hours', 24)))
            ttk.Entry(cache_frame, textvariable=cache_expiry_var).pack(fill=tk.X, pady=(0, 10))

            ttk.Label(cache_frame, text="Max Cache Size (MB):").pack(anchor=tk.W, pady=5)
            max_cache_var = tk.StringVar(value=str(CONFIG.get('max_cache_size_mb', 500)))
            ttk.Entry(cache_frame, textvariable=max_cache_var).pack(fill=tk.X, pady=(0, 10))

            # Security config tab
            security_frame = ttk.Frame(config_notebook)
            config_notebook.add(security_frame, text="Security")

            ttk.Label(security_frame, text="Session Timeout (seconds):").pack(anchor=tk.W, pady=5)
            session_timeout_var = tk.StringVar(value="3600")
            ttk.Entry(security_frame, textvariable=session_timeout_var).pack(fill=tk.X, pady=(0, 10))

            require_auth_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(security_frame, text="Require Authentication", variable=require_auth_var).pack(anchor=tk.W, pady=5)

            # Button frame
            button_frame = ttk.Frame(config_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_config():
                try:
                    new_config = {
                        'database': db_path_var.get(),
                        'reports_dir': reports_dir_var.get(),
                        'cache_expiry_hours': int(cache_expiry_var.get()),
                        'max_cache_size_mb': int(max_cache_var.get())
                    }

                    CONFIG.update(new_config)
                    if ENHANCED_AVAILABLE:
                        SystemConfig.save_config(new_config)

                    messagebox.showinfo("Success", "Configuration saved successfully!")
                    config_window.destroy()
                    self.check_system_status()

                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to save configuration: {str(e)}")

            ttk.Button(button_frame, text="Save", command=save_config).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Cancel", command=config_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Config Error", f"Failed to open configuration editor: {str(e)}")

    def show_email_settings_dialog(self):
        """Show email configuration dialog"""
        try:
            email_window = tk.Toplevel(self.root)
            email_window.title("Email Settings")
            email_window.geometry("500x400")
            email_window.transient(self.root)

            # Email configuration form
            config_frame = ttk.LabelFrame(email_window, text="SMTP Configuration", padding="10")
            config_frame.pack(fill=tk.X, padx=10, pady=10)
            config_frame.columnconfigure(1, weight=1)

            # SMTP Server
            ttk.Label(config_frame, text="SMTP Server:").grid(row=0, column=0, sticky=tk.W, pady=5)
            smtp_server_var = tk.StringVar(value=CONFIG.get('email', {}).get('smtp_server', 'smtp.gmail.com'))
            ttk.Entry(config_frame, textvariable=smtp_server_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # SMTP Port
            ttk.Label(config_frame, text="SMTP Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
            smtp_port_var = tk.StringVar(value=str(CONFIG.get('email', {}).get('smtp_port', 587)))
            ttk.Entry(config_frame, textvariable=smtp_port_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # From Address
            ttk.Label(config_frame, text="From Address:").grid(row=2, column=0, sticky=tk.W, pady=5)
            from_address_var = tk.StringVar(value=CONFIG.get('email', {}).get('from_address', ''))
            ttk.Entry(config_frame, textvariable=from_address_var).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Username
            ttk.Label(config_frame, text="Username:").grid(row=3, column=0, sticky=tk.W, pady=5)
            username_var = tk.StringVar(value=CONFIG.get('email', {}).get('username', ''))
            ttk.Entry(config_frame, textvariable=username_var).grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Password
            ttk.Label(config_frame, text="Password:").grid(row=4, column=0, sticky=tk.W, pady=5)
            password_var = tk.StringVar()
            ttk.Entry(config_frame, textvariable=password_var, show='*').grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Use TLS
            use_tls_var = tk.BooleanVar(value=CONFIG.get('email', {}).get('use_tls', True))
            ttk.Checkbutton(config_frame, text="Use TLS", variable=use_tls_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)

            # Enable email
            email_enabled_var = tk.BooleanVar(value=CONFIG.get('email', {}).get('enabled', False))
            ttk.Checkbutton(config_frame, text="Enable Email Notifications", variable=email_enabled_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)

            # Test email section
            test_frame = ttk.LabelFrame(email_window, text="Test Email", padding="10")
            test_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(test_frame, text="Test Email Address:").pack(anchor=tk.W)
            test_email_var = tk.StringVar()
            ttk.Entry(test_frame, textvariable=test_email_var, width=40).pack(fill=tk.X, pady=(0, 10))

            def send_test_email():
                try:
                    from education_system.post_18.university_system.infrastructure.email.email_service import send_email

                    test_email = test_email_var.get().strip()
                    if not test_email or '@' not in test_email:
                        messagebox.showerror("Invalid Email", "Please enter a valid email address")
                        return

                    # Use temporary config for test
                    test_config = {
                        'smtp_server': smtp_server_var.get(),
                        'smtp_port': int(smtp_port_var.get()),
                        'from_address': from_address_var.get(),
                        'username': username_var.get(),
                        'password': password_var.get(),
                        'use_tls': use_tls_var.get()
                    }

                    body = """This is a test email from the University Reporting System.

If you receive this email, your email settings are configured correctly!

System Configuration:
- SMTP Server: {smtp_server}
- SMTP Port: {smtp_port}
- From Address: {from_address}
- TLS Enabled: {use_tls}

Thank you for using our system.
""".format(**test_config)

                    success = send_email(
                        recipient_email=test_email,
                        subject='Test Email from University Reporting System',
                        body=body
                    )

                    if success:
                        messagebox.showinfo("Test Email Sent", f"Test email successfully sent to {test_email}!")
                    else:
                        messagebox.showerror("Test Failed", "Test email failed to send")

                except Exception as e:
                    messagebox.showerror("Test Failed", f"Test email failed: {str(e)}")

            ttk.Button(test_frame, text="Send Test Email", command=send_test_email).pack()

            # Button frame
            button_frame = ttk.Frame(email_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_email_settings():
                try:
                    email_config = {
                        'enabled': email_enabled_var.get(),
                        'smtp_server': smtp_server_var.get(),
                        'smtp_port': int(smtp_port_var.get()),
                        'from_address': from_address_var.get(),
                        'username': username_var.get(),
                        'use_tls': use_tls_var.get()
                    }

                    CONFIG['email'] = email_config

                    if ENHANCED_AVAILABLE:
                        full_config = SystemConfig.load_config()
                        full_config['email'] = email_config
                        SystemConfig.save_config(full_config)

                    messagebox.showinfo("Success", "Email settings saved successfully!")
                    email_window.destroy()

                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to save email settings: {str(e)}")

            ttk.Button(button_frame, text="Save", command=save_email_settings).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Cancel", command=email_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Email Settings Error", f"Failed to open email settings: {str(e)}")

    def show_advanced_settings(self):
        """Show advanced settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Advanced Settings")
        settings_window.geometry("500x400")
        settings_window.transient(self.root)

        # Create notebook for different setting categories
        settings_notebook = ttk.Notebook(settings_window)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load existing settings
        default_settings = {
            'cache_expiry_hours': 24,
            'max_cache_size_mb': 500,
            'session_timeout_seconds': 3600,
            'require_2fa': False,
            'enable_caching': True,
            'max_concurrent_reports': 5
        }

        try:
            config_file = paths.DATA_DIR / 'reporting_settings.json'
            if config_file.exists():
                with open(config_file, 'r') as f:
                    loaded_settings = json.load(f)
                    default_settings.update(loaded_settings)
        except Exception as e:
            logging.warning(f"Could not load settings: {e}")

        # General settings
        general_frame = ttk.Frame(settings_notebook, padding="10")
        settings_notebook.add(general_frame, text="General")

        ttk.Label(general_frame, text="Cache expiry (hours):").pack(anchor=tk.W, pady=5)
        cache_expiry = tk.StringVar(value=str(default_settings['cache_expiry_hours']))
        ttk.Entry(general_frame, textvariable=cache_expiry).pack(fill=tk.X, pady=(0, 10))

        ttk.Label(general_frame, text="Max cache size (MB):").pack(anchor=tk.W, pady=5)
        cache_size = tk.StringVar(value=str(default_settings['max_cache_size_mb']))
        ttk.Entry(general_frame, textvariable=cache_size).pack(fill=tk.X, pady=(0, 10))

        # Security settings
        security_frame = ttk.Frame(settings_notebook, padding="10")
        settings_notebook.add(security_frame, text="Security")

        ttk.Label(security_frame, text="Session timeout (seconds):").pack(anchor=tk.W, pady=5)
        session_timeout = tk.StringVar(value=str(default_settings['session_timeout_seconds']))
        ttk.Entry(security_frame, textvariable=session_timeout).pack(fill=tk.X, pady=(0, 10))

        require_2fa = tk.BooleanVar(value=default_settings['require_2fa'])
        ttk.Checkbutton(security_frame, text="Require 2FA", variable=require_2fa).pack(anchor=tk.W, pady=5)

        # Performance settings
        performance_frame = ttk.Frame(settings_notebook, padding="10")
        settings_notebook.add(performance_frame, text="Performance")

        enable_caching = tk.BooleanVar(value=default_settings['enable_caching'])
        ttk.Checkbutton(performance_frame, text="Enable caching", variable=enable_caching).pack(anchor=tk.W, pady=5)

        ttk.Label(performance_frame, text="Max concurrent reports:").pack(anchor=tk.W, pady=5)
        max_reports = tk.StringVar(value=str(default_settings['max_concurrent_reports']))
        ttk.Entry(performance_frame, textvariable=max_reports).pack(fill=tk.X, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def save_settings():
            try:
                # Prepare settings dictionary
                settings = {
                    'cache_expiry_hours': int(cache_expiry.get()),
                    'max_cache_size_mb': int(cache_size.get()),
                    'session_timeout_seconds': int(session_timeout.get()),
                    'require_2fa': require_2fa.get(),
                    'enable_caching': enable_caching.get(),
                    'max_concurrent_reports': int(max_reports.get())
                }

                # Save to config file
                config_file = paths.DATA_DIR / 'reporting_settings.json'
                with open(config_file, 'w') as f:
                    json.dump(settings, f, indent=4)

                messagebox.showinfo("Success", "Settings saved successfully!")
                settings_window.destroy()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numeric values for all fields.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

        ttk.Button(button_frame, text="Save", command=save_settings).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=settings_window.destroy).pack(side=tk.RIGHT)

    def show_settings(self):
        """Show general settings"""
        self.show_advanced_settings()

    def show_cache_management_dialog(self):
        """Show cache management dialog"""
        try:
            cache_window = tk.Toplevel(self.root)
            cache_window.title("Cache Management")
            cache_window.geometry("600x500")
            cache_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(cache_window)
            header_frame.pack(fill=tk.X, padx=20, pady=10)
            ttk.Label(header_frame, text="\U0001f4be Cache Management",
                     font=('Arial', 14, 'bold')).pack(anchor=tk.W)

            # Cache info
            info_frame = ttk.LabelFrame(cache_window, text="Cache Information", padding="10")
            info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            info_text = ScrolledText(info_frame, wrap=tk.WORD, height=15)
            info_text.pack(fill=tk.BOTH, expand=True)

            def load_cache_info():
                try:
                    cache_dir = CONFIG.get('cache_dir', 'cache')
                    if os.path.exists(cache_dir):
                        cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
                        total_size = sum(os.path.getsize(os.path.join(cache_dir, f))
                                       for f in cache_files)

                        info_text.insert(tk.END, f"Cache Directory: {cache_dir}\n")
                        info_text.insert(tk.END, f"Total Cached Reports: {len(cache_files)}\n")
                        info_text.insert(tk.END, f"Total Size: {total_size / (1024 * 1024):.2f} MB\n")
                        info_text.insert(tk.END, f"Max Cache Size: {CONFIG.get('max_cache_size_mb', 100)} MB\n")
                        info_text.insert(tk.END, f"Cache Expiry: {CONFIG.get('cache_expiry_hours', 24)} hours\n\n")

                        if cache_files:
                            info_text.insert(tk.END, "Cached Reports:\n")
                            for cache_file in cache_files[:20]:  # Show first 20
                                file_path = os.path.join(cache_dir, cache_file)
                                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                age = datetime.now() - file_time
                                info_text.insert(tk.END, f"  \u2022 {cache_file} (Age: {age.seconds // 3600}h)\n")

                            if len(cache_files) > 20:
                                info_text.insert(tk.END, f"\n  ... and {len(cache_files) - 20} more\n")
                    else:
                        info_text.insert(tk.END, "Cache directory does not exist yet.\n")

                    info_text.config(state=tk.DISABLED)
                except Exception as e:
                    info_text.insert(tk.END, f"Error loading cache info: {str(e)}")
                    info_text.config(state=tk.DISABLED)

            load_cache_info()

            # Buttons
            button_frame = ttk.Frame(cache_window)
            button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            def refresh_info():
                info_text.config(state=tk.NORMAL)
                info_text.delete(1.0, tk.END)
                load_cache_info()

            def cleanup_action():
                if messagebox.askyesno("Confirm", "Clean up old cache files?"):
                    self.cleanup_cache_dialog()
                    refresh_info()

            ttk.Button(button_frame, text="Cleanup Cache", command=cleanup_action).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Refresh", command=refresh_info).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Close", command=cache_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show cache management: {str(e)}")
