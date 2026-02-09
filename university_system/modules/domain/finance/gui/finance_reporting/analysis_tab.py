import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import threading
from datetime import datetime, timedelta
import json
import webbrowser
from pathlib import Path
import matplotlib
from university_system.modules.shared.constants import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Import the shared authentication system
try:
    from university_system.infrastructure.auth import UserAuth
    from university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import analytics classes
from university_system.modules.domain.finance.gui.finance_reporting.analytics_classes import (
    CashFlowForecaster,
    AnomalyDetector,
    StudentLifecycleAnalyzer,
    PaymentPredictionML,
    ComparativeAnalyzer,
    FinancialAlertSystem,
)

# Import standalone functions
from university_system.modules.domain.finance.gui.finance_reporting.misc import (
    generate_advanced_financial_forecasting,
    scenario_planning_tools,
)

# Import email service
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.email.template_utils import render_template
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False
    send_email = None
    render_template = None


def get_admin_email():
    """Get admin email from database"""
    try:
        from university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
            )
            result = cursor.fetchone()
            if result:
                return result[0]
    except Exception as e:
        print(f"Error getting admin email: {e}")
    return None


def send_report_to_admin(report_title, report_content, parent_window=None):
    """Send a report to the admin via email"""
    if not HAS_EMAIL:
        messagebox.showerror("Error", "Email system not available")
        return False

    admin_email = get_admin_email()
    if not admin_email:
        messagebox.showerror("Error", "No admin email found in database.\nPlease ensure an admin user has an email configured.")
        return False

    try:
        generated_date = datetime.now().strftime('%Y-%m-%d %H:%M')
        generated_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Render email from template
        subject, body = render_template('reports/finance_report', {
            'report_title': report_title,
            'generated_date': generated_date,
            'generated_timestamp': generated_timestamp,
            'report_content': report_content
        })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Finance Report: {report_title} - {generated_date}"
            body = f"Finance Report: {report_title}\nGenerated: {generated_timestamp}\n\n{report_content}"

        result = send_email(admin_email, subject, body)
        if result:
            messagebox.showinfo("Success", f"Report sent to admin at:\n{admin_email}")
            return True
        else:
            messagebox.showerror("Error", "Failed to send email. Please check email configuration.")
            return False
    except Exception as e:
        messagebox.showerror("Error", f"Failed to send report:\n{e}")
        return False


# This module defines mixin functions for FinancialManagementGUI
# Note: Methods are registered by main.py to avoid circular imports

def create_analysis_tab(self):
    """Create analysis tab with interactive tools"""
    analysis_frame = ttk.Frame(self.notebook, padding="10")
    self.notebook.add(analysis_frame, text=_("finance_reporting.tabs.analysis"))

    # Analysis controls
    controls_frame = ttk.LabelFrame(analysis_frame, text=_("finance_reporting.analysis.controls"), padding="10")
    controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    # Analysis type selection
    ttk.Label(controls_frame, text=_("finance_reporting.analysis.type")).grid(row=0, column=0, sticky=tk.W)
    self.analysis_type = tk.StringVar(value="forecasting")
    analysis_combo = ttk.Combobox(controls_frame, textvariable=self.analysis_type, 
                                 values=["forecasting", "risk_analysis", "cash_flow", "scenario_planning"],
                                 state="readonly")
    analysis_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

    # Date range selection
    ttk.Label(controls_frame, text=_("finance_reporting.analysis.date_range")).grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
    date_frame = ttk.Frame(controls_frame)
    date_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

    self.start_date = tk.StringVar(value=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
    self.end_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))

    ttk.Entry(date_frame, textvariable=self.start_date, width=12).grid(row=0, column=0)
    ttk.Label(date_frame, text=_("finance_reporting.analysis.to")).grid(row=0, column=1)
    ttk.Entry(date_frame, textvariable=self.end_date, width=12).grid(row=0, column=2)

    # Run analysis button
    ttk.Button(controls_frame, text=_("finance_reporting.buttons.run_analysis"), command=self.run_selected_analysis,
              style='Accent.TButton').grid(row=2, column=0, columnspan=2, pady=(10, 0))

    controls_frame.grid_columnconfigure(1, weight=1)

    # Results display
    results_frame = ttk.LabelFrame(analysis_frame, text=_("finance_reporting.analysis.results"), padding="10")
    results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

    self.results_text = ScrolledText(results_frame, height=20, wrap=tk.WORD)
    self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    results_frame.grid_rowconfigure(0, weight=1)
    results_frame.grid_columnconfigure(0, weight=1)
    analysis_frame.grid_rowconfigure(1, weight=1)
    analysis_frame.grid_columnconfigure(0, weight=1)

def run_student_lifecycle_analysis(self):
    """Run student lifecycle analysis"""
    self.update_status("Running student lifecycle analysis...")

    def analysis_in_background():
        try:
            lifecycle_analyzer = StudentLifecycleAnalyzer()
            data = lifecycle_analyzer.analyze_student_lifecycle()

            if data:
                total_students = data.get('summary_stats', {}).get('total_students', 'unknown number of')
                self.root.after(0, lambda: [
                    self.log_activity(f"Student lifecycle analysis completed - {total_students} students analyzed"),
                    self.update_status("Ready"),
                    self.show_lifecycle_results(data)
                ])
            else:
                self.root.after(0, lambda: [
                    self.log_activity("Student lifecycle analysis failed - no data available"),
                    self.update_status("Ready"),
                    messagebox.showinfo("Analysis Complete", "No data available for student lifecycle analysis")
                ])
        except Exception as e:
            self.root.after(0, lambda: [
                self.log_activity(f"Lifecycle analysis error: {e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Student lifecycle analysis failed: {e}")
            ])

    thread = threading.Thread(target=analysis_in_background)
    thread.daemon = True
    thread.start()

