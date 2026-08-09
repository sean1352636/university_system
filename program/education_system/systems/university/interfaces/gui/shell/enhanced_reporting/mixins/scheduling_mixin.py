"""Scheduling methods mixin for the enhanced reporting GUI."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.standalone.constants import (
    tk, ttk, filedialog, messagebox,
    ScrolledText,
    threading, os, json, logging, time,
    schedule,
    datetime, timedelta,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
    _t,
    load_templates,
    load_scheduled_reports as _standalone_load_scheduled_reports,
    save_scheduled_reports as _standalone_save_scheduled_reports,
    generate_report,
    AdvancedScheduledReport,
)

logger = logging.getLogger(__name__)


class SchedulingMixin:
    """Mixin providing scheduling methods."""

    def load_scheduled_reports(self):
        """Load scheduled reports into the GUI"""
        if not ENHANCED_AVAILABLE:
            return

        try:
            scheduled_reports = _standalone_load_scheduled_reports()
            self.root.after(0, lambda: self._update_schedule_tree(scheduled_reports))
        except Exception as e:
            logger.error(f"Error loading scheduled reports: {str(e)}")

    def _update_schedule_tree(self, scheduled_reports):
        """Update schedule tree in main thread"""
        # Clear existing items
        for item in self.schedule_tree.get_children():
            self.schedule_tree.delete(item)

        self.scheduled_reports_data = scheduled_reports

        for report in scheduled_reports:
            config = report.get('schedule_config', {})
            status = "Enabled" if config.get('enabled', True) else "Disabled"

            values = (
                report['template_name'],
                config.get('frequency', 'Unknown').title(),
                f"{config.get('hour', 9):02d}:00",
                str(len(report.get('recipients', []))),
                report.get('last_run', 'Never')[:19] if report.get('last_run') else 'Never',
                status
            )

            self.schedule_tree.insert('', tk.END, values=values)

    def create_schedule(self):
        """Create a new scheduled report"""
        template_name = self.schedule_template_combo.get()
        if not template_name:
            messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.no_template', default="No Template"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.please_select_a_template_for_scheduling', default="Please select a template for scheduling."))
            return

        frequency = self.frequency_combo.get().lower()
        hour = int(self.hour_var.get())

        # Get recipients
        recipients_text = self.recipients_entry.get(1.0, tk.END).strip()
        recipients = [email.strip() for email in recipients_text.split('\n') if email.strip() and '@' in email]

        if not recipients:
            if not messagebox.askyesno(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.no_recipients', default="No Recipients"),
                                     _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.no_email_recipients_specified_report_will_be_generated_but_not_s', default="No email recipients specified. Report will be generated but not sent. Continue?")):
                return

        try:
            if ENHANCED_AVAILABLE:
                # Create schedule configuration
                schedule_config = {
                    'frequency': frequency,
                    'hour': hour,
                    'enabled': True,
                    'last_run': None,
                    'next_run': None
                }

                # Save scheduled report
                scheduled_report = AdvancedScheduledReport(
                    template_name=template_name,
                    schedule_config=schedule_config,
                    recipients=recipients
                )

                scheduled_reports = _standalone_load_scheduled_reports()
                scheduled_reports.append(scheduled_report.to_dict())
                _standalone_save_scheduled_reports(scheduled_reports)

                # Clear form
                self.recipients_entry.delete(1.0, tk.END)

                self.refresh_data()
                messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.success', default="Success"),
                                  f"✅ Report '{template_name}' scheduled for {frequency} generation at {hour:02d}:00\n\n📧 Recipients: {len(recipients)}")
            else:
                messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.feature_unavailable', default="Feature Unavailable"),
                                     _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.scheduling_requires_the_enhanced_system', default="Scheduling requires the enhanced system."))

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to create schedule: {str(e)}")

    def toggle_schedule(self):
        """Enable/disable selected schedule"""
        selection = self.schedule_tree.selection()
        if not selection or not hasattr(self, 'scheduled_reports_data'):
            messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.no_selection', default="No Selection"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.please_select_a_schedule_to_toggle', default="Please select a schedule to toggle."))
            return

        try:
            item_index = self.schedule_tree.index(selection[0])
            report_data = self.scheduled_reports_data[item_index]

            current_status = report_data['schedule_config'].get('enabled', True)
            report_data['schedule_config']['enabled'] = not current_status

            if ENHANCED_AVAILABLE:
                _standalone_save_scheduled_reports(self.scheduled_reports_data)

            self.refresh_data()

            new_status = "Enabled" if not current_status else "Disabled"
            messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.success', default="Success"), f"Schedule {new_status.lower()} successfully!")

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to toggle schedule: {str(e)}")

    def edit_schedule(self):
        """Edit selected schedule"""
        selection = self.schedule_tree.selection()
        if not selection or not hasattr(self, 'scheduled_reports_data'):
            messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.no_selection', default="No Selection"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.please_select_a_schedule_to_edit', default="Please select a schedule to edit."))
            return

        try:
            # Get selected schedule
            item_index = self.schedule_tree.index(selection[0])
            schedule_data = self.scheduled_reports_data[item_index].copy()

            # Create edit dialog
            edit_dialog = tk.Toplevel(self.root)
            edit_dialog.title(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.windows.edit_schedule', default="Edit Schedule"))
            edit_dialog.geometry("600x550")
            edit_dialog.transient(self.root)
            edit_dialog.grab_set()

            main_frame = ttk.Frame(edit_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.edit_report_schedule', default="Edit Report Schedule"), font=('Arial', 12, 'bold')).pack(pady=10)

            # Form frame
            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill='both', expand=True, pady=10)

            row = 0
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.report_template', default="Report Template:")).grid(row=row, column=0, sticky='w', pady=5)
            template_var = tk.StringVar(value=schedule_data.get('template_name', ''))
            template_combo = ttk.Combobox(form_frame, textvariable=template_var, width=40)
            template_combo.grid(row=row, column=1, pady=5, padx=10)

            # Load available templates
            try:
                if ENHANCED_AVAILABLE:
                    from education_system.systems.university.services.analytics.enhanced_reporting import load_templates as get_available_templates
                    templates = get_available_templates()
                    template_combo['values'] = list(templates.keys())
            except Exception:
                template_combo['values'] = ['enrollment_summary', 'financial_overview', 'student_performance', 'course_analytics']

            row += 1
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.schedule_type', default="Schedule Type:")).grid(row=row, column=0, sticky='w', pady=5)
            schedule_type_var = tk.StringVar(value=schedule_data.get('schedule_type', 'daily'))
            schedule_type_combo = ttk.Combobox(form_frame, textvariable=schedule_type_var,
                                              values=['daily', 'weekly', 'monthly'], width=40)
            schedule_type_combo.grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.time_hh_mm', default="Time (HH:MM):")).grid(row=row, column=0, sticky='w', pady=5)
            time_var = tk.StringVar(value=schedule_data.get('time', '09:00'))
            ttk.Entry(form_frame, textvariable=time_var, width=40).grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.format', default="Format:")).grid(row=row, column=0, sticky='w', pady=5)
            format_var = tk.StringVar(value=schedule_data.get('format', 'pdf'))
            format_combo = ttk.Combobox(form_frame, textvariable=format_var,
                                       values=['pdf', 'xlsx', 'html', 'csv'], width=40)
            format_combo.grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.email_recipients', default="Email Recipients:")).grid(row=row, column=0, sticky='nw', pady=5)
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.one_per_line', default="(One per line)"), font=('Arial', 8)).grid(row=row, column=1, sticky='w', pady=5, padx=10)

            row += 1
            recipients_text = tk.Text(form_frame, height=6, width=40)
            recipients_text.grid(row=row, column=1, pady=5, padx=10)
            if 'recipients' in schedule_data:
                recipients_text.insert('1.0', '\n'.join(schedule_data['recipients']))

            row += 1
            enabled_var = tk.BooleanVar(value=schedule_data.get('enabled', True))
            ttk.Checkbutton(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.schedule_enabled', default="Schedule Enabled"), variable=enabled_var).grid(row=row, column=1, sticky='w', pady=10, padx=10)

            row += 1
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.description', default="Description:")).grid(row=row, column=0, sticky='nw', pady=5)
            description_text = tk.Text(form_frame, height=4, width=40)
            description_text.grid(row=row, column=1, pady=5, padx=10)
            if 'description' in schedule_data:
                description_text.insert('1.0', schedule_data['description'])

            def save_schedule():
                try:
                    # Update schedule data
                    schedule_data['template_name'] = template_var.get()
                    schedule_data['schedule_type'] = schedule_type_var.get()
                    schedule_data['time'] = time_var.get()
                    schedule_data['format'] = format_var.get()
                    schedule_data['enabled'] = enabled_var.get()
                    schedule_data['description'] = description_text.get('1.0', tk.END).strip()

                    # Parse recipients
                    recipients_input = recipients_text.get('1.0', tk.END).strip()
                    schedule_data['recipients'] = [r.strip() for r in recipients_input.split('\n') if r.strip()]

                    # Update in list
                    self.scheduled_reports_data[item_index] = schedule_data

                    # Save to file
                    if ENHANCED_AVAILABLE:
                        from education_system.systems.university.services.analytics.enhanced_reporting import save_scheduled_reports
                        save_scheduled_reports(self.scheduled_reports_data)

                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.success', default="Success"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.schedule_updated_successfully', default="Schedule updated successfully!"))
                    edit_dialog.destroy()
                    self.refresh_data()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to save schedule: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.save', default="Save"), command=save_schedule).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.cancel', default="Cancel"), command=edit_dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to edit schedule: {str(e)}")

    def run_schedule_now(self):
        """Run selected schedule immediately"""
        selection = self.schedule_tree.selection()
        if not selection or not hasattr(self, 'scheduled_reports_data'):
            messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.no_selection', default="No Selection"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.please_select_a_schedule_to_run', default="Please select a schedule to run."))
            return

        try:
            item_index = self.schedule_tree.index(selection[0])
            report_data = self.scheduled_reports_data[item_index]
            template_name = report_data['template_name']

            self.update_status(f"Running scheduled report: {template_name}")
            self.start_progress()

            def run_task():
                try:
                    if ENHANCED_AVAILABLE:
                        end_date = datetime.now().strftime("%Y-%m-%d")
                        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

                        report_path = generate_report(template_name, start_date, end_date, 'pdf')

                        if report_path:
                            # Update run statistics
                            report_data['last_run'] = datetime.now().isoformat()
                            report_data['run_count'] = report_data.get('run_count', 0) + 1

                            _standalone_save_scheduled_reports(self.scheduled_reports_data)

                            self.root.after(0, lambda: [
                                self.stop_progress(),
                                self.update_status("Scheduled report completed"),
                                self.refresh_data(),
                                messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.success', default="Success"), f"✅ Scheduled report '{template_name}' generated successfully!\n\n📄 File: {os.path.basename(report_path)}")
                            ])
                        else:
                            self.root.after(0, lambda: [
                                self.stop_progress(),
                                self.update_status("Scheduled report failed", "error"),
                                messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to generate scheduled report '{template_name}'")
                            ])
                    else:
                        self.root.after(0, lambda: [
                            self.stop_progress(),
                            self.update_status("Feature unavailable", "warning"),
                            messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.feature_unavailable', default="Feature Unavailable"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.scheduling_requires_the_enhanced_system', default="Scheduling requires the enhanced system."))
                        ])

                except Exception as e:
                    _err = str(e)
                    self.root.after(0, lambda _e=_err: [
                        self.update_status(f"Error: {_e}", "error"),
                        messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Error running scheduled report: {_e}")
                    ])

            threading.Thread(target=run_task, daemon=True).start()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to run schedule: {str(e)}")

    def delete_schedule(self):
        """Delete selected schedule"""
        selection = self.schedule_tree.selection()
        if not selection or not hasattr(self, 'scheduled_reports_data'):
            messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.no_selection', default="No Selection"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.please_select_a_schedule_to_delete', default="Please select a schedule to delete."))
            return

        try:
            item_index = self.schedule_tree.index(selection[0])
            report_data = self.scheduled_reports_data[item_index]
            template_name = report_data['template_name']

            if messagebox.askyesno(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.confirm_delete', default="Confirm Delete"),
                                 f"Are you sure you want to delete the schedule for '{template_name}'?"):

                del self.scheduled_reports_data[item_index]

                if ENHANCED_AVAILABLE:
                    _standalone_save_scheduled_reports(self.scheduled_reports_data)

                self.refresh_data()
                messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.success', default="Success"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.schedule_deleted_successfully', default="Schedule deleted successfully!"))

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to delete schedule: {str(e)}")

    def save_scheduled_reports(self, scheduled_reports):
        """Save scheduled reports to file"""
        try:
            scheduled_file = os.path.join(
                CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)),
                'scheduled_reports.json'
            )

            with open(scheduled_file, 'w') as f:
                json.dump(scheduled_reports, f, indent=4)

            self.update_status("Scheduled reports saved successfully", "success")
            return True
        except Exception as e:
            logging.error(f"Error saving scheduled reports: {e}")
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to save scheduled reports: {str(e)}")
            return False

    def schedule_advanced_report_menu(self):
        """Show dialog for scheduling advanced reports"""
        try:
            schedule_window = tk.Toplevel(self.root)
            schedule_window.title(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.windows.schedule_advanced_report', default="Schedule Advanced Report"))
            schedule_window.geometry("600x700")
            schedule_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(schedule_window)
            header_frame.pack(fill=tk.X, padx=20, pady=10)
            ttk.Label(header_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.schedule_advanced_report', default="📅 Schedule Advanced Report"),
                     font=('Arial', 14, 'bold')).pack(anchor=tk.W)

            # Main form
            form_frame = ttk.LabelFrame(schedule_window, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.report_configuration', default="Report Configuration"), padding="10")
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # Template selection
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.template', default="Template:")).grid(row=0, column=0, sticky=tk.W, pady=5)
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(form_frame, textvariable=template_var, state='readonly')
            template_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)

            # Load templates
            try:
                templates = load_templates()
                template_names = [t.get('name', 'Unnamed') for t in templates]
                template_combo['values'] = template_names
                if template_names:
                    template_combo.current(0)
            except Exception:
                template_combo['values'] = []

            # Frequency
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.frequency', default="Frequency:")).grid(row=1, column=0, sticky=tk.W, pady=5)
            frequency_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.values.daily', default="daily"))
            frequency_combo = ttk.Combobox(form_frame, textvariable=frequency_var,
                                         values=['daily', 'weekly', 'monthly'], state='readonly')
            frequency_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)

            # Time
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.time_hour_0_23', default="Time (Hour 0-23):")).grid(row=2, column=0, sticky=tk.W, pady=5)
            hour_var = tk.StringVar(value="9")
            hour_spinbox = ttk.Spinbox(form_frame, from_=0, to=23, textvariable=hour_var)
            hour_spinbox.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)

            # Day of week (for weekly)
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.day_of_week', default="Day of Week:")).grid(row=3, column=0, sticky=tk.W, pady=5)
            day_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.values.monday', default="monday"))
            day_combo = ttk.Combobox(form_frame, textvariable=day_var,
                                    values=['monday', 'tuesday', 'wednesday', 'thursday',
                                           'friday', 'saturday', 'sunday'], state='readonly')
            day_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)

            # Recipients
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.recipients_comma_separated', default="Recipients (comma-separated):")).grid(row=4, column=0, sticky=tk.W, pady=5)
            recipients_text = ScrolledText(form_frame, height=4, wrap=tk.WORD)
            recipients_text.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5)

            # Report name
            ttk.Label(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.report_name', default="Report Name:")).grid(row=5, column=0, sticky=tk.W, pady=5)
            report_name_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=report_name_var).grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5)

            # Enabled checkbox
            enabled_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(form_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.enabled', default="Enabled"), variable=enabled_var).grid(
                row=6, column=0, columnspan=2, sticky=tk.W, pady=5)

            form_frame.columnconfigure(1, weight=1)

            # Buttons
            button_frame = ttk.Frame(schedule_window)
            button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            def save_schedule():
                try:
                    template_name = template_var.get()
                    if not template_name:
                        messagebox.showwarning(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.validation', default="Validation"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.please_select_a_template', default="Please select a template"))
                        return

                    recipients_str = recipients_text.get(1.0, tk.END).strip()
                    recipients = [r.strip() for r in recipients_str.split(',') if r.strip()]

                    report_name = report_name_var.get() or f"Scheduled {template_name}"

                    schedule_config = {
                        'template_name': template_name,
                        'frequency': frequency_var.get(),
                        'hour': int(hour_var.get()),
                        'day_of_week': day_var.get() if frequency_var.get() == 'weekly' else None,
                        'recipients': recipients,
                        'report_name': report_name,
                        'enabled': enabled_var.get(),
                        'created_at': datetime.now().isoformat()
                    }

                    # Load existing schedules
                    try:
                        scheduled_reports = _standalone_load_scheduled_reports()
                    except Exception:
                        scheduled_reports = []

                    # Add new schedule
                    scheduled_reports.append({
                        'template_name': template_name,
                        'schedule_config': schedule_config,
                        'recipients': recipients,
                        'last_run': None
                    })

                    # Save schedules
                    if self.save_scheduled_reports(scheduled_reports):
                        messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.success', default="Success"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.report_scheduled_successfully', default="Report scheduled successfully!"))
                        self.load_scheduled_reports()
                        schedule_window.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to schedule report: {str(e)}")

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.save_schedule', default="Save Schedule"), command=save_schedule,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.cancel', default="Cancel"),
                      command=schedule_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to open schedule dialog: {str(e)}")

    def schedule_report(self, report_data):
        """Schedule a single report using the schedule library"""
        try:
            if not ENHANCED_AVAILABLE:
                return False

            def run_report():
                try:
                    template_name = report_data['template_name']
                    recipients = report_data.get('recipients', [])

                    # Generate report
                    end_date = datetime.now().strftime("%Y-%m-%d")
                    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

                    report_path = generate_report(template_name, start_date, end_date)

                    # Send email if recipients exist
                    if recipients and report_path:
                        self.send_scheduled_report_email(recipients, report_path, template_name)

                    # Update last run time
                    report_data['last_run'] = datetime.now().isoformat()

                except Exception as e:
                    logging.error(f"Scheduled report error: {str(e)}")

            # Schedule based on frequency
            frequency = report_data.get('schedule_config', {}).get('frequency', 'daily')
            hour = report_data.get('schedule_config', {}).get('hour', 9)
            time_str = f"{hour:02d}:00"

            if frequency == 'daily':
                schedule.every().day.at(time_str).do(run_report)
            elif frequency == 'weekly':
                day = report_data.get('schedule_config', {}).get('day_of_week', 'monday')
                getattr(schedule.every(), day).at(time_str).do(run_report)
            elif frequency == 'monthly':
                schedule.every().day.at(time_str).do(run_report)  # Simplified

            return True
        except Exception as e:
            logging.error(f"Error scheduling report: {str(e)}")
            return False

    def send_scheduled_report_email(self, recipients, report_path, template_name):
        """Send scheduled report via email"""
        try:
            from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.email_delivery import send_report_email
            results = send_report_email(recipients, report_path, template_name)
            failed = [address for address, sent in results.items() if not sent]
            if failed:
                logging.error("Scheduled report failed for: %s", ", ".join(failed))
            return not failed

        except Exception as e:
            logging.error(f"Error sending scheduled report email: {str(e)}")
            return False

    def run_scheduler(self):
        """Run the scheduler loop (internal method)"""
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logging.error(f"Scheduler error: {str(e)}")
                time.sleep(60)

    def start_scheduler_method(self):
        """Start the background scheduler for automatic reports"""
        try:
            # Load and schedule all reports
            try:
                scheduled_reports = _standalone_load_scheduled_reports()

                for report in scheduled_reports:
                    if report.get('schedule_config', {}).get('enabled', True):
                        self.schedule_report(report)

            except Exception as e:
                logging.error(f"Error loading scheduled reports: {str(e)}")

            # Start scheduler thread
            scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
            scheduler_thread.start()

            self.update_status("Background scheduler started", "success")
            messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.scheduler', default="Scheduler"), _t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.background_scheduler_started_successfully', default="Background scheduler started successfully!"))

        except Exception as e:
            logging.error(f"Error starting scheduler: {str(e)}")
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to start scheduler: {str(e)}")

    def view_scheduled_reports_menu(self):
        """View and manage scheduled reports"""
        try:
            view_window = tk.Toplevel(self.root)
            view_window.title(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.windows.scheduled_reports', default="Scheduled Reports"))
            view_window.geometry("800x600")
            view_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(view_window)
            header_frame.pack(fill=tk.X, padx=20, pady=10)
            ttk.Label(header_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.labels.scheduled_reports', default="📅 Scheduled Reports"),
                     font=('Arial', 14, 'bold')).pack(anchor=tk.W)

            # Tree view for scheduled reports
            tree_frame = ttk.Frame(view_window)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            columns = ('Template', 'Frequency', 'Time', 'Recipients', 'Last Run', 'Status')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            # Scrollbar
            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Load scheduled reports
            def load_reports():
                tree.delete(*tree.get_children())
                try:
                    scheduled_reports = _standalone_load_scheduled_reports()

                    for report in scheduled_reports:
                        config = report.get('schedule_config', {})
                        status = "Enabled" if config.get('enabled', True) else "Disabled"

                        values = (
                            report.get('template_name', 'N/A'),
                            config.get('frequency', 'Unknown').title(),
                            f"{config.get('hour', 9):02d}:00",
                            str(len(report.get('recipients', []))),
                            report.get('last_run', 'Never')[:19] if report.get('last_run') else 'Never',
                            status
                        )

                        tree.insert('', tk.END, values=values)
                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to load scheduled reports: {str(e)}")

            load_reports()

            # Buttons
            button_frame = ttk.Frame(view_window)
            button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.add_schedule', default="Add Schedule"),
                      command=lambda: [self.schedule_advanced_report_menu(), view_window.after(500, load_reports)]).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.refresh', default="Refresh"), command=load_reports).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.buttons.close', default="Close"), command=view_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.scheduling_mixin.dialogs.error', default="Error"), f"Failed to show scheduled reports: {str(e)}")

    def manage_schedule_menu(self):
        """Manage scheduled reports (wrapper for view_scheduled_reports_menu)"""
        self.view_scheduled_reports_menu()
