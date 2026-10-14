"""Methods __init__ through generate_enrollment_statistics."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import report_manager_shared as _shared
from education_system.systems.university.shell.gui.batch_operations.thread_ui import post
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ReportManager:
    def __init__(self, gui):
        self.gui = gui

    def run_data_quality_check(self):
        """Menu item for data quality check - redirect to validate_data"""
        self.gui.validate_data()

    def show_dashboard(self):
        """Show main dashboard in a new window"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.menu.dashboard"))
        dialog.geometry("680x620")
        dialog.transient(self.gui.root)

        # ReportView draws its own title band, so no separate header.
        from education_system.systems.university.shell.gui.batch_operations import report_view as rv
        view = rv.ReportView(dialog)
        view.pack(fill=tk.BOTH, expand=True, padx=14, pady=(14, 8))
        view.empty(_t("batch_ops.labels.dashboard_loading",
                      "Loading dashboard data..."))

        def show(data, error=None):
            """Redraw the dashboard. Main loop only."""
            if not view.winfo_exists():
                return
            view.clear()
            if error is not None:
                view.title(_t("batch_ops.menu.dashboard"))
                view.item(_t("batch_ops.errors.generic_error", error=str(error)),
                          tone='bad')
            else:
                self.gui.quality_mgr.render_quality_dashboard(view, data)
            view.freeze()

        def load_dashboard():
            # Runs on a worker thread (and on the main thread via the Refresh
            # button); the widget writes are marshalled either way. The raw
            # data crosses the boundary, not a rendered string — the widgets
            # need the numbers to size their bars.
            try:
                data = self.gui.get_quality_dashboard_data()
                post(dialog, lambda d=data: show(d))
            except Exception as e:
                post(dialog, lambda err=e: show(None, error=err))

        import threading
        thread = threading.Thread(target=load_dashboard)
        thread.daemon = True
        thread.start()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 10))
        ttk.Button(btn_frame, text=_t("batch_ops.buttons.refresh_dashboard"),
                   command=load_dashboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("batch_ops.buttons.cancel"),
                   command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_import_history(self):
        """Show import history tab"""
        # Switch to history tab and refresh
        self.gui.notebook.select(6)  # History tab
        self.refresh_history()

    def export_history(self):
        """Export import history to file"""
        if not self.gui.backend.import_history:
            messagebox.showinfo(_t("batch_ops.msg_titles.no_history"), _t("batch_ops.messages.no_history_export"))
            return

        output_file = filedialog.asksaveasfilename(
            title=_t('gui.shell.batch_operations.report_manager_parts.reportmanager_init.dialogs.export_import_history', default="Export import history"),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not output_file:
            return

        try:
            if output_file.lower().endswith('.csv'):
                # Export as CSV
                with open(output_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Timestamp', 'Operation', 'Total Records', 'Successful', 'Failed', 'File Path'])

                    for entry in self.gui.backend.import_history:
                        writer.writerow([
                            entry['timestamp'],
                            entry['operation_type'],
                            entry['total_records'],
                            entry['successful_imports'],
                            entry['failed_imports'],
                            entry['file_path']
                        ])
            else:
                # Export as JSON
                with open(output_file, 'w') as f:
                    json.dump(self.gui.backend.import_history, f, indent=2)

            messagebox.showinfo(_t("batch_ops.msg_titles.exported"), _t("batch_ops.messages.export_history_confirm", output_file=output_file))

        except Exception as e:
            messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

    def clear_history(self):
        """Clear import history"""
        if messagebox.askyesno(_t("batch_ops.msg_titles.clear_history"),
                              _t('gui.shell.batch_operations.report_manager_parts.reportmanager_init.dialogs.this_will_permanently_delete_all_import_history_this_action_cann', default="This will permanently delete all import history.\n"
                              "This action cannot be undone!\n\n"
                              "Continue?")):
            try:
                self.gui.backend.import_history = []

                # Remove history file
                if IMPORT_HISTORY_PATH.exists():
                    IMPORT_HISTORY_PATH.unlink(missing_ok=True)

                # Refresh display
                self.refresh_history()

                messagebox.showinfo(_t("batch_ops.msg_titles.cleared"), _t("batch_ops.messages.history_cleared"))

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

    def refresh_history(self):
        """Refresh import history display"""
        try:
            # Load history from backend
            if not self.gui.backend.import_history:
                try:
                    with open(IMPORT_HISTORY_PATH, 'r') as f:
                        self.gui.backend.import_history = json.load(f)
                except FileNotFoundError:
                    self.gui.backend.import_history = []

            # Clear existing items
            for item in self.gui.history_tree.get_children():
                self.gui.history_tree.delete(item)

            # Filter history based on selection
            filter_type = self.gui.history_filter.get().lower()

            # Add history items
            for entry in reversed(self.gui.backend.import_history[-50:]):  # Show last 50 entries
                if filter_type == "all" or filter_type in entry['operation_type'].lower():
                    timestamp = datetime.datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M')
                    operation = entry['operation_type']
                    records = f"{entry['successful_imports']}/{entry['total_records']}"
                    success_rate = f"{(entry['successful_imports']/entry['total_records']*100):.1f}%" if entry['total_records'] > 0 else "N/A"
                    errors = str(entry['failed_imports'])

                    # Color coding based on success rate
                    if entry['successful_imports'] == entry['total_records']:
                        tags = ('success',)
                    elif entry['failed_imports'] > entry['successful_imports']:
                        tags = ('error',)
                    else:
                        tags = ('warning',)

                    self.gui.history_tree.insert('', 'end', values=(timestamp, operation, records, success_rate, errors), tags=tags)

            # Configure tag colors
            self.gui.history_tree.tag_configure('success', background='#d4edda')
            self.gui.history_tree.tag_configure('warning', background='#fff3cd')
            self.gui.history_tree.tag_configure('error', background='#f8d7da')

        except Exception as e:
            logger.error(f"Error refreshing history: {e}")
            messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

    def update_automation_status(self):
        """Update automation status display"""
        try:
            status_text = f"""🤖 AUTOMATION STATUS
Last Updated: {datetime.datetime.now().strftime('%H:%M:%S')}

📅 SCHEDULED TASKS
Active Tasks: {len(schedule.get_jobs())}

🌐 API SERVER
Status: {'Running' if self.gui.backend.api_app else 'Stopped'}

🔗 EXTERNAL INTEGRATIONS
Database: {'Configured' if EXTERNAL_DB_CONFIG_PATH.exists() else 'Not configured'}
REST API: {'Configured' if EXTERNAL_API_CONFIG_PATH.exists() else 'Not configured'}

📊 RECENT ACTIVITY
Last automated import: {'N/A'}
Last scheduled task run: {'N/A'}
"""

            self.gui.automation_status.config(state='normal')
            self.gui.automation_status.delete(1.0, tk.END)
            self.gui.automation_status.insert(tk.END, status_text)
            self.gui.automation_status.config(state='disabled')

        except Exception as e:
            logger.error(f"Error updating automation status: {e}")

    def show_connection_test_results(self, results):
        """Show connection test results"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.connection_test"))
        dialog.geometry("500x300")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text=_t("batch_ops.windows.connection_test"), font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Results display
        results_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.test_results"), padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        results_text = scrolledtext.ScrolledText(results_frame, height=12)
        results_text.pack(fill=tk.BOTH, expand=True)

        for connection_type, result in results.items():
            status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
            results_text.insert(tk.END, f"{connection_type}: {status}\n")
            if result.get('message'):
                results_text.insert(tk.END, f"  Message: {result['message']}\n")
            results_text.insert(tk.END, "\n")

        results_text.config(state='disabled')

        # Close button
        ttk.Button(dialog, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(pady=10)

    def get_quality_dashboard_data(self) -> Dict:
        """Get data for quality dashboard"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Basic statistics
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM students WHERE email_address IS NOT NULL AND email_address != ''")
            students_with_email = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM students WHERE dob IS NOT NULL AND dob != ''")
            students_with_dob = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT s.student_id) FROM students s JOIN student_modules sm ON s.student_id = sm.student_id")
            students_with_modules = cursor.fetchone()[0]

            # Calculate metrics
            email_completeness = (students_with_email / total_students * 100) if total_students > 0 else 0
            dob_completeness = (students_with_dob / total_students * 100) if total_students > 0 else 0
            module_rate = (students_with_modules / total_students * 100) if total_students > 0 else 0

            quality_score = (email_completeness + dob_completeness + module_rate) / 3

            conn.close()

            return {
                'total_students': total_students,
                'quality_score': quality_score,
                'email_completeness': email_completeness,
                'dob_completeness': dob_completeness,
                'module_rate': module_rate,
                'students_with_modules': students_with_modules,
                'validation_errors': 0,  # Would be calculated from recent validation
                'duplicate_candidates': 0,  # Would be calculated from recent duplicate check
                'missing_info': total_students - students_with_email,
                'active_students': total_students,
                'new_registrations': 0,  # Would be calculated from recent registrations
                'data_updates': 0,  # Would be tracked from recent updates
                'quality_improvements': 0,  # Would be tracked from fixes
                'alerts': 'No current alerts'
            }

        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {}

    def generate_template_file(self, template_type: str, output_file: str, file_format: str, include_examples: bool):
        """Generate template file"""
        import pandas as pd
        # Template field definitions
        template_fields = {
            'new_students': ['first_name', 'middle_name', 'last_name', 'gender', 'dob', 'course', 'email_address', 'phone_number'],
            'update_students': ['student_id', 'first_name', 'middle_name', 'last_name', 'gender', 'dob', 'course', 'email_address'],
            'module_enrollment': ['student_id', 'module_code', 'module_name', 'module_type'],
            'grade_import': ['student_id', 'module_code', 'grade', 'semester', 'year'],
            'custom': []
        }

        fields = template_fields.get(template_type, [])

        # Example data
        example_data = {
            'new_students': {
                'first_name': 'John',
                'middle_name': 'William',
                'last_name': 'Doe',
                'gender': 'male',
                'dob': '1995-01-15',
                'course': 'CS',
                'email_address': 'john.doe@example.com',
                'phone_number': '+44123456789'
            },
            'update_students': {
                'student_id': '1234567',
                'first_name': 'John',
                'course': 'DS'
            },
            'module_enrollment': {
                'student_id': '1234567',
                'module_code': 'CS101',
                'module_name': 'Introduction to Programming',
                'module_type': 'compulsory'
            },
            'grade_import': {
                'student_id': '1234567',
                'module_code': 'CS101',
                'grade': '85.5',
                'semester': 'Fall',
                'year': '2024'
            }
        }

        try:
            if file_format == 'csv':
                with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fields)
                    writer.writeheader()

                    if include_examples and template_type in example_data:
                        example_row = {field: example_data[template_type].get(field, '') for field in fields}
                        writer.writerow(example_row)

            else:  # Excel
                df = pd.DataFrame(columns=fields)

                if include_examples and template_type in example_data:
                    example_row = {field: example_data[template_type].get(field, '') for field in fields}
                    df = df.append(example_row, ignore_index=True)

                df.to_excel(output_file, index=False)

        except Exception as e:
            logger.error(f"Error creating template: {e}")
            raise

    def generate_enrollment_statistics(self) -> Dict:
        """Generate enrollment statistics"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            stats = {}

            # Course enrollment stats
            cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course")
            stats['course_enrollment'] = dict(cursor.fetchall())

            # Module enrollment stats
            cursor.execute("""
            SELECT module_code, module_name, COUNT(*) as enrollment_count
            FROM student_modules
            GROUP BY module_code, module_name
            ORDER BY enrollment_count DESC
            """)
            stats['module_enrollment'] = [
                {'module_code': row[0], 'module_name': row[1], 'enrollment': row[2]}
                for row in cursor.fetchall()
            ]

            # Gender distribution
            cursor.execute("SELECT gender, COUNT(*) FROM students GROUP BY gender")
            stats['gender_distribution'] = dict(cursor.fetchall())

            # Registration trends
            cursor.execute("""
            SELECT strftime('%Y-%m', registration_datetime) as month, COUNT(*)
            FROM students
            WHERE registration_datetime >= date('now', '-12 months')
            GROUP BY month
            ORDER BY month
            """)
            stats['registration_trends'] = dict(cursor.fetchall())

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Error generating statistics: {e}")
            return {}