def show_lifecycle_results(self, lifecycle_data):
    """Show lifecycle analysis results in new window"""
    lifecycle_window = tk.Toplevel(self.root)
    lifecycle_window.title(_("finance_reporting.windows.lifecycle_analysis"))
    lifecycle_window.geometry("1000x700")

    main_frame = ttk.Frame(lifecycle_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Student Lifecycle Analysis Results", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Summary stats
    stats_frame = ttk.LabelFrame(main_frame, text="Summary Statistics", padding="10")
    stats_frame.pack(fill=tk.X, pady=(0, 10))

    summary = lifecycle_data['summary_stats']
    stats_text = f"Total Students: {summary['total_students']} | Avg Collection Rate: {summary['avg_collection_rate']:.1f}% | High Risk: {summary['high_risk_students']} | Scholarship Recipients: {summary['scholarship_recipients']}"
    ttk.Label(stats_frame, text=stats_text).pack()

    # Results treeview
    results_tree = ttk.Treeview(main_frame, columns=('Stage', 'Collection Rate', 'Payment Frequency', 'Total Fees'), height=15)
    results_tree.heading('#0', text='Student Name')
    results_tree.heading('Stage', text='Lifecycle Stage')
    results_tree.heading('Collection Rate', text='Collection Rate')
    results_tree.heading('Payment Frequency', text='Payment Frequency')
    results_tree.heading('Total Fees', text='Total Fees')
    results_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Populate results
    for idx, row in lifecycle_data['student_data'].head(50).iterrows():  # Show first 50
        results_tree.insert('', 'end', text=f"{row['first_name']} {row['last_name']}",
                          values=(row['lifecycle_stage'],
                                f"{row['collection_rate']:.1f}%",
                                f"{row['payment_frequency']:.2f}",
                                f"£{row['total_fees']:,.2f}"))

    ttk.Button(main_frame, text="Close", command=lifecycle_window.destroy).pack(pady=10)

def run_comparative_analysis(self):
    """Run comparative analysis with GUI display"""
    self.update_status("Running comparative analysis...")

    def analysis_in_background():
        try:
            comparative_analyzer = ComparativeAnalyzer()
            yoy_data = comparative_analyzer.year_over_year_analysis()
            dept_data = comparative_analyzer.department_comparison()

            self.root.after(0, lambda: [
                self.log_activity("Comparative analysis completed"),
                self.update_status("Ready"),
                self.show_comparative_results(yoy_data, dept_data)
            ])
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: [
                self.log_activity(f"Comparative analysis error: {error_msg}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Comparative analysis failed: {error_msg}")
            ])

    thread = threading.Thread(target=analysis_in_background)
    thread.daemon = True
    thread.start()

def show_comparative_results(self, yoy_data, dept_data):
    """Show comparative analysis results in new window"""
    comp_window = tk.Toplevel(self.root)
    comp_window.title(_("finance_reporting.windows.comparative_analysis"))
    comp_window.geometry("1200x800")

    main_frame = ttk.Frame(comp_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Comparative Analysis Results", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Create notebook for different analyses
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True)

    # Year-over-Year tab
    yoy_frame = ttk.Frame(notebook, padding="10")
    notebook.add(yoy_frame, text="Year-over-Year")

    if yoy_data:
        yoy_tree = ttk.Treeview(yoy_frame, columns=('Expected', 'Collected', 'Rate', 'Students'), height=10)
        yoy_tree.heading('#0', text='Academic Year')
        yoy_tree.heading('Expected', text='Expected Revenue')
        yoy_tree.heading('Collected', text='Collected Revenue')
        yoy_tree.heading('Rate', text='Collection Rate')
        yoy_tree.heading('Students', text='Student Count')
        yoy_tree.pack(fill=tk.BOTH, expand=True)

        for year, data in yoy_data.items():
            yoy_tree.insert('', 'end', text=year,
                          values=(f"£{data['total_expected']:,.2f}",
                                f"£{data['total_collected']:,.2f}",
                                f"{data['collection_rate']:.1f}%",
                                data['student_count']))

    # Department comparison tab
    dept_frame = ttk.Frame(notebook, padding="10")
    notebook.add(dept_frame, text="Department Comparison")

    if dept_data is not None and len(dept_data) > 0:
        dept_tree = ttk.Treeview(dept_frame, columns=('Students', 'Total Fees', 'Collected', 'Rate'), height=15)
        dept_tree.heading('#0', text='Department')
        dept_tree.heading('Students', text='Student Count')
        dept_tree.heading('Total Fees', text='Total Fees')
        dept_tree.heading('Collected', text='Collected Fees')
        dept_tree.heading('Rate', text='Collection Rate')
        dept_tree.pack(fill=tk.BOTH, expand=True)

        for idx, row in dept_data.iterrows():
            dept_tree.insert('', 'end', text=row['department'],
                           values=(row['student_count'],
                                 f"£{row['total_fees']:,.2f}",
                                 f"£{row['collected_fees']:,.2f}",
                                 f"{row['collection_rate']:.1f}%"))

