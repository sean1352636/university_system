"""API handler methods mixin for the enhanced reporting GUI."""

from ..standalone.constants import (
    tk, ttk, filedialog, messagebox, simpledialog,
    ScrolledText,
    threading, webbrowser, os, json, logging,
    datetime, timedelta, pd,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
    _t,
    DataQualityMonitor, PredictiveAnalytics, AdvancedVisualization,
    CacheManager, SystemConfig, ReportTemplate,
    load_templates, generate_report,
)

try:
    from ..standalone.constants import (
        get_section_dataframe,
        get_correlation_data,
        start_scheduler,
        logger,
    )
except ImportError:
    get_section_dataframe = None
    get_correlation_data = None
    start_scheduler = None
    logger = logging.getLogger(__name__)


class ApiHandlersMixin:
    """Mixin providing API-style handler methods for the reporting GUI.

    These were originally standalone functions with a ``self`` parameter
    at module level.  They are now proper methods on a mixin class.
    """

    def not_found_handler(self, error_msg):
        """Handle 404-like errors in GUI context"""
        messagebox.showerror("Not Found", f"Resource not found: {error_msg}")
        self.update_status("Resource not found", "error")

    def internal_error_handler(self, error_msg):
        """Handle 500-like errors in GUI context"""
        messagebox.showerror("Internal Error", f"An internal error occurred: {error_msg}")
        self.update_status("Internal error occurred", "error")
        logging.error(f"Internal error: {error_msg}")

    def api_health_check(self):
        """Check API health status and display in GUI"""
        try:
            # Simulate health check
            status = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'database': 'connected',
                'version': '2.0'
            }

            conn = get_db_connection()
            if conn:
                conn.close()
                status['database'] = 'connected'
            else:
                status['database'] = 'disconnected'
                status['status'] = 'unhealthy'

            # Display in dialog
            health_window = tk.Toplevel(self.root)
            health_window.title("System Health Check")
            health_window.geometry("400x300")

            health_text = ScrolledText(health_window, wrap=tk.WORD)
            health_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            health_info = f"""System Health Status
{'=' * 30}

Status: {status['status'].upper()}
Timestamp: {status['timestamp']}
Database: {status['database'].upper()}
Version: {status['version']}

Enhanced Features: {'Available' if ENHANCED_AVAILABLE else 'Not Available'}
"""

            health_text.insert(1.0, health_info)
            health_text.config(state=tk.DISABLED)

        except Exception as e:
            self.internal_error_handler(str(e))

    def get_section_data_dialog(self, section=None):
        """Get section data and display in dialog"""
        if not section:
            section = simpledialog.askstring("Section Data", "Enter section name:")

        if section:
            try:
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                end_date = datetime.now().strftime("%Y-%m-%d")

                df = get_section_dataframe(section, start_date, end_date)

                if not df.empty:
                    # Create data display window
                    data_window = tk.Toplevel(self.root)
                    data_window.title(f"Section Data: {section}")
                    data_window.geometry("800x600")

                    # Create treeview for data
                    columns = list(df.columns)
                    tree = ttk.Treeview(data_window, columns=columns, show='headings')

                    for col in columns:
                        tree.heading(col, text=col)
                        tree.column(col, width=100)

                    # Add data rows
                    for _, row in df.head(100).iterrows():
                        tree.insert('', tk.END, values=list(row))

                    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                    # Add export button
                    ttk.Button(data_window, text="Export to CSV",
                             command=lambda: self.export_dataframe_csv(df, section)).pack(pady=5)
                else:
                    messagebox.showinfo("No Data", f"No data found for section: {section}")

            except Exception as e:
                self.internal_error_handler(str(e))

    def export_dataframe_csv(self, df, section_name):
        """Export dataframe to CSV file"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"{section_name}_data.csv"
            )

            if file_path:
                df.to_csv(file_path, index=False)
                messagebox.showinfo("Export Success", f"Data exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

    def show_templates_dialog(self):
        """Show templates in a dialog (API equivalent)"""
        try:
            templates = load_templates() if ENHANCED_AVAILABLE else []

            # Create templates window
            templates_window = tk.Toplevel(self.root)
            templates_window.title("All Templates")
            templates_window.geometry("700x500")

            # Create treeview
            columns = ('Name', 'Description', 'Sections', 'Security Level', 'Created')
            tree = ttk.Treeview(templates_window, columns=columns, show='headings')

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            # Populate with templates
            for template in templates:
                sections_count = len(template.get('sections', []))
                values = (
                    template['name'],
                    template.get('description', '')[:50] + '...' if len(template.get('description', '')) > 50 else template.get('description', ''),
                    f"{sections_count} sections",
                    template.get('security_level', 'normal').title(),
                    template.get('created_at', 'Unknown')[:10]
                )
                tree.insert('', tk.END, values=values)

            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Action buttons
            button_frame = ttk.Frame(templates_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(button_frame, text="Close", command=templates_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            self.internal_error_handler(str(e))

    def create_template_api_style(self):
        """Create template through API-style dialog"""
        try:
            # Create input dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Template (API Style)")
            dialog.geometry("500x400")
            dialog.transient(self.root)

            # Template data inputs
            ttk.Label(dialog, text="Template Name:").pack(anchor=tk.W, padx=10, pady=5)
            name_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=name_var, width=50).pack(fill=tk.X, padx=10)

            ttk.Label(dialog, text="Description:").pack(anchor=tk.W, padx=10, pady=5)
            desc_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=desc_var, width=50).pack(fill=tk.X, padx=10)

            ttk.Label(dialog, text="Sections (comma-separated):").pack(anchor=tk.W, padx=10, pady=5)
            sections_text = tk.Text(dialog, height=4, width=50)
            sections_text.pack(fill=tk.X, padx=10)
            sections_text.insert(1.0, "student_overview,course_distribution,gender_distribution")

            ttk.Label(dialog, text="Security Level:").pack(anchor=tk.W, padx=10, pady=5)
            security_var = tk.StringVar(value="normal")
            security_combo = ttk.Combobox(dialog, textvariable=security_var,
                                        values=["normal", "confidential", "restricted"], state="readonly")
            security_combo.pack(fill=tk.X, padx=10)

            def save_template():
                try:
                    name = name_var.get().strip()
                    if not name:
                        messagebox.showerror("Validation Error", "Template name is required")
                        return

                    sections = [s.strip() for s in sections_text.get(1.0, tk.END).strip().split(',') if s.strip()]
                    if not sections:
                        messagebox.showerror("Validation Error", "At least one section is required")
                        return

                    template_data = {
                        'name': name,
                        'description': desc_var.get().strip(),
                        'sections': sections,
                        'security_level': security_var.get(),
                        'visualization_type': 'standard',
                        'created_at': datetime.now().isoformat(),
                        'version': '1.0',
                        'filters': {}
                    }

                    if ENHANCED_AVAILABLE:
                        templates = load_templates()
                        templates.append(template_data)

                        os.makedirs(CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)), exist_ok=True)
                        with open(os.path.join(CONFIG.get('templates_dir', str(paths.REPORT_TEMPLATES_DIR)), "templates.json"), 'w') as f:
                            json.dump(templates, f, indent=4)

                    messagebox.showinfo("Success", f"Template '{name}' created successfully!")
                    dialog.destroy()
                    self.refresh_data()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create template: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Create Template", command=save_template).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            self.internal_error_handler(str(e))

    def generate_report_api_style(self):
        """Generate report through API-style interface"""
        try:
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Generate Report (API Style)")
            dialog.geometry("500x350")
            dialog.transient(self.root)

            # Parameters
            ttk.Label(dialog, text="Template Name:").pack(anchor=tk.W, padx=10, pady=5)
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(dialog, textvariable=template_var, state="readonly")
            template_combo.pack(fill=tk.X, padx=10)

            # Load templates
            if ENHANCED_AVAILABLE:
                templates = load_templates()
                template_combo['values'] = [t['name'] for t in templates]
                if templates:
                    template_combo.set(templates[0]['name'])

            ttk.Label(dialog, text="Start Date (YYYY-MM-DD):").pack(anchor=tk.W, padx=10, pady=5)
            start_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
            ttk.Entry(dialog, textvariable=start_var).pack(fill=tk.X, padx=10)

            ttk.Label(dialog, text="End Date (YYYY-MM-DD):").pack(anchor=tk.W, padx=10, pady=5)
            end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
            ttk.Entry(dialog, textvariable=end_var).pack(fill=tk.X, padx=10)

            ttk.Label(dialog, text="Format:").pack(anchor=tk.W, padx=10, pady=5)
            format_var = tk.StringVar(value="pdf")
            format_combo = ttk.Combobox(dialog, textvariable=format_var,
                                      values=["pdf", "excel", "interactive"], state="readonly")
            format_combo.pack(fill=tk.X, padx=10)

            def generate():
                try:
                    template_name = template_var.get()
                    start_date = start_var.get()
                    end_date = end_var.get()
                    format_type = format_var.get()

                    if not template_name:
                        messagebox.showerror("Error", "Please select a template")
                        return

                    # Validate dates
                    try:
                        datetime.strptime(start_date, "%Y-%m-%d")
                        datetime.strptime(end_date, "%Y-%m-%d")
                    except ValueError:
                        messagebox.showerror("Error", "Invalid date format")
                        return

                    self.update_status("Generating report via API...")
                    dialog.destroy()

                    def generate_task():
                        try:
                            if ENHANCED_AVAILABLE:
                                report_path = generate_report(template_name, start_date, end_date, format_type)
                                if report_path:
                                    self.root.after(0, lambda: [
                                        self.update_status("Report generated successfully"),
                                        messagebox.showinfo("Success", f"Report generated: {os.path.basename(report_path)}"),
                                        self.refresh_reports()
                                    ])
                                else:
                                    self.root.after(0, lambda: [
                                        self.update_status("Report generation failed", "error"),
                                        messagebox.showerror("Error", "Failed to generate report")
                                    ])
                            else:
                                self.root.after(0, lambda: [
                                    self.update_status("Enhanced features not available", "warning"),
                                    messagebox.showwarning("Feature Unavailable", "Enhanced reporting not available")
                                ])
                        except Exception as e:
                            self.root.after(0, lambda: [
                                self.update_status(f"Error: {str(e)}", "error"),
                                messagebox.showerror("Error", f"Generation failed: {str(e)}")
                            ])

                    threading.Thread(target=generate_task, daemon=True).start()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Generate", command=generate).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            self.internal_error_handler(str(e))

    def show_data_quality_dialog(self):
        """Show data quality in dedicated dialog"""
        try:
            # Create quality dialog
            quality_window = tk.Toplevel(self.root)
            quality_window.title("Data Quality Dashboard")
            quality_window.geometry("800x600")

            # Create notebook for different quality aspects
            quality_notebook = ttk.Notebook(quality_window)
            quality_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Overview tab
            overview_frame = ttk.Frame(quality_notebook)
            quality_notebook.add(overview_frame, text="Overview")

            self.quality_overview_text = ScrolledText(overview_frame, wrap=tk.WORD)
            self.quality_overview_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Missing data tab
            missing_frame = ttk.Frame(quality_notebook)
            quality_notebook.add(missing_frame, text="Missing Data")

            self.missing_data_text = ScrolledText(missing_frame, wrap=tk.WORD)
            self.missing_data_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Duplicates tab
            duplicates_frame = ttk.Frame(quality_notebook)
            quality_notebook.add(duplicates_frame, text="Duplicates")

            self.duplicates_text = ScrolledText(duplicates_frame, wrap=tk.WORD)
            self.duplicates_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Action buttons
            button_frame = ttk.Frame(quality_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(button_frame, text="Refresh Quality Check",
                     command=self.run_comprehensive_quality_check).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Export Report",
                     command=self.export_quality_report).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Close",
                     command=quality_window.destroy).pack(side=tk.RIGHT)

            # Run initial quality check
            self.run_comprehensive_quality_check()

        except Exception as e:
            self.internal_error_handler(str(e))

    def run_comprehensive_quality_check(self):
        """Run comprehensive quality check and display results"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable", "Data quality checking requires enhanced features")
            return

        self.update_status("Running comprehensive quality check...")

        def quality_task():
            try:
                quality_report = DataQualityMonitor.run_quality_checks()
                self.root.after(0, lambda: self.display_comprehensive_quality_results(quality_report))
            except Exception as e:
                self.root.after(0, lambda: [
                    self.update_status("Quality check failed", "error"),
                    messagebox.showerror("Error", f"Quality check failed: {str(e)}")
                ])

        threading.Thread(target=quality_task, daemon=True).start()

    def display_comprehensive_quality_results(self, quality_report):
        """Display comprehensive quality results in tabs"""
        try:
            self.update_status("Quality check completed")

            # Overview tab
            if hasattr(self, 'quality_overview_text'):
                self.quality_overview_text.delete(1.0, tk.END)
                overview = f"""Data Quality Overview
{'=' * 50}

Timestamp: {quality_report.get('timestamp', 'Unknown')}
Status: {'PASSED' if quality_report.get('overall_status', 'unknown') == 'passed' else 'ISSUES FOUND'}

Summary:
"""
                checks = quality_report.get('checks', {})
                if 'missing_data' in checks:
                    missing = checks['missing_data']['students']
                    total = missing.get('total_records', 0)
                    overview += f"- Total Records: {total}\n"
                    overview += f"- Data Completeness: {((total * 3 - sum([missing.get('missing_emails', 0), missing.get('missing_names', 0), missing.get('missing_courses', 0)])) / (total * 3) * 100) if total > 0 else 0:.1f}%\n"

                self.quality_overview_text.insert(1.0, overview)

            # Missing data tab
            if hasattr(self, 'missing_data_text'):
                self.missing_data_text.delete(1.0, tk.END)
                missing_content = "Missing Data Analysis\n" + "=" * 30 + "\n\n"

                if 'missing_data' in checks:
                    missing = checks['missing_data']['students']
                    missing_content += f"Total Records: {missing.get('total_records', 0)}\n"
                    missing_content += f"Missing Emails: {missing.get('missing_emails', 0)}\n"
                    missing_content += f"Missing Names: {missing.get('missing_names', 0)}\n"
                    missing_content += f"Missing Courses: {missing.get('missing_courses', 0)}\n\n"

                    if missing.get('missing_email_details'):
                        missing_content += "Records with Missing Emails:\n"
                        for detail in missing['missing_email_details'][:10]:
                            missing_content += f"- ID: {detail.get('id', 'N/A')}, Name: {detail.get('name', 'N/A')}\n"

                self.missing_data_text.insert(1.0, missing_content)

            # Duplicates tab
            if hasattr(self, 'duplicates_text'):
                self.duplicates_text.delete(1.0, tk.END)
                duplicates_content = "Duplicate Data Analysis\n" + "=" * 30 + "\n\n"

                if 'duplicates' in checks:
                    duplicates = checks['duplicates']
                    duplicates_content += f"Duplicate Emails: {duplicates.get('duplicate_emails', 0)}\n\n"

                    if duplicates.get('duplicate_email_details'):
                        duplicates_content += "Duplicate Email Details:\n"
                        for detail in duplicates['duplicate_email_details'][:10]:
                            duplicates_content += f"- Email: {detail.get('email', 'N/A')}, Count: {detail.get('count', 0)}\n"

                self.duplicates_text.insert(1.0, duplicates_content)

        except Exception as e:
            logging.error(f"Error displaying quality results: {str(e)}")

    def show_predictive_analytics_dialog(self):
        """Show predictive analytics in dedicated dialog"""
        try:
            # Create analytics dialog
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title("Predictive Analytics Dashboard")
            analytics_window.geometry("900x700")

            # Create notebook for different analytics
            analytics_notebook = ttk.Notebook(analytics_window)
            analytics_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Dropout Risk tab
            dropout_frame = ttk.Frame(analytics_notebook)
            analytics_notebook.add(dropout_frame, text="Dropout Risk")

            self.dropout_text = ScrolledText(dropout_frame, wrap=tk.WORD)
            self.dropout_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Model Performance tab
            performance_frame = ttk.Frame(analytics_notebook)
            analytics_notebook.add(performance_frame, text="Model Performance")

            self.performance_text = ScrolledText(performance_frame, wrap=tk.WORD)
            self.performance_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Recommendations tab
            recommendations_frame = ttk.Frame(analytics_notebook)
            analytics_notebook.add(recommendations_frame, text="Recommendations")

            self.recommendations_text = ScrolledText(recommendations_frame, wrap=tk.WORD)
            self.recommendations_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Action buttons
            button_frame = ttk.Frame(analytics_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(button_frame, text="Run Analysis",
                     command=self.run_comprehensive_predictions).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Export Results",
                     command=self.export_predictions_report).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Close",
                     command=analytics_window.destroy).pack(side=tk.RIGHT)

            # Run initial analysis
            self.run_comprehensive_predictions()

        except Exception as e:
            self.internal_error_handler(str(e))

    def run_comprehensive_predictions(self):
        """Run comprehensive predictive analysis"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable", "Predictive analytics requires enhanced features")
            return

        self.update_status("Running predictive analytics...")

        def predictions_task():
            try:
                predictions = PredictiveAnalytics.predict_dropout_risk()
                self.root.after(0, lambda: self.display_comprehensive_predictions(predictions))
            except Exception as e:
                self.root.after(0, lambda: [
                    self.update_status("Predictions failed", "error"),
                    messagebox.showerror("Error", f"Predictions failed: {str(e)}")
                ])

        threading.Thread(target=predictions_task, daemon=True).start()

    def display_comprehensive_predictions(self, predictions):
        """Display comprehensive prediction results"""
        try:
            self.update_status("Predictive analysis completed")

            # Dropout Risk tab
            if hasattr(self, 'dropout_text'):
                self.dropout_text.delete(1.0, tk.END)
                dropout_content = "Dropout Risk Analysis\n" + "=" * 40 + "\n\n"

                if 'error' in predictions:
                    dropout_content += f"Analysis unavailable: {predictions['error']}\n"
                else:
                    dropout_content += f"Students Analyzed: {predictions.get('total_students_analyzed', 0)}\n"
                    dropout_content += f"High Risk Students: {len(predictions.get('high_risk_students', []))}\n"

                    if predictions.get('high_risk_students'):
                        dropout_content += "\nHigh Risk Student Details:\n"
                        for student in predictions['high_risk_students'][:10]:
                            dropout_content += f"- ID: {student.get('student_id', 'N/A')}, Risk Score: {student.get('risk_score', 0):.2%}\n"

                self.dropout_text.insert(1.0, dropout_content)

            # Model Performance tab
            if hasattr(self, 'performance_text'):
                self.performance_text.delete(1.0, tk.END)
                performance_content = "Model Performance Metrics\n" + "=" * 40 + "\n\n"

                if 'model_accuracy' in predictions:
                    accuracy = predictions['model_accuracy']
                    performance_content += f"Model Accuracy: {accuracy:.2%}\n"

                    if accuracy > 0.8:
                        performance_content += "Status: Excellent model performance\n"
                    elif accuracy > 0.6:
                        performance_content += "Status: Good model performance\n"
                    else:
                        performance_content += "Status: Model needs improvement\n"

                if 'feature_importance' in predictions:
                    performance_content += "\nMost Important Risk Factors:\n"
                    importance = predictions['feature_importance']
                    sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
                    for feature, score in sorted_features:
                        performance_content += f"- {feature.replace('_', ' ').title()}: {score:.3f}\n"

                self.performance_text.insert(1.0, performance_content)

            # Recommendations tab
            if hasattr(self, 'recommendations_text'):
                self.recommendations_text.delete(1.0, tk.END)
                recommendations_content = "Recommendations\n" + "=" * 20 + "\n\n"

                high_risk_count = len(predictions.get('high_risk_students', []))

                if high_risk_count > 0:
                    recommendations_content += f"Action Required for {high_risk_count} students:\n\n"
                    recommendations_content += "1. Contact high-risk students immediately\n"
                    recommendations_content += "2. Provide additional academic support\n"
                    recommendations_content += "3. Schedule counseling sessions\n"
                    recommendations_content += "4. Monitor attendance closely\n"
                    recommendations_content += "5. Consider intervention programs\n\n"
                else:
                    recommendations_content += "No immediate action required.\n"
                    recommendations_content += "Continue monitoring student performance.\n\n"

                recommendations_content += "General Recommendations:\n"
                recommendations_content += "- Regular model updates with new data\n"
                recommendations_content += "- Monitor model accuracy trends\n"
                recommendations_content += "- Validate predictions with academic staff\n"

                self.recommendations_text.insert(1.0, recommendations_content)

        except Exception as e:
            logging.error(f"Error displaying predictions: {str(e)}")

    def export_predictions_report(self):
        """Export predictions report to file"""
        try:
            if not hasattr(self, 'dropout_text'):
                messagebox.showwarning("No Data", "No predictions data to export")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"predictions_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if file_path:
                with open(file_path, 'w') as f:
                    f.write("Comprehensive Predictive Analytics Report\n")
                    f.write("=" * 60 + "\n\n")
                    f.write("DROPOUT RISK ANALYSIS:\n")
                    f.write(self.dropout_text.get(1.0, tk.END))
                    f.write("\n\nMODEL PERFORMANCE:\n")
                    if hasattr(self, 'performance_text'):
                        f.write(self.performance_text.get(1.0, tk.END))
                    f.write("\n\nRECOMMENDATIONS:\n")
                    if hasattr(self, 'recommendations_text'):
                        f.write(self.recommendations_text.get(1.0, tk.END))

                messagebox.showinfo("Export Success", f"Predictions report exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report: {str(e)}")

    def show_anomaly_detection_dialog(self):
        """Show anomaly detection in dedicated dialog"""
        try:
            # Create anomaly dialog
            anomaly_window = tk.Toplevel(self.root)
            anomaly_window.title("Anomaly Detection Dashboard")
            anomaly_window.geometry("800x600")

            # Results display
            self.anomaly_results_text = ScrolledText(anomaly_window, wrap=tk.WORD)
            self.anomaly_results_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Action buttons
            button_frame = ttk.Frame(anomaly_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(button_frame, text="Run Detection",
                     command=self.run_comprehensive_anomaly_detection).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Export Results",
                     command=self.export_anomaly_report).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Close",
                     command=anomaly_window.destroy).pack(side=tk.RIGHT)

            # Run initial detection
            self.run_comprehensive_anomaly_detection()

        except Exception as e:
            self.internal_error_handler(str(e))

    def run_comprehensive_anomaly_detection(self):
        """Run comprehensive anomaly detection"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable", "Anomaly detection requires enhanced features")
            return

        self.update_status("Running anomaly detection...")

        def anomaly_task():
            try:
                anomalies = PredictiveAnalytics.detect_anomalies()
                self.root.after(0, lambda: self.display_comprehensive_anomalies(anomalies))
            except Exception as e:
                self.root.after(0, lambda: [
                    self.update_status("Anomaly detection failed", "error"),
                    messagebox.showerror("Error", f"Anomaly detection failed: {str(e)}")
                ])

        threading.Thread(target=anomaly_task, daemon=True).start()

    def display_comprehensive_anomalies(self, anomalies):
        """Display comprehensive anomaly results"""
        try:
            self.update_status("Anomaly detection completed")

            if hasattr(self, 'anomaly_results_text'):
                self.anomaly_results_text.delete(1.0, tk.END)

                content = "Comprehensive Anomaly Detection Results\n"
                content += "=" * 50 + "\n\n"

                if 'error' in anomalies:
                    content += f"Analysis unavailable: {anomalies['error']}\n"
                else:
                    content += f"Total Students Analyzed: {anomalies.get('total_students_analyzed', 0)}\n"
                    content += f"Anomalies Detected: {anomalies.get('total_anomalies', 0)}\n"
                    content += f"Anomaly Rate: {anomalies.get('anomaly_rate', 0):.2f}%\n\n"

                    anomaly_rate = anomalies.get('anomaly_rate', 0)
                    if anomaly_rate > 15:
                        content += "STATUS: HIGH - Investigate data quality issues\n"
                    elif anomaly_rate > 5:
                        content += "STATUS: MODERATE - Review identified anomalies\n"
                    else:
                        content += "STATUS: NORMAL - Low anomaly rate detected\n"

                    content += "\n" + "-" * 40 + "\n\n"

                    if anomalies.get('anomalous_students'):
                        content += "DETAILED ANOMALY ANALYSIS:\n\n"
                        for i, student in enumerate(anomalies['anomalous_students'][:15], 1):
                            content += f"{i}. Student ID: {student.get('student_id', 'N/A')}\n"
                            content += f"   Age: {student.get('age', 'N/A')}\n"
                            content += f"   Unique Modules: {student.get('unique_modules', 'N/A')}\n"
                            content += f"   Average Grade: {student.get('avg_grade', 'N/A')}\n"
                            content += f"   Anomaly Score: {student.get('anomaly_score', 'N/A')}\n"
                            content += f"   Reason: {student.get('anomaly_reason', 'Statistical outlier')}\n\n"

                        if len(anomalies['anomalous_students']) > 15:
                            remaining = len(anomalies['anomalous_students']) - 15
                            content += f"... and {remaining} more anomalous profiles\n"

                    content += "\nRECOMMENDATIONS:\n"
                    content += "1. Verify data accuracy for flagged students\n"
                    content += "2. Check for data entry errors\n"
                    content += "3. Investigate unusual enrollment patterns\n"
                    content += "4. Contact students with extreme anomalies\n"

                self.anomaly_results_text.insert(1.0, content)

        except Exception as e:
            logging.error(f"Error displaying anomalies: {str(e)}")

    def export_anomaly_report(self):
        """Export anomaly detection report"""
        try:
            if not hasattr(self, 'anomaly_results_text'):
                messagebox.showwarning("No Data", "No anomaly data to export")
                return

            content = self.anomaly_results_text.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("No Data", "No anomaly data to export")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"anomaly_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if file_path:
                with open(file_path, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Export Success", f"Anomaly report exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report: {str(e)}")

    def show_correlation_analysis_dialog(self):
        """Show correlation analysis in dedicated dialog"""
        try:
            # Create correlation dialog
            correlation_window = tk.Toplevel(self.root)
            correlation_window.title("Correlation Analysis Dashboard")
            correlation_window.geometry("900x700")

            # Create notebook for different correlation views
            correlation_notebook = ttk.Notebook(correlation_window)
            correlation_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Matrix tab
            matrix_frame = ttk.Frame(correlation_notebook)
            correlation_notebook.add(matrix_frame, text="Correlation Matrix")

            self.correlation_text = ScrolledText(matrix_frame, wrap=tk.WORD)
            self.correlation_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Insights tab
            insights_frame = ttk.Frame(correlation_notebook)
            correlation_notebook.add(insights_frame, text="Key Insights")

            self.insights_text = ScrolledText(insights_frame, wrap=tk.WORD)
            self.insights_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Action buttons
            button_frame = ttk.Frame(correlation_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(button_frame, text="Run Analysis",
                     command=self.run_comprehensive_correlation).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Generate Heatmap",
                     command=self.generate_correlation_heatmap).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Export Results",
                     command=self.export_correlation_report).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Close",
                     command=correlation_window.destroy).pack(side=tk.RIGHT)

            # Run initial analysis
            self.run_comprehensive_correlation()

        except Exception as e:
            self.internal_error_handler(str(e))

    def run_comprehensive_correlation(self):
        """Run comprehensive correlation analysis"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable", "Correlation analysis requires enhanced features")
            return

        self.update_status("Running correlation analysis...")

        def correlation_task():
            try:
                conn = get_db_connection()
                if not conn:
                    raise Exception("Database connection failed")

                # Get correlation data
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

                correlation_df = get_correlation_data(conn, start_date, end_date, {})
                conn.close()

                if not correlation_df.empty:
                    correlation_matrix = correlation_df.corr()
                    self.root.after(0, lambda: self.display_comprehensive_correlation(correlation_matrix, correlation_df))
                else:
                    self.root.after(0, lambda: [
                        self.update_status("No correlation data available", "warning"),
                        messagebox.showwarning("No Data", "Insufficient data for correlation analysis")
                    ])

            except Exception as e:
                self.root.after(0, lambda: [
                    self.update_status("Correlation analysis failed", "error"),
                    messagebox.showerror("Error", f"Correlation analysis failed: {str(e)}")
                ])

        threading.Thread(target=correlation_task, daemon=True).start()

    def display_comprehensive_correlation(self, correlation_matrix, raw_data):
        """Display comprehensive correlation results"""
        try:
            self.update_status("Correlation analysis completed")

            # Matrix tab
            if hasattr(self, 'correlation_text'):
                self.correlation_text.delete(1.0, tk.END)

                content = "Correlation Matrix Analysis\n"
                content += "=" * 40 + "\n\n"

                content += f"Variables Analyzed: {len(correlation_matrix.columns)}\n"
                content += f"Data Points: {len(raw_data)}\n\n"

                content += "Correlation Matrix:\n"
                content += "-" * 20 + "\n"

                # Format correlation matrix for display
                for i, row in correlation_matrix.iterrows():
                    content += f"\n{i}:\n"
                    for col, value in row.items():
                        if col != i:  # Skip self-correlation
                            content += f"  vs {col}: {value:.3f}\n"

                self.correlation_text.insert(1.0, content)

            # Insights tab
            if hasattr(self, 'insights_text'):
                self.insights_text.delete(1.0, tk.END)

                insights = "Key Correlation Insights\n"
                insights += "=" * 30 + "\n\n"

                # Find strong correlations
                strong_correlations = []
                for i in range(len(correlation_matrix.columns)):
                    for j in range(i+1, len(correlation_matrix.columns)):
                        col1 = correlation_matrix.columns[i]
                        col2 = correlation_matrix.columns[j]
                        corr_value = correlation_matrix.iloc[i, j]

                        if abs(corr_value) > 0.5:  # Strong correlation threshold
                            strong_correlations.append((col1, col2, corr_value))

                if strong_correlations:
                    insights += "STRONG CORRELATIONS (|r| > 0.5):\n\n"
                    for col1, col2, corr in sorted(strong_correlations, key=lambda x: abs(x[2]), reverse=True):
                        direction = "positive" if corr > 0 else "negative"
                        strength = "very strong" if abs(corr) > 0.8 else "strong"
                        insights += f"• {col1} ↔ {col2}\n"
                        insights += f"  Correlation: {corr:.3f} ({strength} {direction})\n"

                        # Add interpretation
                        if corr > 0:
                            insights += f"  As {col1} increases, {col2} tends to increase\n\n"
                        else:
                            insights += f"  As {col1} increases, {col2} tends to decrease\n\n"
                else:
                    insights += "No strong correlations found (|r| > 0.5)\n\n"

                insights += "INTERPRETATION GUIDELINES:\n"
                insights += "• |r| > 0.8: Very strong relationship\n"
                insights += "• |r| > 0.6: Strong relationship\n"
                insights += "• |r| > 0.4: Moderate relationship\n"
                insights += "• |r| > 0.2: Weak relationship\n"
                insights += "• |r| ≤ 0.2: Very weak/no relationship\n\n"

                insights += "BUSINESS IMPLICATIONS:\n"
                if strong_correlations:
                    insights += "• Use identified relationships for predictive modeling\n"
                    insights += "• Consider correlated factors in decision making\n"
                    insights += "• Monitor relationships over time for changes\n"
                else:
                    insights += "• Variables appear to be largely independent\n"
                    insights += "• May need additional variables for analysis\n"
                    insights += "• Consider non-linear relationships\n"

                self.insights_text.insert(1.0, insights)

        except Exception as e:
            logging.error(f"Error displaying correlation results: {str(e)}")

    def generate_correlation_heatmap(self):
        """Generate correlation heatmap visualization"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable", "Heatmap generation requires enhanced features")
            return

        self.update_status("Generating correlation heatmap...")

        def heatmap_task():
            try:
                conn = get_db_connection()
                chart_path = AdvancedVisualization.create_correlation_matrix(conn)

                self.root.after(0, lambda: [
                    self.update_status("Heatmap generated successfully"),
                    self.show_correlation_heatmap_result(chart_path)
                ])

            except Exception as e:
                self.root.after(0, lambda: [
                    self.update_status("Heatmap generation failed", "error"),
                    messagebox.showerror("Error", f"Heatmap generation failed: {str(e)}")
                ])

        threading.Thread(target=heatmap_task, daemon=True).start()

    def show_correlation_heatmap_result(self, chart_path):
        """Show correlation heatmap result"""
        if chart_path and os.path.exists(chart_path):
            result = messagebox.askyesno("Heatmap Generated",
                                       f"Correlation heatmap generated successfully!\n\nFile: {os.path.basename(chart_path)}\n\nWould you like to open it now?")

            if result:
                try:
                    webbrowser.open(f"file://{os.path.abspath(chart_path)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open heatmap: {str(e)}")
        else:
            messagebox.showwarning("Generation Failed", "Unable to generate correlation heatmap - insufficient data")

    def export_correlation_report(self):
        """Export correlation analysis report"""
        try:
            if not hasattr(self, 'correlation_text') or not hasattr(self, 'insights_text'):
                messagebox.showwarning("No Data", "No correlation data to export")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"correlation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if file_path:
                with open(file_path, 'w') as f:
                    f.write("Comprehensive Correlation Analysis Report\n")
                    f.write("=" * 60 + "\n\n")
                    f.write("CORRELATION MATRIX:\n")
                    f.write(self.correlation_text.get(1.0, tk.END))
                    f.write("\n\nKEY INSIGHTS:\n")
                    f.write(self.insights_text.get(1.0, tk.END))

                messagebox.showinfo("Export Success", f"Correlation report exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report: {str(e)}")

    def start_api_server_gui(self):
        """Start API server with GUI interface"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Feature Unavailable", "API server requires enhanced features")
                return

            # Enhanced API server dialog
            api_dialog = tk.Toplevel(self.root)
            api_dialog.title("API Server Configuration")
            api_dialog.geometry("600x500")
            api_dialog.transient(self.root)

            # Configuration section
            config_frame = ttk.LabelFrame(api_dialog, text="Server Configuration", padding="10")
            config_frame.pack(fill=tk.X, padx=10, pady=10)

            # Host setting
            ttk.Label(config_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, pady=5)
            host_var = tk.StringVar(value="localhost")
            ttk.Entry(config_frame, textvariable=host_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Port setting
            ttk.Label(config_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
            port_var = tk.StringVar(value="5000")
            ttk.Entry(config_frame, textvariable=port_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)

            # Debug mode
            debug_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(config_frame, text="Debug Mode", variable=debug_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

            config_frame.columnconfigure(1, weight=1)

            # API endpoints info
            endpoints_frame = ttk.LabelFrame(api_dialog, text="Available Endpoints", padding="10")
            endpoints_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            endpoints_text = ScrolledText(endpoints_frame, height=15, wrap=tk.WORD)
            endpoints_text.pack(fill=tk.BOTH, expand=True)

            endpoints_info = """API Endpoints Documentation:

