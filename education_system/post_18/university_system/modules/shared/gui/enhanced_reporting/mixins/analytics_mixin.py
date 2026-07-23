"""Analytics methods mixin for the enhanced reporting GUI."""

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (
    tk, ttk, filedialog, messagebox,
    ScrolledText,
    threading, webbrowser, os, json, logging,
    datetime, timedelta, pd,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
    _t,
    DataQualityMonitor, PredictiveAnalytics, AdvancedVisualization,
    CacheManager,
)


class AnalyticsMixin:
    """Mixin providing analytics, quality checks, and visualization methods."""

    def run_quality_check(self):
        """Run data quality check"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable",
                                 "Data quality checking requires the enhanced system.")
            return

        self.update_status("Running data quality check...")
        self.start_progress()

        def quality_task():
            try:
                quality_report = DataQualityMonitor.run_quality_checks()
                self.root.after(0, lambda: self._display_quality_results(quality_report))
            except Exception as e:
                self.root.after(0, lambda _e=e: [
                    self.update_status(f"Quality check failed: {_e}", "error"),
                    messagebox.showerror("Error", f"Failed to run quality check: {str(_e)}")
                ])

        threading.Thread(target=quality_task, daemon=True).start()

    def _display_quality_results(self, quality_report):
        """Display quality check results in separate window"""
        self.stop_progress()
        self.update_status("Quality check completed")

        # Create new window for quality results
        quality_window = tk.Toplevel(self.root)
        quality_window.title("Data Quality Report")
        quality_window.geometry("700x600")

        # Results display
        quality_text = ScrolledText(quality_window, wrap=tk.WORD)
        quality_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        output = f"Data Quality Report - {quality_report['timestamp']}\n"
        output += "=" * 60 + "\n\n"

        checks = quality_report.get('checks', {})

        if 'missing_data' in checks:
            missing = checks['missing_data']['students']
            total = missing['total_records']
            output += "📊 MISSING DATA ANALYSIS:\n"
            output += f"   Total Records: {total}\n"
            output += f"   Missing Emails: {missing['missing_emails']}\n"
            output += f"   Missing Names: {missing['missing_names']}\n"
            output += f"   Missing Courses: {missing['missing_courses']}\n"

            if total > 0:
                completeness = ((total * 3) - (missing['missing_emails'] + missing['missing_names'] + missing['missing_courses'])) / (total * 3) * 100
                output += f"   Data Completeness: {completeness:.1f}%\n"

                if completeness < 90:
                    output += "   ⚠️  Warning: Data completeness below 90%\n"
                else:
                    output += "   ✅ Good data completeness\n"
            output += "\n"

        if 'duplicates' in checks:
            duplicates = checks['duplicates']
            output += "👥 DUPLICATE ANALYSIS:\n"
            output += f"   Duplicate Emails: {duplicates['duplicate_emails']}\n"

            if duplicates['duplicate_emails'] > 0:
                output += "   📋 Duplicate Email Details:\n"
                for detail in duplicates.get('duplicate_email_details', [])[:5]:
                    output += f"      {detail['email']}: {detail['count']} occurrences\n"
                output += "   ⚠️  Action Required: Review duplicate emails\n"
            else:
                output += "   ✅ No duplicate emails found\n"
            output += "\n"

        if 'invalid_data' in checks:
            invalid = checks['invalid_data']
            output += "❌ INVALID DATA ANALYSIS:\n"
            output += f"   Invalid Ages: {invalid['invalid_ages']}\n"
            output += f"   Invalid Emails: {invalid['invalid_emails']}\n"

            if invalid['invalid_ages'] > 0 or invalid['invalid_emails'] > 0:
                output += "   ⚠️  Action Required: Clean invalid data\n"
            else:
                output += "   ✅ No invalid data found\n"
            output += "\n"

        if 'data_freshness' in checks:
            freshness = checks['data_freshness']
            if freshness['last_registration_date']:
                days_since = freshness['days_since_last_registration']
                output += "📅 DATA FRESHNESS:\n"
                output += f"   Last Registration: {freshness['last_registration_date']}\n"
                output += f"   Days Since Last: {days_since}\n"

                if days_since > 7:
                    output += "   ⚠️  Warning: No recent registrations\n"
                else:
                    output += "   ✅ Recent data available\n"
            else:
                output += "📅 DATA FRESHNESS:\n"
                output += "   ❌ No registration data found\n"

        quality_text.insert(1.0, output)
        quality_text.config(state=tk.DISABLED)

        # Action buttons
        button_frame = ttk.Frame(quality_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="💾 Save Report",
                  command=lambda: self._save_analytics_report(output, "quality_report")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="📧 Send to Admin",
                  command=lambda: self._send_report_to_admin(output, "Data Quality Report")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close",
                  command=quality_window.destroy).pack(side=tk.RIGHT)

    def export_quality_report(self):
        """Export quality report to file"""
        content = self.quality_display.get(1.0, tk.END).strip()
        if not content:
            messagebox.showwarning("No Data", "No quality report data to export.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Quality report exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report: {str(e)}")

    def run_predictions(self):
        """Run predictive analytics"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable",
                                 "Predictive analytics requires the enhanced system.")
            return

        self.update_status("Running predictive analytics...")
        self.start_progress()

        def predictions_task():
            try:
                predictions = PredictiveAnalytics.predict_dropout_risk()
                self.root.after(0, lambda: self._display_predictions_results(predictions))
            except Exception as e:
                self.root.after(0, lambda _e=e: [
                    self.stop_progress(),
                    self.update_status(f"Predictions failed: {str(_e)}", "error"),
                    messagebox.showerror("Error", f"Failed to run predictions: {str(_e)}")
                ])

        threading.Thread(target=predictions_task, daemon=True).start()

    def _display_predictions_results(self, predictions):
        """Display prediction results in separate window"""
        self.stop_progress()
        self.update_status("Predictions completed")

        # Create new window for predictions results
        predictions_window = tk.Toplevel(self.root)
        predictions_window.title("Predictive Analytics Report")
        predictions_window.geometry("700x600")

        # Results display
        predictions_text = ScrolledText(predictions_window, wrap=tk.WORD)
        predictions_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        output = "Predictive Analytics Report\n"
        output += "=" * 40 + "\n\n"

        if 'error' in predictions:
            output += f"❌ Analysis unavailable: {predictions['error']}\n"
        else:
            output += "🎯 DROPOUT RISK ANALYSIS:\n\n"

            if 'model_accuracy' in predictions:
                accuracy = predictions['model_accuracy'] * 100
                output += f"   Model Accuracy: {accuracy:.1f}%\n"

                if accuracy > 80:
                    output += "   ✅ High confidence predictions\n"
                elif accuracy > 60:
                    output += "   ⚠️  Moderate confidence predictions\n"
                else:
                    output += "   ❌ Low confidence - more data needed\n"

            if 'total_students_analyzed' in predictions:
                output += f"   Students Analyzed: {predictions['total_students_analyzed']}\n"

            if 'high_risk_students' in predictions:
                high_risk = predictions['high_risk_students']
                output += f"   High Risk Students: {len(high_risk)}\n\n"

                if high_risk:
                    output += "   🚨 Students requiring attention:\n"
                    for student in high_risk[:10]:  # Show top 10
                        output += f"      Student ID: {student['student_id']} (Risk: {student['risk_score']:.2%})\n"

                    if len(high_risk) > 10:
                        output += f"      ... and {len(high_risk) - 10} more\n"

            if 'feature_importance' in predictions:
                importance = predictions['feature_importance']
                sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)

                output += "\n   📈 Most Important Risk Factors:\n"
                for feature, score in sorted_features:
                    feature_name = feature.replace('_', ' ').title()
                    output += f"      {feature_name}: {score:.3f}\n"

        predictions_text.insert(1.0, output)
        predictions_text.config(state=tk.DISABLED)

        # Action buttons
        button_frame = ttk.Frame(predictions_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="💾 Save Report",
                  command=lambda: self._save_analytics_report(output, "predictions_report")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="📧 Send to Admin",
                  command=lambda: self._send_report_to_admin(output, "Predictive Analytics Report")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close",
                  command=predictions_window.destroy).pack(side=tk.RIGHT)

    def run_anomaly_detection(self):
        """Run anomaly detection"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable",
                                 "Anomaly detection requires the enhanced system.")
            return

        self.update_status("Running anomaly detection...")
        self.start_progress()

        def anomaly_task():
            try:
                anomalies = PredictiveAnalytics.detect_anomalies()
                self.root.after(0, lambda: self._display_anomaly_results(anomalies))
            except Exception as e:
                self.root.after(0, lambda _e=e: [
                    self.stop_progress(),
                    self.update_status(f"Anomaly detection failed: {str(_e)}", "error"),
                    messagebox.showerror("Error", f"Failed to run anomaly detection: {str(_e)}")
                ])

        threading.Thread(target=anomaly_task, daemon=True).start()

    def _display_anomaly_results(self, anomalies):
        """Display anomaly detection results"""
        self.stop_progress()
        self.update_status("Anomaly detection completed")

        # Create new window for anomaly results
        anomaly_window = tk.Toplevel(self.root)
        anomaly_window.title("Anomaly Detection Results")
        anomaly_window.geometry("700x600")

        # Results display
        anomaly_text = ScrolledText(anomaly_window, wrap=tk.WORD)
        anomaly_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        output = "Anomaly Detection Results\n"
        output += "=" * 35 + "\n\n"

        if 'error' in anomalies:
            output += f"❌ Analysis unavailable: {anomalies['error']}\n"
        else:
            output += "🔍 ANOMALY DETECTION RESULTS:\n\n"

            anomaly_count = anomalies.get('total_anomalies', 0)
            anomaly_rate = anomalies.get('anomaly_rate', 0)

            output += f"   Anomalous Students: {anomaly_count}\n"
            output += f"   Anomaly Rate: {anomaly_rate:.2f}%\n\n"

            if anomaly_rate > 15:
                output += "   ⚠️  High anomaly rate - investigate data quality\n"
            elif anomaly_rate > 5:
                output += "   ⚠️  Moderate anomalies detected\n"
            else:
                output += "   ✅ Normal anomaly rate\n"

            if 'anomalous_students' in anomalies and anomalies['anomalous_students']:
                output += "\n   🔍 Anomalous Student Profiles:\n\n"

                for student in anomalies['anomalous_students'][:10]:
                    output += f"      Student ID: {student['student_id']}\n"
                    output += f"         Age: {student['age']}\n"
                    output += f"         Modules: {student['unique_modules']}\n"
                    output += f"         Avg Grade: {student.get('avg_grade', 'N/A')}\n\n"

                if len(anomalies['anomalous_students']) > 10:
                    remaining = len(anomalies['anomalous_students']) - 10
                    output += f"      ... and {remaining} more anomalous profiles\n"

        anomaly_text.insert(1.0, output)
        anomaly_text.config(state=tk.DISABLED)

        # Action buttons
        button_frame = ttk.Frame(anomaly_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="💾 Save Report",
                  command=lambda: self._save_analytics_report(output, "anomaly_report")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="📧 Send to Admin",
                  command=lambda: self._send_report_to_admin(output, "Anomaly Detection Report")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close",
                  command=anomaly_window.destroy).pack(side=tk.RIGHT)

    def run_correlation_analysis(self):
        """Run correlation analysis"""
        if not ENHANCED_AVAILABLE:
            messagebox.showwarning("Feature Unavailable",
                                 "Correlation analysis requires the enhanced system.")
            return

        self.update_status("Running correlation analysis...")
        self.start_progress()

        def correlation_task():
            try:
                conn = get_db_connection()
                chart_path = AdvancedVisualization.create_correlation_matrix(conn)

                self.root.after(0, lambda: [
                    self.stop_progress(),
                    self.update_status("Correlation analysis completed"),
                    self._show_correlation_results(chart_path)
                ])

            except Exception as e:
                self.root.after(0, lambda _e=e: [
                    self.stop_progress(),
                    self.update_status(f"Correlation analysis failed: {str(_e)}", "error"),
                    messagebox.showerror("Error", f"Failed to run correlation analysis: {str(_e)}")
                ])

        threading.Thread(target=correlation_task, daemon=True).start()

    def _show_correlation_results(self, chart_path):
        """Show correlation analysis results"""
        if chart_path and os.path.exists(chart_path):
            messagebox.showinfo("Correlation Analysis",
                              f"✅ Correlation matrix generated successfully!\n\n📊 Chart saved to: {os.path.basename(chart_path)}")

            # Open the chart
            try:
                webbrowser.open(f"file://{os.path.abspath(chart_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open chart: {str(e)}")
        else:
            messagebox.showwarning("No Results", "❌ Unable to generate correlation matrix - insufficient data")

    def run_quality_checks(self):
        """Run comprehensive data quality checks and display results"""
        try:
            self.update_status("Running quality checks...")
            self.start_progress()

            def run_checks():
                try:
                    if not ENHANCED_AVAILABLE:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Not Available", "Enhanced features not available"))
                        return

                    quality_report = DataQualityMonitor.run_quality_checks()
                    self.root.after(0, lambda: self.display_quality_checks_results(quality_report))
                except Exception as e:
                    self.root.after(0, lambda _e=e: messagebox.showerror(
                        "Error", f"Quality check failed: {str(_e)}"))
                finally:
                    self.root.after(0, self.stop_progress)
                    self.root.after(0, lambda: self.update_status("Quality checks complete"))

            threading.Thread(target=run_checks, daemon=True).start()
        except Exception as e:
            self.stop_progress()
            messagebox.showerror("Error", f"Failed to start quality checks: {str(e)}")

    def display_quality_checks_results(self, quality_report):
        """Display quality check results in a GUI dialog"""
        try:
            results_window = tk.Toplevel(self.root)
            results_window.title("Data Quality Check Results")
            results_window.geometry("700x600")
            results_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(results_window)
            header_frame.pack(fill=tk.X, padx=20, pady=10)

            ttk.Label(header_frame, text="🔍 Data Quality Dashboard",
                     font=('Arial', 16, 'bold')).pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Generated: {quality_report.get('timestamp', 'N/A')}",
                     font=('Arial', 10)).pack(anchor=tk.W)

            # Results notebook
            notebook = ttk.Notebook(results_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            checks = quality_report.get('checks', {})

            # Missing Data Tab
            if 'missing_data' in checks:
                missing_frame = ttk.Frame(notebook)
                notebook.add(missing_frame, text="Missing Data")

                missing_text = ScrolledText(missing_frame, wrap=tk.WORD, height=20)
                missing_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                missing = checks['missing_data'].get('students', {})
                missing_text.insert(tk.END, f"Total Records: {missing.get('total_records', 0)}\n")
                missing_text.insert(tk.END, f"Missing Emails: {missing.get('missing_emails', 0)}\n")
                missing_text.insert(tk.END, f"Missing Names: {missing.get('missing_names', 0)}\n\n")
                missing_text.config(state=tk.DISABLED)

            # Duplicates Tab
            if 'duplicates' in checks:
                dup_frame = ttk.Frame(notebook)
                notebook.add(dup_frame, text="Duplicates")

                dup_text = ScrolledText(dup_frame, wrap=tk.WORD, height=20)
                dup_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                duplicates = checks['duplicates']
                dup_text.insert(tk.END, f"Duplicate Students: {duplicates.get('duplicate_count', 0)}\n\n")

                if duplicates.get('examples'):
                    dup_text.insert(tk.END, "Examples:\n")
                    for example in duplicates['examples'][:10]:
                        dup_text.insert(tk.END, f"  • {example}\n")

                dup_text.config(state=tk.DISABLED)

            # Invalid Data Tab
            if 'invalid_data' in checks:
                invalid_frame = ttk.Frame(notebook)
                notebook.add(invalid_frame, text="Invalid Data")

                invalid_text = ScrolledText(invalid_frame, wrap=tk.WORD, height=20)
                invalid_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                invalid = checks['invalid_data']
                invalid_text.insert(tk.END, f"Invalid Email Count: {invalid.get('invalid_email_count', 0)}\n")
                invalid_text.insert(tk.END, f"Out of Range Scores: {invalid.get('out_of_range_scores', 0)}\n\n")
                invalid_text.config(state=tk.DISABLED)

            # Data Freshness Tab
            if 'data_freshness' in checks:
                fresh_frame = ttk.Frame(notebook)
                notebook.add(fresh_frame, text="Data Freshness")

                fresh_text = ScrolledText(fresh_frame, wrap=tk.WORD, height=20)
                fresh_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                freshness = checks['data_freshness']
                fresh_text.insert(tk.END, f"Last Update: {freshness.get('last_update', 'N/A')}\n")
                fresh_text.insert(tk.END, f"Days Since Update: {freshness.get('days_since_update', 'N/A')}\n")
                fresh_text.insert(tk.END, f"Status: {freshness.get('status', 'N/A')}\n\n")
                fresh_text.config(state=tk.DISABLED)

            # Close button
            ttk.Button(results_window, text="Close",
                      command=results_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to display quality results: {str(e)}")

    def show_data_quality_dashboard(self):
        """Show comprehensive data quality dashboard"""
        self.run_quality_checks()

    def check_missing_data(self):
        """Check for missing data in the database"""
        try:
            if not ENHANCED_AVAILABLE:
                return None

            conn = get_db_connection()
            if not conn:
                return None

            return DataQualityMonitor.check_missing_data(conn)
        except Exception as e:
            logging.error(f"Error checking missing data: {str(e)}")
            return None

    def check_duplicates(self):
        """Check for duplicate records"""
        try:
            if not ENHANCED_AVAILABLE:
                return None

            conn = get_db_connection()
            if not conn:
                return None

            return DataQualityMonitor.check_duplicates(conn)
        except Exception as e:
            logging.error(f"Error checking duplicates: {str(e)}")
            return None

    def check_invalid_data(self):
        """Check for invalid data"""
        try:
            if not ENHANCED_AVAILABLE:
                return None

            conn = get_db_connection()
            if not conn:
                return None

            return DataQualityMonitor.check_invalid_data(conn)
        except Exception as e:
            logging.error(f"Error checking invalid data: {str(e)}")
            return None

    def check_data_freshness(self):
        """Check data freshness"""
        try:
            if not ENHANCED_AVAILABLE:
                return None

            conn = get_db_connection()
            if not conn:
                return None

            return DataQualityMonitor.check_data_freshness(conn)
        except Exception as e:
            logging.error(f"Error checking data freshness: {str(e)}")
            return None

    # ===== ANALYTICS & VISUALIZATION METHODS =====

    def create_correlation_matrix(self):
        """Create and display correlation matrix"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return

            self.update_status("Creating correlation matrix...")
            self.start_progress()

            def create_matrix():
                try:
                    conn = get_db_connection()
                    if not conn:
                        self.root.after(0, lambda: messagebox.showerror("Error", "Database connection failed"))
                        return

                    chart_path = AdvancedVisualization.create_correlation_matrix(conn)

                    if chart_path:
                        self.root.after(0, lambda: self.show_visualization_result(
                            chart_path, "Correlation Matrix"))
                    else:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "No Data", "Insufficient data to create correlation matrix"))
                except Exception as e:
                    self.root.after(0, lambda _e=e: messagebox.showerror(
                        "Error", f"Failed to create correlation matrix: {str(_e)}"))
                finally:
                    self.root.after(0, self.stop_progress)
                    self.root.after(0, lambda: self.update_status("Ready"))

            threading.Thread(target=create_matrix, daemon=True).start()
        except Exception as e:
            self.stop_progress()
            messagebox.showerror("Error", f"Failed to start correlation analysis: {str(e)}")

    def create_heatmap(self, data, title, x_col, y_col, value_col):
        """Create heatmap visualization"""
        try:
            if not ENHANCED_AVAILABLE:
                return None

            chart_path = AdvancedVisualization.create_heatmap(data, title, x_col, y_col, value_col)

            if chart_path:
                self.show_visualization_result(chart_path, title)

            return chart_path
        except Exception as e:
            logging.error(f"Error creating heatmap: {str(e)}")
            return None

    def create_interactive_dashboard(self):
        """Create interactive dashboard"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return

            self.update_status("Creating interactive dashboard...")
            self.start_progress()

            def create_dashboard():
                try:
                    conn = get_db_connection()
                    if not conn:
                        self.root.after(0, lambda: messagebox.showerror("Error", "Database connection failed"))
                        return

                    # Gather data for dashboard
                    cursor = conn.cursor()
                    cursor.execute("SELECT course, COUNT(*) as student_count FROM students GROUP BY course")
                    course_data = cursor.fetchall()

                    data_dict = {
                        'course_distribution': {
                            'course': [row[0] for row in course_data],
                            'student_count': [row[1] for row in course_data]
                        }
                    }

                    dashboard_path = AdvancedVisualization.create_interactive_dashboard(data_dict)

                    if dashboard_path:
                        self.root.after(0, lambda: self.show_visualization_result(
                            dashboard_path, "Interactive Dashboard", is_html=True))
                    else:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "No Data", "Could not create dashboard"))
                except Exception as e:
                    self.root.after(0, lambda _e=e: messagebox.showerror(
                        "Error", f"Failed to create dashboard: {str(_e)}"))
                finally:
                    self.root.after(0, self.stop_progress)
                    self.root.after(0, lambda: self.update_status("Ready"))

            threading.Thread(target=create_dashboard, daemon=True).start()
        except Exception as e:
            self.stop_progress()
            messagebox.showerror("Error", f"Failed to start dashboard creation: {str(e)}")

    def show_visualization_result(self, file_path, title, is_html=False):
        """Show visualization result in browser or viewer"""
        try:
            result_window = tk.Toplevel(self.root)
            result_window.title(title)
            result_window.geometry("500x200")
            result_window.transient(self.root)

            ttk.Label(result_window, text=f"✅ {title} Created Successfully!",
                     font=('Arial', 12, 'bold')).pack(pady=20)

            ttk.Label(result_window, text=f"File: {os.path.basename(file_path)}").pack(pady=10)

            button_frame = ttk.Frame(result_window)
            button_frame.pack(pady=20)

            def open_file():
                try:
                    webbrowser.open(f"file://{os.path.abspath(file_path)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open file: {str(e)}")

            ttk.Button(button_frame, text="Open File", command=open_file,
                      style='Success.TButton').pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=result_window.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show result: {str(e)}")

    def detect_anomalies(self):
        """Detect anomalies in student data"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return

            self.update_status("Detecting anomalies...")
            self.start_progress()

            def detect():
                try:
                    anomalies = PredictiveAnalytics.detect_anomalies()
                    self.root.after(0, lambda: self.display_comprehensive_anomalies(anomalies))
                except Exception as e:
                    self.root.after(0, lambda _e=e: messagebox.showerror(
                        "Error", f"Anomaly detection failed: {str(_e)}"))
                finally:
                    self.root.after(0, self.stop_progress)
                    self.root.after(0, lambda: self.update_status("Anomaly detection complete"))

            threading.Thread(target=detect, daemon=True).start()
        except Exception as e:
            self.stop_progress()
            messagebox.showerror("Error", f"Failed to start anomaly detection: {str(e)}")

    def predict_dropout_risk(self):
        """Predict student dropout risk"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return

            self.update_status("Predicting dropout risk...")
            self.start_progress()

            def predict():
                try:
                    predictions = PredictiveAnalytics.predict_dropout_risk()
                    self.root.after(0, lambda: self.display_comprehensive_predictions(predictions))
                except Exception as e:
                    self.root.after(0, lambda _e=e: messagebox.showerror(
                        "Error", f"Prediction failed: {str(_e)}"))
                finally:
                    self.root.after(0, self.stop_progress)
                    self.root.after(0, lambda: self.update_status("Prediction complete"))

            threading.Thread(target=predict, daemon=True).start()
        except Exception as e:
            self.stop_progress()
            messagebox.showerror("Error", f"Failed to start prediction: {str(e)}")