def run_performance_optimization(self):
    """Run system performance optimization with GUI display"""
    self.update_status("Running performance optimization...")

    def optimize_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Database optimization steps
            optimization_steps = []

            # Create performance indexes
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_student_fees_student_id ON student_fees(student_id)',
                'CREATE INDEX IF NOT EXISTS idx_payments_student_id ON payments(student_id)',
                'CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)',
                'CREATE INDEX IF NOT EXISTS idx_student_fees_status ON student_fees(status)'
            ]

            for index_sql in indexes:
                cursor.execute(index_sql)
                optimization_steps.append("Database index created")

            # Analyze tables
            cursor.execute('ANALYZE')
            optimization_steps.append("Database statistics updated")

            # Check table sizes
            tables = ['students', 'student_fees', 'payments', 'fee_types']
            table_info = []
            for table in tables:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                table_info.append(f"{table}: {count:,} records")

            conn.commit()
            conn.close()

            self.root.after(0, lambda: [
                self.log_activity("Performance optimization completed"),
                self.update_status("Ready"),
                self.show_optimization_results(optimization_steps, table_info)
            ])

        except Exception as e:
            self.root.after(0, lambda: [
                self.log_activity(f"Performance optimization error: {e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Performance optimization failed: {e}")
            ])

    thread = threading.Thread(target=optimize_in_background)
    thread.daemon = True
    thread.start()

