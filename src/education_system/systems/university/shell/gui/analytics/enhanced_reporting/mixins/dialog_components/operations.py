"""Operations dialogs extracted from DialogsMixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ._shared import *  # noqa: F401,F403
from education_system.platform.delivery.gui.tk_threads import start_thread, ui


class OperationsDialogsMixin:
    def show_enhanced_scheduling_dialog(self):
        """Show enhanced scheduling dialog with all CLI features"""
        try:
            schedule_window = tk.Toplevel(self.root)
            schedule_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.windows.enhanced_report_scheduling', default="Enhanced Report Scheduling"))
            schedule_window.geometry("700x600")
            schedule_window.transient(self.root)

            # Create notebook for different scheduling aspects
            schedule_notebook = ttk.Notebook(schedule_window)
            schedule_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Basic Scheduling Tab
            basic_frame = ttk.Frame(schedule_notebook)
            schedule_notebook.add(basic_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.tabs.basic_schedule', default="Basic Schedule"))

            # Template selection
            template_frame = ttk.LabelFrame(basic_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.template_selection', default="Template Selection"), padding="10")
            template_frame.pack(fill=tk.X, padx=10, pady=10)

            templates = load_templates() if ENHANCED_AVAILABLE else []
            if not templates:
                ttk.Label(template_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.no_templates_available_for_scheduling', default="No templates available for scheduling")).pack()
                return

            ttk.Label(template_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.select_template', default="Select Template:")).pack(anchor=tk.W)
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(template_frame, textvariable=template_var, state="readonly")
            template_combo['values'] = [t['name'] for t in templates]
            template_combo.pack(fill=tk.X, pady=(5, 0))

            if templates:
                template_combo.set(templates[0]['name'])

            # Schedule configuration
            config_frame = ttk.LabelFrame(basic_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.schedule_configuration', default="Schedule Configuration"), padding="10")
            config_frame.pack(fill=tk.X, padx=10, pady=10)
            config_frame.columnconfigure(1, weight=1)

            ttk.Label(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.frequency', default="Frequency:")).grid(row=0, column=0, sticky=tk.W, pady=5)
            frequency_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.values.weekly', default="weekly"))
            frequency_combo = ttk.Combobox(config_frame, textvariable=frequency_var,
                                          values=["daily", "weekly", "monthly"], state="readonly")
            frequency_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            ttk.Label(config_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.hour_0_23', default="Hour (0-23):")).grid(row=1, column=0, sticky=tk.W, pady=5)
            hour_var = tk.StringVar(value="9")
            hour_spin = ttk.Spinbox(config_frame, from_=0, to=23, textvariable=hour_var, width=5)
            hour_spin.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

            # Recipients Tab
            recipients_frame = ttk.Frame(schedule_notebook)
            schedule_notebook.add(recipients_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.tabs.recipients', default="Recipients"))

            recipients_info = ttk.LabelFrame(recipients_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.email_recipients', default="Email Recipients"), padding="10")
            recipients_info.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Label(recipients_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.enter_email_addresses_one_per_line', default="Enter email addresses (one per line):")).pack(anchor=tk.W)
            recipients_text = tk.Text(recipients_info, height=10, width=50)
            recipients_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

            # Conditions Tab
            conditions_frame = ttk.Frame(schedule_notebook)
            schedule_notebook.add(conditions_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.tabs.conditions', default="Conditions"))

            conditions_info = ttk.LabelFrame(conditions_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.execution_conditions', default="Execution Conditions"), padding="10")
            conditions_info.pack(fill=tk.X, padx=10, pady=10)

            only_if_data_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(conditions_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.only_run_if_new_data_is_available', default="Only run if new data is available"),
                           variable=only_if_data_var).pack(anchor=tk.W, pady=2)

            skip_if_empty_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(conditions_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.skip_if_no_students_found', default="Skip if no students found"),
                           variable=skip_if_empty_var).pack(anchor=tk.W, pady=2)

            retry_on_failure_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(conditions_info, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.retry_on_failure', default="Retry on failure"),
                           variable=retry_on_failure_var).pack(anchor=tk.W, pady=2)

            def create_enhanced_schedule():
                try:
                    template_name = template_var.get()
                    if not template_name:
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.error', default="Error"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.please_select_a_template', default="Please select a template"))
                        return

                    # Validate hour
                    try:
                        hour = int(hour_var.get())
                        if not (0 <= hour <= 23):
                            raise ValueError("Hour must be between 0 and 23")
                    except ValueError as e:
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.error', default="Error"), f"Invalid hour: {str(e)}")
                        return

                    # Get recipients
                    recipients_input = recipients_text.get(1.0, tk.END).strip()
                    recipients = [email.strip() for email in recipients_input.split('\n')
                                 if email.strip() and '@' in email]

                    if not recipients:
                        if not messagebox.askyesno(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.no_recipients', default="No Recipients"),
                                                 _t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.no_email_recipients_specified_report_will_be_generated_but_not_s', default="No email recipients specified. Report will be generated but not sent. Continue?")):
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

                        messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.success', default="Success"),
                                          f"Enhanced schedule created for '{template_name}'!\n\n"
                                          f"Frequency: {frequency_var.get().title()}\n"
                                          f"Time: {hour:02d}:00\n"
                                          f"Recipients: {len(recipients)}")

                        schedule_window.destroy()
                        self.refresh_data()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.error', default="Error"), f"Failed to create schedule: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(schedule_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.create_schedule', default="Create Schedule"), command=create_enhanced_schedule,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.cancel', default="Cancel"), command=schedule_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.scheduling_error', default="Scheduling Error"), f"Failed to open scheduling dialog: {str(e)}")

    def show_bulk_operations_dialog(self):
        """Show bulk operations for templates and reports"""
        try:
            bulk_window = tk.Toplevel(self.root)
            bulk_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.windows.bulk_operations', default="Bulk Operations"))
            bulk_window.geometry("600x500")
            bulk_window.transient(self.root)

            # Operation selection
            operation_frame = ttk.LabelFrame(bulk_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.select_operation', default="Select Operation"), padding="10")
            operation_frame.pack(fill=tk.X, padx=10, pady=10)

            operation_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.values.export_templates', default="export_templates"))

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
            options_frame = ttk.LabelFrame(bulk_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.options', default="Options"), padding="10")
            options_frame.pack(fill=tk.X, padx=10, pady=10)

            include_data_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.include_data_files', default="Include data files"),
                           variable=include_data_var).pack(anchor=tk.W)

            confirm_actions_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.confirm_each_action', default="Confirm each action"),
                           variable=confirm_actions_var).pack(anchor=tk.W)

            # Progress display
            progress_frame = ttk.LabelFrame(bulk_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.progress', default="Progress"), padding="10")
            progress_frame.pack(fill=tk.X, padx=10, pady=10)

            progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
            progress_bar.pack(fill=tk.X, pady=(0, 5))

            progress_label = ttk.Label(progress_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.ready', default="Ready"))
            progress_label.pack(anchor=tk.W)

            # Results display
            results_frame = ttk.LabelFrame(bulk_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.results', default="Results"), padding="10")
            results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            results_text = ScrolledText(results_frame, height=8, wrap=tk.WORD)
            results_text.pack(fill=tk.BOTH, expand=True)

            def execute_bulk_operation():
                operation = operation_var.get()
                results_text.delete(1.0, tk.END)

                # Dialogs must run on the Tk main thread: ask before starting the worker.
                export_dir = None
                if operation == "export_templates":
                    export_dir = filedialog.askdirectory(title=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.select_export_directory', default="Select Export Directory"))
                    if not export_dir:
                        return

                def bulk_task():
                    try:
                        if operation == "export_templates":
                            templates = load_templates() if ENHANCED_AVAILABLE else []
                            ui(progress_bar, progress_bar.configure, maximum=len(templates))

                            for i, template in enumerate(templates):
                                filename = f"{template['name'].replace(' ', '_')}_template.json"
                                filepath = os.path.join(export_dir, filename)

                                with open(filepath, 'w') as f:
                                    json.dump(template, f, indent=4)

                                ui(progress_bar, progress_bar.configure, value=i + 1)
                                ui(progress_label, progress_label.config, text=f"Exported: {template['name']}")
                                time.sleep(0.1)

                            ui(results_text, results_text.insert, tk.END, f"Successfully exported {len(templates)} templates to {export_dir}")

                        elif operation == "generate_all_reports":
                            templates = load_templates() if ENHANCED_AVAILABLE else []
                            ui(progress_bar, progress_bar.configure, maximum=len(templates))

                            end_date = datetime.now().strftime("%Y-%m-%d")
                            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

                            for i, template in enumerate(templates):
                                try:
                                    report_path = generate_report(template['name'], start_date, end_date, 'pdf')
                                    if report_path:
                                        ui(results_text, results_text.insert, tk.END, f"✓ Generated: {template['name']}\n")
                                    else:
                                        ui(results_text, results_text.insert, tk.END, f"✗ Failed: {template['name']}\n")
                                except Exception as e:
                                    ui(results_text, results_text.insert, tk.END, f"✗ Error in {template['name']}: {str(e)}\n")

                                ui(progress_bar, progress_bar.configure, value=i + 1)
                                ui(progress_label, progress_label.config, text=f"Processing: {template['name']}")
                                ui(results_text, results_text.see, tk.END)
                                time.sleep(0.5)

                        ui(progress_label, progress_label.config, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.text.operation_completed', default="Operation completed"))

                    except Exception as e:
                        ui(results_text, results_text.insert, tk.END, f"Error: {str(e)}")

                start_thread(results_text, bulk_task)

            # Buttons
            button_frame = ttk.Frame(bulk_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.execute', default="Execute"), command=execute_bulk_operation,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.close', default="Close"), command=bulk_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.bulk_operations_error', default="Bulk Operations Error"), f"Failed to open bulk operations: {str(e)}")

    def show_data_import_export_dialog(self):
        """Show data import/export utilities dialog"""
        try:
            import_export_window = tk.Toplevel(self.root)
            import_export_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.windows.data_import_export_utilities', default="Data Import/Export Utilities"))
            import_export_window.geometry("700x500")
            import_export_window.transient(self.root)

            # Create notebook for import/export operations
            ie_notebook = ttk.Notebook(import_export_window)
            ie_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Import Tab
            import_frame = ttk.Frame(ie_notebook)
            ie_notebook.add(import_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.tabs.import_data', default="Import Data"))

            import_options = ttk.LabelFrame(import_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.import_options', default="Import Options"), padding="10")
            import_options.pack(fill=tk.X, padx=10, pady=10)

            import_type_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.values.students', default="students"))
            import_types = [("students", "Student Data"), ("courses", "Course Data"),
                           ("modules", "Module Data"), ("templates", "Report Templates"),
                           ("schedules", "Scheduled Reports"), ("config", "System Configuration")]

            for import_id, import_name in import_types:
                ttk.Radiobutton(import_options, text=import_name,
                               variable=import_type_var, value=import_id).pack(anchor=tk.W)

            # File selection
            file_frame = ttk.LabelFrame(import_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.file_selection', default="File Selection"), padding="10")
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

            ttk.Button(file_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.browse', default="Browse"), command=browse_import_file).pack(side=tk.LEFT)

            def import_data():
                file_path = file_path_var.get()
                import_type = import_type_var.get()

                if not file_path:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.error', default="Error"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.please_select_a_file_to_import', default="Please select a file to import"))
                    return

                try:
                    if import_type == "templates":
                        from education_system.systems.university.shell.gui.analytics.enhanced_reporting.tabular_io import read_records
                        imported_templates = read_records(file_path)

                        existing_templates = load_templates() if ENHANCED_AVAILABLE else []
                        existing_templates.extend(imported_templates)

                        if ENHANCED_AVAILABLE:
                            os.makedirs(CONFIG.get('templates_dir', str(paths.UNIVERSITY_REPORT_TEMPLATES_DIR)), exist_ok=True)
                            with open(os.path.join(CONFIG.get('templates_dir', str(paths.UNIVERSITY_REPORT_TEMPLATES_DIR)), "templates.json"), 'w') as f:
                                json.dump(existing_templates, f, indent=4)

                        messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.success', default="Success"), f"Imported {len(imported_templates)} templates successfully!")
                        self.refresh_data()

                    elif import_type in {"students", "courses", "modules"}:
                        from education_system.systems.university.shell.gui.analytics.enhanced_reporting.tabular_io import import_table
                        count = import_table(import_type, file_path)
                        messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.success', default="Success"), f"Imported {count} {import_type} record(s).")
                    elif import_type == "schedules":
                        from education_system.systems.university.shell.gui.analytics.enhanced_reporting.tabular_io import read_records
                        schedules = read_records(file_path)
                        save_scheduled_reports(schedules)
                        messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.success', default="Success"), f"Imported {len(schedules)} scheduled report(s).")
                    elif import_type == "config":
                        from education_system.systems.university.shell.gui.analytics.enhanced_reporting.tabular_io import read_records
                        config_rows = read_records(file_path)
                        imported_config = config_rows[0] if config_rows else {}
                        CONFIG.update(imported_config)
                        messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.success', default="Success"), f"Imported {len(imported_config)} configuration value(s).")

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.import_error', default="Import Error"), f"Failed to import data: {str(e)}")

            ttk.Button(import_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.import_data', default="Import Data"), command=import_data,
                      style='Success.TButton').pack(pady=20)

            # Export Tab
            export_frame = ttk.Frame(ie_notebook)
            ie_notebook.add(export_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.tabs.export_data', default="Export Data"))

            export_options = ttk.LabelFrame(export_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.export_options', default="Export Options"), padding="10")
            export_options.pack(fill=tk.X, padx=10, pady=10)

            export_type_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.values.templates', default="templates"))
            export_format_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.values.json', default="json"))

            for export_id, export_name in import_types:
                ttk.Radiobutton(export_options, text=export_name,
                               variable=export_type_var, value=export_id).pack(anchor=tk.W)

            format_frame = ttk.LabelFrame(export_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.labels.export_format', default="Export Format"), padding="10")
            format_frame.pack(fill=tk.X, padx=10, pady=10)

            formats = [("json", "JSON"), ("csv", "CSV"), ("excel", "Excel")]
            for format_id, format_name in formats:
                ttk.Radiobutton(format_frame, text=format_name,
                               variable=export_format_var, value=format_id).pack(anchor=tk.W)

            def export_data():
                export_type = export_type_var.get()
                export_format = export_format_var.get()

                try:
                    from education_system.systems.university.shell.gui.analytics.enhanced_reporting.tabular_io import table_records, write_records
                    if export_type == "templates":
                        records = load_templates() if ENHANCED_AVAILABLE else []
                    elif export_type in {"students", "courses", "modules"}:
                        records = table_records(export_type)
                    elif export_type == "schedules":
                        records = load_scheduled_reports()
                    else:
                        records = [CONFIG]
                    extension = {"json": ".json", "csv": ".csv", "excel": ".xlsx"}[export_format]
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=extension,
                        initialfile=f"{export_type}{extension}",
                    )
                    if file_path:
                        write_records(records, file_path, export_format)
                        messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.success', default="Success"), f"Exported {len(records)} record(s) to {file_path}")

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.export_error', default="Export Error"), f"Failed to export data: {str(e)}")

            ttk.Button(export_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.buttons.export_data', default="Export Data"), command=export_data,
                      style='Success.TButton').pack(pady=20)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.operations.dialogs.import_export_error', default="Import/Export Error"), f"Failed to open import/export dialog: {str(e)}")