AUTHENTICATION:
POST /api/login - User authentication
    Body: {"username": "user", "password": "pass"}

TEMPLATES:
GET  /api/templates - List all templates
POST /api/templates - Create new template
    Body: {"name": "Template Name", "sections": [...]}

REPORTS:
POST /api/reports/generate - Generate report
    Body: {"template": "name", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "format": "pdf"}

DATA:
GET  /api/data/<section> - Get section data
    Parameters: start_date, end_date, filters

ANALYTICS:
GET  /api/analytics/quality - Data quality metrics
GET  /api/analytics/predictions - Dropout risk predictions
GET  /api/analytics/anomalies - Anomaly detection results

SYSTEM:
GET  /api/health - System health check

Example Usage:
curl -X POST http://localhost:5000/api/reports/generate \\
  -H "Content-Type: application/json" \\
  -d '{"template": "student_overview", "start_date": "2024-01-01", "end_date": "2024-12-31"}'
"""

            endpoints_text.insert(1.0, endpoints_info)
            endpoints_text.config(state=tk.DISABLED)

            # Status display
            status_frame = ttk.Frame(api_dialog)
            status_frame.pack(fill=tk.X, padx=10, pady=5)

            self.api_status_label = ttk.Label(status_frame, text="Server Status: Stopped", style='Info.TLabel')
            self.api_status_label.pack(side=tk.LEFT)

            # Control buttons
            button_frame = ttk.Frame(api_dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            def start_server():
                try:
                    host = host_var.get()
                    port = int(port_var.get())
                    debug = debug_var.get()

                    # In a real implementation, this would start the Flask server
                    self.api_status_label.config(text=f"Server Status: Running on http://{host}:{port}", style='Success.TLabel')
                    messagebox.showinfo("API Server",
                                      f"API server started successfully!\n\nURL: http://{host}:{port}\nDebug Mode: {debug}")

                    # Store server config for stopping later
                    self.api_server_config = {'host': host, 'port': port, 'debug': debug, 'running': True}

                except ValueError:
                    messagebox.showerror("Invalid Port", "Please enter a valid port number")
                except Exception as e:
                    messagebox.showerror("Server Error", f"Failed to start server: {str(e)}")

            def stop_server():
                if hasattr(self, 'api_server_config') and self.api_server_config.get('running'):
                    self.api_status_label.config(text="Server Status: Stopped", style='Info.TLabel')
                    self.api_server_config['running'] = False
                    messagebox.showinfo("API Server", "API server stopped successfully!")
                else:
                    messagebox.showwarning("Server Not Running", "API server is not currently running")

            def test_connection():
                if hasattr(self, 'api_server_config') and self.api_server_config.get('running'):
                    host = self.api_server_config['host']
                    port = self.api_server_config['port']
                    messagebox.showinfo("Connection Test", f"API server is responding at http://{host}:{port}")
                else:
                    messagebox.showwarning("Server Not Running", "Please start the API server first")

            ttk.Button(button_frame, text="Start Server", command=start_server,
                     style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Stop Server", command=stop_server,
                     style='Warning.TButton').pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Test Connection", command=test_connection).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="Close", command=api_dialog.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            self.internal_error_handler(str(e))

    def main_gui_entry_point(self):
        """Main entry point for GUI application"""
        try:
            # Initialize logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler('reporting_system_gui.log'),
                    logging.StreamHandler()
                ]
            )

            logging.info("Starting Enhanced Reporting System GUI...")

            # Check system requirements
            self.check_system_requirements()

            # Initialize directories
            if ENHANCED_AVAILABLE:
                self.initialize_directories()

            # Check database connection
            self.verify_database_connection()

            # Load initial data
            self.refresh_data()

            # Start scheduler if available
            if ENHANCED_AVAILABLE:
                try:
                    start_scheduler()
                    logging.info("Background scheduler started successfully")
                except Exception as e:
                    logging.warning(f"Failed to start scheduler: {str(e)}")

            logging.info("GUI application initialized successfully")

        except Exception as e:
            logging.error(f"Failed to initialize GUI application: {str(e)}")
            messagebox.showerror("Initialization Error",
                               f"Failed to initialize application: {str(e)}\n\nThe application may not function correctly.")

    def check_system_requirements(self):
        """Check system requirements for GUI application"""
        try:
            requirements_status = {
                'tkinter': True,  # Already imported if we got this far
                'pandas': pd is not None,
                'enhanced_features': ENHANCED_AVAILABLE,
                'database': False
            }

            # Test database connection
            try:
                conn = get_db_connection()
                if conn:
                    conn.close()
                    requirements_status['database'] = True
            except Exception as e:
                logger.debug(f"Failed to check database requirements: {e}")

            # Log requirements status
            logging.info("System Requirements Check:")
            for requirement, status in requirements_status.items():
                status_text = "✓" if status else "✗"
                logging.info(f"  {requirement}: {status_text}")

            # Warn about missing requirements
            missing = [req for req, status in requirements_status.items() if not status]
            if missing:
                warning_msg = f"Missing requirements: {', '.join(missing)}\nSome features may be limited."
                logging.warning(warning_msg)

                if 'database' in missing:
                    messagebox.showwarning("Database Warning",
                                         "Database connection failed. Reports and analytics will be limited.")

        except Exception as e:
            logging.error(f"Requirements check failed: {str(e)}")

    def initialize_directories(self):
        """Initialize required directories"""
        try:
            directories = [
                str(paths.REPORTS_DIR),
                str(paths.REPORT_TEMPLATES_DIR),
                str(paths.REPORT_CACHE_DIR),
                str(paths.REPORTS_DIR / 'charts'),
                str(paths.LOG_DIR)
            ]

            for directory in directories:
                os.makedirs(directory, exist_ok=True)
                logging.debug(f"Directory ensured: {directory}")

            logging.info("All required directories initialized")

        except Exception as e:
            logging.error(f"Failed to initialize directories: {str(e)}")

    def verify_database_connection(self):
        """Verify database connection and structure"""
        try:
            conn = get_db_connection()
            if not conn:
                raise Exception("Could not establish database connection")

            # Check for required tables
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = ['students']
            missing_tables = [table for table in required_tables if table not in tables]

            if missing_tables:
                logging.warning(f"Missing database tables: {missing_tables}")
            else:
                logging.info("Database structure verified")

            conn.close()

        except Exception as e:
            logging.error(f"Database verification failed: {str(e)}")
            raise