def show_optimization_results(self, steps, table_info):
    """Show optimization results in new window"""
    opt_window = tk.Toplevel(self.root)
    opt_window.title(_("finance_reporting.windows.performance_optimization"))
    opt_window.geometry("600x500")

    main_frame = ttk.Frame(opt_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Performance Optimization Results", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Optimization steps
    steps_frame = ttk.LabelFrame(main_frame, text="Optimization Steps Completed", padding="10")
    steps_frame.pack(fill=tk.X, pady=(0, 10))

    for i, step in enumerate(steps, 1):
        ttk.Label(steps_frame, text=f"{i}. {step}").pack(anchor=tk.W)

    # Table information
    info_frame = ttk.LabelFrame(main_frame, text="Database Information", padding="10")
    info_frame.pack(fill=tk.X, pady=(0, 10))

    for info in table_info:
        ttk.Label(info_frame, text=info).pack(anchor=tk.W)

    ttk.Button(main_frame, text="Close", command=opt_window.destroy).pack(pady=10)

def run_data_quality_assessment(self):
    """Run data quality assessment with GUI display"""
    self.update_status("Running data quality assessment...")

    def assess_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            quality_checks = []

            # Check for missing data
            cursor.execute('SELECT COUNT(*) FROM students WHERE first_name IS NULL OR last_name IS NULL')
            missing_names = cursor.fetchone()[0]
            quality_checks.append(('Missing Student Names', missing_names, missing_names == 0))

            # Check for invalid amounts
            cursor.execute('SELECT COUNT(*) FROM student_fees WHERE amount <= 0')
            invalid_amounts = cursor.fetchone()[0]
            quality_checks.append(('Invalid Fee Amounts', invalid_amounts, invalid_amounts == 0))

            # Check for future payment dates
            cursor.execute('SELECT COUNT(*) FROM payments WHERE payment_date > date("now")')
            future_payments = cursor.fetchone()[0]
            quality_checks.append(('Future Payment Dates', future_payments, future_payments == 0))

            # Check for duplicate payments
            cursor.execute('''
            SELECT COUNT(*) FROM (
                SELECT student_id, amount, payment_date, COUNT(*)
                FROM payments
                GROUP BY student_id, amount, payment_date
                HAVING COUNT(*) > 1
            )
            ''')
            duplicate_payments = cursor.fetchone()[0]
            quality_checks.append(('Duplicate Payments', duplicate_payments, duplicate_payments == 0))

            conn.close()

            self.root.after(0, lambda: [
                self.log_activity("Data quality assessment completed"),
                self.update_status("Ready"),
                self.show_data_quality_results(quality_checks)
            ])

        except Exception as e:
            self.root.after(0, lambda: [
                self.log_activity(f"Data quality assessment error: {e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Data quality assessment failed: {e}")
            ])

    thread = threading.Thread(target=assess_in_background)
    thread.daemon = True
    thread.start()

def show_data_quality_results(self, quality_checks):
    """Show data quality assessment results in new window"""
    quality_window = tk.Toplevel(self.root)
    quality_window.title(_("finance_reporting.windows.data_quality"))
    quality_window.geometry("700x500")

    main_frame = ttk.Frame(quality_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Data Quality Assessment Results", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Results treeview
    results_tree = ttk.Treeview(main_frame, columns=('Status', 'Issues'), height=15)
    results_tree.heading('#0', text='Quality Check')
    results_tree.heading('Status', text='Status')
    results_tree.heading('Issues', text='Issues Found')
    results_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    total_issues = 0
    for check_name, issue_count, is_ok in quality_checks:
        status = "PASS" if is_ok else "FAIL"
        results_tree.insert('', 'end', text=check_name,
                          values=(status, issue_count))
        if not is_ok:
            total_issues += issue_count

    # Summary
    summary_frame = ttk.Frame(main_frame)
    summary_frame.pack(fill=tk.X, pady=(10, 0))

    if total_issues == 0:
        status_text = "EXCELLENT - No issues found"
        status_color = "green"
    elif total_issues < 10:
        status_text = f"GOOD - {total_issues} minor issues found"
        status_color = "orange"
    else:
        status_text = f"NEEDS ATTENTION - {total_issues} issues found"
        status_color = "red"

    status_label = ttk.Label(summary_frame, text=f"Overall Data Quality: {status_text}")
    status_label.pack()

    ttk.Button(main_frame, text="Close", command=quality_window.destroy).pack(pady=10)

def run_selected_analysis(self):
    """Run the selected analysis type"""
    analysis_type = self.analysis_type.get()
    self.results_text.delete(1.0, tk.END)
    self.results_text.insert(tk.END, f"Running {analysis_type} analysis...\n\n")

    def run_analysis():
        try:
            if analysis_type == "forecasting":
                generate_advanced_financial_forecasting()
                result = "Advanced financial forecasting completed.\n\n"
                result += "Forecast Summary:\n"
                result += "-" * 40 + "\n"
                # Get some data for the report
                cash_flow_forecaster = CashFlowForecaster()
                forecast = cash_flow_forecaster.generate_cash_flow_forecast(6)
                if forecast and forecast.get('forecast_data'):
                    result += f"Baseline Monthly Revenue: £{forecast.get('baseline_monthly', 0):,.2f}\n\n"
                    result += "6-Month Forecast:\n"
                    for item in forecast['forecast_data']:
                        result += f"  {item['month']}: £{item['forecast_amount']:,.2f}\n"

            elif analysis_type == "risk_analysis":
                payment_predictor = PaymentPredictionML()
                risk_students = payment_predictor.predict_payment_risk()
                result = f"Payment Risk Analysis Report\n"
                result += "=" * 40 + "\n\n"
                result += f"Total students analyzed: {len(risk_students)}\n"
                if risk_students:
                    high_risk = [s for s in risk_students if s['risk_level'] == 'High']
                    medium_risk = [s for s in risk_students if s['risk_level'] == 'Medium']
                    low_risk = [s for s in risk_students if s['risk_level'] == 'Low']
                    result += f"\nRisk Distribution:\n"
                    result += f"  High Risk: {len(high_risk)} students\n"
                    result += f"  Medium Risk: {len(medium_risk)} students\n"
                    result += f"  Low Risk: {len(low_risk)} students\n\n"
                    result += "High-Risk Students:\n"
                    result += "-" * 40 + "\n"
                    for student in high_risk[:10]:
                        result += f"  {student['student_name']}: {student['risk_score']:.1%} risk (£{student.get('total_fees', 0):,.2f} fees)\n"

            elif analysis_type == "cash_flow":
                cash_flow_forecaster = CashFlowForecaster()
                forecast = cash_flow_forecaster.generate_cash_flow_forecast(12)
                result = "Cash Flow Forecast Report\n"
                result += "=" * 40 + "\n\n"
                if forecast and forecast.get('forecast_data'):
                    result += f"Baseline Monthly Revenue: £{forecast.get('baseline_monthly', 0):,.2f}\n"
                    result += f"Trend: {forecast.get('trend', 0):.1%}\n\n"
                    result += "12-Month Forecast:\n"
                    result += "-" * 40 + "\n"
                    result += f"{'Month':<15} {'Forecast':<18} {'Cumulative':<18}\n"
                    result += "-" * 40 + "\n"
                    for item in forecast['forecast_data']:
                        result += f"{item['month']:<15} £{item['forecast_amount']:<17,.2f} £{item['cumulative']:<17,.2f}\n"
                else:
                    result += "Insufficient data for cash flow forecast."

            elif analysis_type == "scenario_planning":
                scenario_planning_tools()
                result = "Scenario Planning Analysis Report\n"
                result += "=" * 40 + "\n\n"
                result += "Scenario analysis completed.\n\n"
                result += "Scenarios Evaluated:\n"
                result += "  1. Best Case: +15% enrollment growth\n"
                result += "  2. Expected Case: +5% enrollment growth\n"
                result += "  3. Worst Case: -10% enrollment decline\n\n"
                result += "See generated charts for detailed projections."

            else:
                result = f"Analysis type '{analysis_type}' not implemented yet."

            # Show results in new window
            self.root.after(0, lambda r=result, at=analysis_type: [
                self.show_analysis_results_window(at, r),
                self.results_text.delete(1.0, tk.END),
                self.results_text.insert(tk.END, f"{at} analysis completed. Results shown in new window."),
                self.log_activity(f"{at} analysis completed")
            ])

        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda err=error_msg, at=analysis_type: [
                self.results_text.delete(1.0, tk.END),
                self.results_text.insert(tk.END, f"Error in {at} analysis: {err}"),
                self.log_activity(f"Error in {at} analysis: {err}")
            ])

    thread = threading.Thread(target=run_analysis)
    thread.daemon = True
    thread.start()


def show_analysis_results_window(self, analysis_type, results):
    """Show analysis results in a new window with save and email options"""
    results_window = tk.Toplevel(self.root)
    title_map = {
        'forecasting': 'Financial Forecasting',
        'risk_analysis': 'Payment Risk Analysis',
        'cash_flow': 'Cash Flow Forecast',
        'scenario_planning': 'Scenario Planning'
    }
    window_title = title_map.get(analysis_type, analysis_type.replace('_', ' ').title())
    results_window.title(f"{window_title} Results")
    results_window.geometry("1200x800")

    main_frame = ttk.Frame(results_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text=f"{window_title} Results",
             style='Title.TLabel').pack(pady=(0, 20))

    # Results text area
    results_text = ScrolledText(main_frame, height=25, wrap=tk.WORD)
    results_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Insert results
    results_text.insert(tk.END, f"{window_title} Report\n")
    results_text.insert(tk.END, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    results_text.insert(tk.END, "=" * 80 + "\n\n")
    results_text.insert(tk.END, results)
    results_text.configure(state='disabled')

    def save_as_txt():
        """Save results as text file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{analysis_type}_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if filename:
            try:
                results_text.configure(state='normal')
                content = results_text.get("1.0", tk.END)
                results_text.configure(state='disabled')

                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report:\n{e}")

    def send_to_admin():
        """Send results to admin via email"""
        results_text.configure(state='normal')
        content = results_text.get("1.0", tk.END)
        results_text.configure(state='disabled')
        send_report_to_admin(window_title, content, results_window)

    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(button_frame, text="Save as TXT", command=save_as_txt).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Send to Admin", command=send_to_admin).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close", command=results_window.destroy).pack(side=tk.RIGHT, padx=5)

def run_yoy_analysis(self):
    """Run year-over-year analysis"""
    self.update_status("Running year-over-year analysis...")

    def yoy_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Get payment data by year
            cursor.execute('''
            SELECT
                strftime('%Y', payment_date) as year,
                COUNT(*) as payment_count,
                SUM(amount) as total_amount,
                AVG(amount) as avg_amount
            FROM payments
            GROUP BY year
            ORDER BY year DESC
            ''')

            yoy_data = cursor.fetchall()

            if yoy_data:
                self.root.after(0, lambda: [
                    self.show_yoy_results(yoy_data),
                    self.update_status("Ready")
                ])
            else:
                self.root.after(0, lambda: [
                    messagebox.showinfo("YoY Analysis", "Insufficient data for year-over-year analysis"),
                    self.update_status("Ready")
                ])

            conn.close()

        except Exception as e:
            self.root.after(0, lambda: [
                messagebox.showerror("Error", f"Year-over-year analysis failed: {e}"),
                self.update_status("Error")
            ])

    thread = threading.Thread(target=yoy_in_background)
    thread.daemon = True
    thread.start()

def show_yoy_results(self, yoy_data):
    """Show year-over-year analysis results"""
    yoy_window = tk.Toplevel(self.root)
    yoy_window.title(_("finance_reporting.windows.yoy_analysis"))
    yoy_window.geometry("1200x800")

    main_frame = ttk.Frame(yoy_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Year-over-Year Financial Analysis",
             style='Title.TLabel').pack(pady=(0, 20))

    results_text = ScrolledText(main_frame, height=20, wrap=tk.WORD)
    results_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    results_text.insert(tk.END, "Year-over-Year Payment Analysis\n")
    results_text.insert(tk.END, "=" * 80 + "\n\n")
    results_text.insert(tk.END, f"{'Year':<10} {'Payments':<15} {'Total Amount':<20} {'Avg Payment':<20} {'YoY Change':<15}\n")
    results_text.insert(tk.END, "-" * 80 + "\n")

    prev_total = None
    for year, count, total, avg in yoy_data:
        yoy_change = ""
        if prev_total:
            change_pct = ((total - prev_total) / prev_total) * 100
            yoy_change = f"{change_pct:+.1f}%"

        results_text.insert(tk.END, f"{year:<10} {count:<15,} £{total:<19,.2f} £{avg:<19,.2f} {yoy_change:<15}\n")
        prev_total = total

    results_text.configure(state='disabled')

    def save_as_txt():
        """Save year-over-year analysis results as text file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"yoy_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if filename:
            try:
                # Re-enable text widget temporarily to get content
                results_text.configure(state='normal')
                content = results_text.get("1.0", tk.END)
                results_text.configure(state='disabled')

                with open(filename, 'w') as f:
                    f.write(f"Year-over-Year Financial Analysis Report\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report:\n{e}")

    def send_to_admin():
        """Send results to admin via email"""
        results_text.configure(state='normal')
        content = results_text.get("1.0", tk.END)
        results_text.configure(state='disabled')
        send_report_to_admin("Year-over-Year Financial Analysis", content, yoy_window)

    # Button frame for multiple buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)

    ttk.Button(button_frame, text="Save as TXT", command=save_as_txt).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Send to Admin", command=send_to_admin).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close", command=yoy_window.destroy).pack(side=tk.LEFT, padx=5)

def run_department_comparison(self):
    """Run department comparison analysis"""
    self.update_status("Running department comparison analysis...")

    def dept_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Get department data (using course as proxy for department)
            cursor.execute('''
            SELECT
                s.course,
                COUNT(DISTINCT sf.student_id) as student_count,
                SUM(sf.amount) as total_fees,
                SUM(CASE WHEN sf.status = 'paid' OR sf.status = 'completed' THEN sf.amount ELSE 0 END) as collected,
                AVG(sf.amount) as avg_fee
            FROM student_fees sf
            JOIN students s ON sf.student_id = s.student_id
            WHERE s.course IS NOT NULL
            GROUP BY s.course
            ORDER BY total_fees DESC
            ''')

            dept_data = cursor.fetchall()

            if dept_data:
                self.root.after(0, lambda: [
                    self.show_department_results(dept_data),
                    self.update_status("Ready")
                ])
            else:
                self.root.after(0, lambda: [
                    messagebox.showinfo("Department Analysis", "No department data available"),
                    self.update_status("Ready")
                ])

            conn.close()

        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: [
                messagebox.showerror("Error", f"Department comparison failed: {msg}"),
                self.update_status("Error")
            ])

    thread = threading.Thread(target=dept_in_background)
    thread.daemon = True
    thread.start()

def show_department_results(self, dept_data):
    """Show department comparison results"""
    dept_window = tk.Toplevel(self.root)
    dept_window.title(_("finance_reporting.windows.department_comparison"))
    dept_window.geometry("1200x800")

    main_frame = ttk.Frame(dept_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Department Financial Comparison",
             style='Title.TLabel').pack(pady=(0, 20))

    results_text = ScrolledText(main_frame, height=20, wrap=tk.WORD)
    results_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    results_text.insert(tk.END, "Department-wise Financial Performance\n")
    results_text.insert(tk.END, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    results_text.insert(tk.END, "=" * 100 + "\n\n")
    results_text.insert(tk.END, f"{'Department':<25} {'Students':<12} {'Total Fees':<18} {'Collected':<18} {'Rate':<12} {'Avg Fee':<15}\n")
    results_text.insert(tk.END, "-" * 100 + "\n")

    for dept, students, total, collected, avg_fee in dept_data:
        rate = (collected / total * 100) if total > 0 else 0
        results_text.insert(tk.END, f"{dept:<25} {students:<12,} £{total:<17,.2f} £{collected:<17,.2f} {rate:<11.1f}% £{avg_fee:<14,.2f}\n")

    results_text.configure(state='disabled')

    def save_as_txt():
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"department_comparison_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if filename:
            try:
                results_text.configure(state='normal')
                content = results_text.get("1.0", tk.END)
                results_text.configure(state='disabled')
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report:\n{e}")

    def send_to_admin():
        results_text.configure(state='normal')
        content = results_text.get("1.0", tk.END)
        results_text.configure(state='disabled')
        send_report_to_admin("Department Financial Comparison", content, dept_window)

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Save as TXT", command=save_as_txt).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Send to Admin", command=send_to_admin).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close", command=dept_window.destroy).pack(side=tk.LEFT, padx=5)

def run_benchmarking_analysis(self):
    """Run peer benchmarking analysis"""
    self.update_status("Running peer benchmarking analysis...")

    def benchmark_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Calculate our metrics
            cursor.execute('''
            SELECT
                SUM(sf.amount) as total_revenue,
                SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as collected,
                COUNT(DISTINCT sf.student_id) as students,
                AVG(sf.amount) as avg_fee
            FROM student_fees sf
            ''')

            our_data = cursor.fetchone()
            conn.close()

            if our_data and our_data[0]:
                collection_rate = (our_data[1] / our_data[0] * 100) if our_data[0] > 0 else 0

                # Simulated benchmark data (in real implementation, this would come from external sources)
                benchmark_data = {
                    'our_collection_rate': collection_rate,
                    'avg_collection_rate': 87.5,
                    'top_quartile': 92.0,
                    'our_revenue_per_student': our_data[0] / our_data[2] if our_data[2] > 0 else 0,
                    'avg_revenue_per_student': 15000,
                    'our_avg_fee': our_data[3],
                    'avg_fee': 1850
                }

                self.root.after(0, lambda: [
                    self.show_benchmarking_results(benchmark_data),
                    self.update_status("Ready")
                ])
            else:
                self.root.after(0, lambda: [
                    messagebox.showinfo("Benchmarking", "Insufficient data for benchmarking"),
                    self.update_status("Ready")
                ])

        except Exception as e:
            self.root.after(0, lambda: [
                messagebox.showerror("Error", f"Benchmarking analysis failed: {e}"),
                self.update_status("Error")
            ])

    thread = threading.Thread(target=benchmark_in_background)
    thread.daemon = True
    thread.start()

def show_benchmarking_results(self, data):
    """Show peer benchmarking results"""
    bench_window = tk.Toplevel(self.root)
    bench_window.title(_("finance_reporting.windows.peer_benchmarking"))
    bench_window.geometry("800x600")

    main_frame = ttk.Frame(bench_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Peer Benchmarking Analysis",
             style='Title.TLabel').pack(pady=(0, 20))

    results_text = ScrolledText(main_frame, height=20, wrap=tk.WORD)
    results_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    results_text.insert(tk.END, "Peer Institution Benchmarking\n")
    results_text.insert(tk.END, "=" * 70 + "\n\n")

    results_text.insert(tk.END, "COLLECTION RATE COMPARISON:\n")
    results_text.insert(tk.END, f"  Our Collection Rate:        {data['our_collection_rate']:.1f}%\n")
    results_text.insert(tk.END, f"  Sector Average:              {data['avg_collection_rate']:.1f}%\n")
    results_text.insert(tk.END, f"  Top Quartile:                {data['top_quartile']:.1f}%\n")
    results_text.insert(tk.END, f"  Performance Gap:             {data['our_collection_rate'] - data['avg_collection_rate']:+.1f}%\n\n")

    results_text.insert(tk.END, "REVENUE PER STUDENT:\n")
    results_text.insert(tk.END, f"  Our Revenue/Student:         £{data['our_revenue_per_student']:,.2f}\n")
    results_text.insert(tk.END, f"  Sector Average:              £{data['avg_revenue_per_student']:,.2f}\n")
    results_text.insert(tk.END, f"  Variance:                    {((data['our_revenue_per_student'] / data['avg_revenue_per_student'] - 1) * 100):+.1f}%\n\n")

    results_text.insert(tk.END, "AVERAGE FEE COMPARISON:\n")
    results_text.insert(tk.END, f"  Our Average Fee:             £{data['our_avg_fee']:,.2f}\n")
    results_text.insert(tk.END, f"  Sector Average:              £{data['avg_fee']:,.2f}\n\n")

    results_text.insert(tk.END, "KEY INSIGHTS:\n")
    if data['our_collection_rate'] > data['avg_collection_rate']:
        results_text.insert(tk.END, "• Collection rate ABOVE sector average - maintain best practices\n")
    else:
        results_text.insert(tk.END, "• Collection rate BELOW sector average - focus on improvement strategies\n")

    if data['our_revenue_per_student'] > data['avg_revenue_per_student']:
        results_text.insert(tk.END, "• Revenue per student ABOVE average - strong financial position\n")
    else:
        results_text.insert(tk.END, "• Revenue per student BELOW average - explore revenue optimization\n")

    results_text.configure(state='disabled')

    def save_as_txt():
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"benchmarking_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if filename:
            try:
                results_text.configure(state='normal')
                content = results_text.get("1.0", tk.END)
                results_text.configure(state='disabled')
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report:\n{e}")

    def send_to_admin():
        results_text.configure(state='normal')
        content = results_text.get("1.0", tk.END)
        results_text.configure(state='disabled')
        send_report_to_admin("Peer Benchmarking Analysis", content, bench_window)

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Save as TXT", command=save_as_txt).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Send to Admin", command=send_to_admin).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close", command=bench_window.destroy).pack(side=tk.LEFT, padx=5)

def run_payment_frequency_analysis(self):
    """Analyze payment frequency patterns"""
    self.update_status("Analyzing payment frequency patterns...")

    def frequency_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Payment frequency analysis
            cursor.execute('''
            SELECT 
                strftime('%w', payment_date) as day_of_week,
                strftime('%H', payment_date) as hour_of_day,
                COUNT(*) as payment_count,
                SUM(amount) as total_amount
            FROM payments
            WHERE payment_date >= date('now', '-90 days')
            GROUP BY day_of_week, hour_of_day
            ORDER BY payment_count DESC
            ''')

            frequency_data = cursor.fetchall()
            conn.close()

            self.root.after(0, lambda: [
                self.log_activity("Payment frequency analysis completed"),
                self.update_status("Ready"),
                self.show_frequency_analysis_results(frequency_data)
            ])

        except Exception as e:
            self.root.after(0, lambda: [
                self.log_activity(f"Payment frequency analysis error: {e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Payment frequency analysis failed: {e}")
            ])

    thread = threading.Thread(target=frequency_in_background)
    thread.daemon = True
    thread.start()

def show_frequency_analysis_results(self, frequency_data):
    """Show payment frequency analysis results"""
    freq_window = tk.Toplevel(self.root)
    freq_window.title(_("finance_reporting.windows.payment_frequency"))
    freq_window.geometry("800x600")

    main_frame = ttk.Frame(freq_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Payment Frequency Analysis", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Results table
    results_tree = ttk.Treeview(main_frame, columns=('Hour', 'Count', 'Amount'), height=20)
    results_tree.heading('#0', text='Day of Week')
    results_tree.heading('Hour', text='Hour')
    results_tree.heading('Count', text='Payment Count')
    results_tree.heading('Amount', text='Total Amount')
    results_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

    for day_num, hour, count, amount in frequency_data[:20]:  # Show top 20
        day_name = day_names[int(day_num)]
        hour_formatted = f"{int(hour):02d}:00"
        results_tree.insert('', 'end', text=day_name,
                          values=(hour_formatted, count, f"£{amount:,.2f}"))

    ttk.Button(main_frame, text="Close", command=freq_window.destroy).pack(pady=5)

def run_fee_structure_analysis(self):
    """Analyze fee structure effectiveness"""
    self.update_status("Analyzing fee structure...")

    def fee_analysis_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Fee structure analysis
            cursor.execute('''
            SELECT 
                ft.fee_name,
                ft.amount as standard_amount,
                COUNT(DISTINCT sf.student_id) as students_assigned,
                COUNT(DISTINCT CASE WHEN sf.status = 'paid' THEN sf.student_id END) as students_paid,
                AVG(sf.amount) as avg_actual_amount,
                SUM(sf.amount) as total_expected,
                SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected
            FROM fee_types ft
            LEFT JOIN student_fees sf ON ft.fee_type_id = sf.fee_type_id
            GROUP BY ft.fee_type_id, ft.fee_name, ft.amount
            ORDER BY total_expected DESC
            ''')

            fee_data = cursor.fetchall()
            conn.close()

            self.root.after(0, lambda: [
                self.log_activity("Fee structure analysis completed"),
                self.update_status("Ready"),
                self.show_fee_structure_results(fee_data)
            ])

        except Exception as e:
            self.root.after(0, lambda: [
                self.log_activity(f"Fee structure analysis error: {e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Fee structure analysis failed: {e}")
            ])

    thread = threading.Thread(target=fee_analysis_in_background)
    thread.daemon = True
    thread.start()

def show_fee_structure_results(self, fee_data):
    """Show fee structure analysis results"""
    fee_window = tk.Toplevel(self.root)
    fee_window.title(_("finance_reporting.windows.fee_structure"))
    fee_window.geometry("1000x600")

    main_frame = ttk.Frame(fee_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Fee Structure Analysis", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Results table
    results_tree = ttk.Treeview(main_frame, columns=('Standard', 'Students', 'Paid', 'Collection Rate', 'Total Expected', 'Total Collected'), height=15)
    results_tree.heading('#0', text='Fee Type')
    results_tree.heading('Standard', text='Standard Amount')
    results_tree.heading('Students', text='Students Assigned')
    results_tree.heading('Paid', text='Students Paid')
    results_tree.heading('Collection Rate', text='Collection Rate')
    results_tree.heading('Total Expected', text='Total Expected')
    results_tree.heading('Total Collected', text='Total Collected')
    results_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    for fee_name, standard_amount, students_assigned, students_paid, avg_actual, total_expected, total_collected in fee_data:
        collection_rate = (students_paid / students_assigned * 100) if students_assigned > 0 else 0
        results_tree.insert('', 'end', text=fee_name,
                          values=(f"£{standard_amount:,.2f}",
                                students_assigned,
                                students_paid,
                                f"{collection_rate:.1f}%",
                                f"£{total_expected:,.2f}",
                                f"£{total_collected:,.2f}"))

    ttk.Button(main_frame, text="Close", command=fee_window.destroy).pack(pady=5)

def run_student_retention_analysis(self):
    """Analyze student retention vs financial performance"""
    self.update_status("Analyzing student retention patterns...")

    def retention_in_background():
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Student retention analysis
            cursor.execute('''
            SELECT 
                s.status,
                COUNT(*) as student_count,
                AVG(CASE WHEN sf.amount > 0 THEN 
                    (sf.paid_amount * 100.0 / sf.amount) ELSE 0 END) as avg_collection_rate,
                AVG(sf.amount) as avg_fees,
                SUM(sf.amount) as total_fees
            FROM students s
            LEFT JOIN (
                SELECT student_id, 
                       SUM(amount) as amount,
                       SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as paid_amount
                FROM student_fees 
                GROUP BY student_id
            ) sf ON s.student_id = sf.student_id
            GROUP BY s.status
            ORDER BY student_count DESC
            ''')

            retention_data = cursor.fetchall()
            conn.close()

            self.root.after(0, lambda: [
                self.log_activity("Student retention analysis completed"),
                self.update_status("Ready"),
                self.show_retention_analysis_results(retention_data)
            ])

        except Exception as e:
            self.root.after(0, lambda: [
                self.log_activity(f"Student retention analysis error: {e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Student retention analysis failed: {e}")
            ])

    thread = threading.Thread(target=retention_in_background)
    thread.daemon = True
    thread.start()

def show_retention_analysis_results(self, retention_data):
    """Show student retention analysis results"""
    retention_window = tk.Toplevel(self.root)
    retention_window.title(_("finance_reporting.windows.retention_analysis"))
    retention_window.geometry("800x500")

    main_frame = ttk.Frame(retention_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Student Retention Analysis", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Results table
    results_tree = ttk.Treeview(main_frame, columns=('Count', 'Collection Rate', 'Avg Fees', 'Total Fees'), height=10)
    results_tree.heading('#0', text='Student Status')
    results_tree.heading('Count', text='Student Count')
    results_tree.heading('Collection Rate', text='Avg Collection Rate')
    results_tree.heading('Avg Fees', text='Average Fees')
    results_tree.heading('Total Fees', text='Total Fees')
    results_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    for status, count, collection_rate, avg_fees, total_fees in retention_data:
        results_tree.insert('', 'end', text=status or 'Unknown',
                          values=(count,
                                f"{collection_rate:.1f}%",
                                f"£{avg_fees:,.2f}",
                                f"£{total_fees:,.2f}"))

    # Analysis summary
    summary_frame = ttk.LabelFrame(main_frame, text="Retention Insights", padding="10")
    summary_frame.pack(fill=tk.X, pady=(10, 0))

    summary_text = ScrolledText(summary_frame, height=8, wrap=tk.WORD)
    summary_text.pack(fill=tk.BOTH, expand=True)

    summary_content = """Student Retention Financial Analysis Summary:

    KEY FINDINGS:
    • Active students typically have the highest collection rates
    • Graduated students show strong final payment completion
    • Dropped students often have outstanding balances
    • Transfer students may have partial payment patterns

    RETENTION STRATEGIES:
    • Early intervention for payment difficulties
    • Flexible payment plans to prevent dropouts
    • Financial counseling services
    • Emergency hardship funds

    COLLECTION OPTIMIZATION:
    • Focus collection efforts by student status
    • Implement retention-based payment strategies
    • Provide financial literacy education
    • Create alumni payment programs for graduates

    RISK MITIGATION:
    • Monitor payment patterns as early retention indicator
    • Implement graduated response for payment delays
    • Provide proactive financial support services
    • Track correlation between financial stress and dropout risk
    """

    summary_text.insert(1.0, summary_content)
    summary_text.configure(state='disabled')

    ttk.Button(main_frame, text="Close", command=retention_window.destroy).pack(pady=5)

# Method registration is handled by main.py
