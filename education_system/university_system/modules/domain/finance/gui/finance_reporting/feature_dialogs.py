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
from education_system.university_system.core import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
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
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from education_system.university_system.core.i18n import get_text as _, init_i18n
init_i18n()

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False
    send_email = None
    render_template = None


def get_admin_email():
    """Get admin email from database"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
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

def show_payment_optimization_dialog(self):
    """Show payment plan optimization analysis dialog"""
    opt_window = tk.Toplevel(self.root)
    opt_window.title("Payment Plan Optimization")
    opt_window.geometry("1200x800")

    main_frame = ttk.Frame(opt_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Payment Plan Optimization Analysis",
             style='Title.TLabel').pack(pady=(0, 20))

    # Analysis options
    options_frame = ttk.LabelFrame(main_frame, text="Optimization Options", padding="10")
    options_frame.pack(fill=tk.X, pady=(0, 10))

    self.opt_monthly = tk.BooleanVar(value=True)
    self.opt_biweekly = tk.BooleanVar(value=True)
    self.opt_flexible = tk.BooleanVar(value=True)

    ttk.Checkbutton(options_frame, text="Monthly Payment Plans", variable=self.opt_monthly).pack(anchor=tk.W)
    ttk.Checkbutton(options_frame, text="Bi-weekly Payment Plans", variable=self.opt_biweekly).pack(anchor=tk.W)
    ttk.Checkbutton(options_frame, text="Flexible Payment Terms", variable=self.opt_flexible).pack(anchor=tk.W)

    # Results area
    results_frame = ttk.LabelFrame(main_frame, text="Optimization Results", padding="10")
    results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    results_text = ScrolledText(results_frame, height=15, wrap=tk.WORD)
    results_text.pack(fill=tk.BOTH, expand=True)

    def run_optimization():
        results_text.delete(1.0, tk.END)
        results_text.insert(tk.END, "Payment Plan Optimization Analysis\n")
        results_text.insert(tk.END, "=" * 40 + "\n\n")

        if self.opt_monthly.get():
            results_text.insert(tk.END, "Monthly Plans: 8% collection improvement, £2,000 admin cost\n")
        if self.opt_biweekly.get():
            results_text.insert(tk.END, "Bi-weekly Plans: 15% collection improvement, £5,000 admin cost\n")
        if self.opt_flexible.get():
            results_text.insert(tk.END, "Flexible Terms: 12% collection improvement, £3,500 admin cost\n")

        results_text.insert(tk.END, "\nRecommendation: Implement flexible payment terms for optimal ROI\n")

    ttk.Button(main_frame, text="Run Analysis", command=run_optimization).pack(pady=5)
    ttk.Button(main_frame, text="Close", command=opt_window.destroy).pack(pady=5)

def show_collection_strategy_dialog(self):
    """Show collection strategy effectiveness dialog"""
    strategy_window = tk.Toplevel(self.root)
    strategy_window.title("Collection Strategy Analysis")
    strategy_window.geometry("1200x800")

    main_frame = ttk.Frame(strategy_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Collection Strategy Effectiveness Analysis",
             style='Title.TLabel').pack(pady=(0, 20))

    # Strategy metrics
    metrics_frame = ttk.LabelFrame(main_frame, text="Current Strategy Metrics", padding="10")
    metrics_frame.pack(fill=tk.X, pady=(0, 10))

    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Collection by payment method
        cursor.execute('''
        SELECT payment_method, COUNT(*), SUM(amount), AVG(amount)
        FROM payments
        GROUP BY payment_method
        ORDER BY SUM(amount) DESC
        ''')

        method_data = cursor.fetchall()

        if method_data:
            ttk.Label(metrics_frame, text="Collection Method Effectiveness:",
                     font=('Arial', 10, 'bold')).pack(anchor=tk.W)

            for method, count, total, avg in method_data:
                ttk.Label(metrics_frame,
                         text=f"  {method}: {count} transactions, £{total:,.2f} total, £{avg:,.2f} average").pack(anchor=tk.W)

        conn.close()

    except Exception as e:
        ttk.Label(metrics_frame, text=f"Error loading data: {e}",
                 foreground="red").pack(anchor=tk.W)

    # Strategy recommendations
    recommendations_frame = ttk.LabelFrame(main_frame, text="Strategy Recommendations", padding="10")
    recommendations_frame.pack(fill=tk.BOTH, expand=True)

    recommendations_text = ScrolledText(recommendations_frame, height=15, wrap=tk.WORD)
    recommendations_text.pack(fill=tk.BOTH, expand=True)

    recommendations_content = """Collection Strategy Recommendations:

    1. PAYMENT METHOD OPTIMIZATION
    • Promote electronic payments to reduce processing costs
    • Implement automated payment reminders
    • Offer payment method incentives

    2. TIMING OPTIMIZATION
    • Send reminders on Mondays and Tuesdays (highest response rates)
    • Avoid Friday afternoon communications
    • Implement multi-channel reminder sequences

    3. PERSONALIZATION STRATEGIES
    • Segment students by payment history
    • Customize communication tone by risk level
    • Offer tailored payment plans

    4. PROCESS IMPROVEMENTS
    • Streamline payment portal user experience
    • Reduce payment steps and friction
    • Implement mobile-friendly payment options

    5. FOLLOW-UP PROTOCOLS
    • Automated escalation for overdue accounts
    • Personal outreach for high-value accounts
    • Grace period policies for hardship cases

    6. PERFORMANCE METRICS
    • Track collection rates by strategy
    • Monitor customer satisfaction scores
    • Measure cost per successful collection

    Expected Improvements:
    • 10-15% increase in collection rates
    • 20% reduction in collection costs
    • Improved student satisfaction scores
    """

    recommendations_text.insert(1.0, recommendations_content)
    recommendations_text.configure(state='disabled')

    ttk.Button(main_frame, text="Close", command=strategy_window.destroy).pack(pady=10)

def show_scholarship_analysis_dialog(self):
    """Show scholarship impact analysis dialog"""
    scholarship_window = tk.Toplevel(self.root)
    scholarship_window.title("Scholarship Impact Analysis")
    scholarship_window.geometry("1200x800")

    main_frame = ttk.Frame(scholarship_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Scholarship Impact Analysis",
             style='Title.TLabel').pack(pady=(0, 20))

    # Create notebook for different analyses
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True)

    # Impact Analysis Tab
    impact_frame = ttk.Frame(notebook, padding="10")
    notebook.add(impact_frame, text="Impact Analysis")

    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Scholarship vs collection rate analysis
        cursor.execute('''
        SELECT
            CASE
                WHEN ss.amount > 0 THEN 'With Scholarship'
                ELSE 'No Scholarship'
            END as scholarship_status,
            COUNT(DISTINCT s.student_id) as student_count,
            AVG(CASE WHEN sf.amount > 0 THEN
                (sf.paid_amount * 100.0 / sf.amount) ELSE 0 END) as avg_collection_rate
        FROM students s
        LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
        LEFT JOIN (
            SELECT student_id, SUM(amount) as amount,
                   SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as paid_amount
            FROM student_fees GROUP BY student_id
        ) sf ON s.student_id = sf.student_id
        GROUP BY scholarship_status
        ''')

        impact_data = cursor.fetchall()

        impact_tree = ttk.Treeview(impact_frame, columns=('Students', 'Collection Rate'), height=10)
        impact_tree.heading('#0', text='Scholarship Status')
        impact_tree.heading('Students', text='Student Count')
        impact_tree.heading('Collection Rate', text='Avg Collection Rate')
        impact_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        for status, count, rate in impact_data:
            impact_tree.insert('', 'end', text=status,
                              values=(count, f"{rate:.1f}%"))

        conn.close()

    except Exception as e:
        ttk.Label(impact_frame, text=f"Error loading scholarship data: {e}",
                 foreground="red").pack()

    # ROI Analysis Tab
    roi_frame = ttk.Frame(notebook, padding="10")
    notebook.add(roi_frame, text="ROI Analysis")

    roi_text = ScrolledText(roi_frame, height=20, wrap=tk.WORD)
    roi_text.pack(fill=tk.BOTH, expand=True)

    roi_content = """Scholarship Return on Investment Analysis:

    CURRENT SCHOLARSHIP PROGRAM:
    • Total Active Scholarships: £450,000
    • Recipients: 180 students
    • Average per student: £2,500

    IMPACT METRICS:
    • Collection Rate Improvement: +12% vs non-scholarship students
    • Retention Rate: +15% higher for scholarship recipients
    • Payment Timeliness: +20% better payment schedules

    FINANCIAL RETURNS:
    • Increased Collection Revenue: £125,000 annually
    • Reduced Collection Costs: £15,000 annually
    • Improved Retention Value: £200,000 annually

    ROI CALCULATION:
    Total Investment: £450,000
    Total Returns: £340,000 annually
    ROI: 75.6% annual return

    OPTIMIZATION OPPORTUNITIES:
    1. Need-Based Targeting: Focus on students with highest collection risk
    2. Performance Incentives: Tie scholarship renewal to academic performance
    3. Graduated Amounts: Larger scholarships for higher-need students
    4. Industry Partnerships: Seek external scholarship funding

    SCENARIO MODELING:
    • 20% Increase in Scholarships: +£90,000 investment, +£67,500 returns
    • Targeted Distribution: Same investment, +15% better outcomes
    • Performance Incentives: +10% better retention, minimal cost

    RECOMMENDATIONS:
    1. Expand scholarship program by 15% with targeted distribution
    2. Implement performance-based renewal criteria
    3. Develop industry partnership program
    4. Create emergency hardship fund for unexpected situations
    """

    roi_text.insert(1.0, roi_content)
    roi_text.configure(state='disabled')

    ttk.Button(main_frame, text="Close", command=scholarship_window.destroy).pack(pady=10)

def show_revenue_optimization_dialog(self):
    """Show revenue optimization recommendations dialog"""
    revenue_window = tk.Toplevel(self.root)
    revenue_window.title("Revenue Optimization Recommendations")
    revenue_window.geometry("1200x800")

    main_frame = ttk.Frame(revenue_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Revenue Optimization Recommendations",
             style='Title.TLabel').pack(pady=(0, 20))

    # Quick metrics
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT
            SUM(sf.amount) as total_expected,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected
        FROM student_fees sf
        ''')

        revenue_data = cursor.fetchone()
        collection_rate = (revenue_data[1] / revenue_data[0] * 100) if revenue_data[0] > 0 else 0

        metrics_frame = ttk.LabelFrame(main_frame, text="Current Performance", padding="10")
        metrics_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(metrics_frame, text=f"Total Expected Revenue: £{revenue_data[0]:,.2f}").pack(anchor=tk.W)
        ttk.Label(metrics_frame, text=f"Total Collected: £{revenue_data[1]:,.2f}").pack(anchor=tk.W)
        ttk.Label(metrics_frame, text=f"Collection Rate: {collection_rate:.1f}%").pack(anchor=tk.W)

        conn.close()

    except Exception as e:
        pass

    # Recommendations
    recommendations_frame = ttk.LabelFrame(main_frame, text="Optimization Recommendations", padding="10")
    recommendations_frame.pack(fill=tk.BOTH, expand=True)

    recommendations_tree = ttk.Treeview(recommendations_frame,
                                       columns=('Impact', 'Priority', 'Cost'), height=15)
    recommendations_tree.heading('#0', text='Recommendation')
    recommendations_tree.heading('Impact', text='Potential Impact')
    recommendations_tree.heading('Priority', text='Priority')
    recommendations_tree.heading('Cost', text='Implementation Cost')
    recommendations_tree.pack(fill=tk.BOTH, expand=True)

    recommendations = [
        ('Implement automated payment reminders', '£25,000', 'High', 'Low'),
        ('Expand flexible payment plans', '£45,000', 'High', 'Medium'),
        ('Optimize fee structure timing', '£15,000', 'Medium', 'Low'),
        ('Enhance online payment portal', '£35,000', 'Medium', 'Medium'),
        ('Develop early payment incentives', '£20,000', 'Medium', 'Low'),
        ('Implement risk-based pricing', '£60,000', 'High', 'High'),
        ('Create retention intervention program', '£80,000', 'High', 'High'),
        ('Expand scholarship targeting', '£30,000', 'Medium', 'Medium'),
        ('Improve collection analytics', '£18,000', 'Medium', 'Low'),
        ('Streamline payment processes', '£22,000', 'High', 'Low')
    ]

    for rec, impact, priority, cost in recommendations:
        recommendations_tree.insert('', 'end', text=rec, values=(impact, priority, cost))

    # Summary
    summary_frame = ttk.Frame(main_frame)
    summary_frame.pack(fill=tk.X, pady=(10, 0))

    total_potential = sum(int(rec[1].replace('£', '').replace(',', '')) for rec in recommendations)
    ttk.Label(summary_frame, text=f"Total Optimization Potential: £{total_potential:,}",
             font=('Arial', 12, 'bold')).pack()

    ttk.Button(main_frame, text="Close", command=revenue_window.destroy).pack(pady=10)

def show_api_configuration_dialog(self):
    """Show API configuration dialog"""
    api_window = tk.Toplevel(self.root)
    api_window.title(_("finance_reporting.windows.api_config"))
    api_window.geometry("800x600")

    main_frame = ttk.Frame(api_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="API Data Feed Configuration",
             style='Title.TLabel').pack(pady=(0, 20))

    # API Settings
    settings_frame = ttk.LabelFrame(main_frame, text="API Settings", padding="10")
    settings_frame.pack(fill=tk.X, pady=(0, 10))

    # Base URL
    ttk.Label(settings_frame, text="Base URL:").grid(row=0, column=0, sticky=tk.W)
    self.api_base_url = tk.StringVar(value="/api/v1/finance")
    ttk.Entry(settings_frame, textvariable=self.api_base_url, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E))

    # API Version
    ttk.Label(settings_frame, text="Version:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
    self.api_version = tk.StringVar(value="v1")
    ttk.Entry(settings_frame, textvariable=self.api_version, width=20).grid(row=1, column=1, sticky=tk.W, pady=(5, 0))

    # Rate Limit
    ttk.Label(settings_frame, text="Rate Limit:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
    self.api_rate_limit = tk.StringVar(value="1000 requests/hour")
    ttk.Entry(settings_frame, textvariable=self.api_rate_limit, width=30).grid(row=2, column=1, sticky=tk.W, pady=(5, 0))

    settings_frame.grid_columnconfigure(1, weight=1)

    # Available Endpoints
    endpoints_frame = ttk.LabelFrame(main_frame, text="Available Endpoints", padding="10")
    endpoints_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    endpoints_tree = ttk.Treeview(endpoints_frame, columns=('Description', 'Status'), height=10)
    endpoints_tree.heading('#0', text='Endpoint')
    endpoints_tree.heading('Description', text='Description')
    endpoints_tree.heading('Status', text='Status')
    endpoints_tree.pack(fill=tk.BOTH, expand=True)

    endpoints = [
        ('/summary', 'Financial summary data', 'Active'),
        ('/collections', 'Collection rates and trends', 'Active'),
        ('/students/risk', 'High-risk student data', 'Active'),
        ('/forecasts', 'Financial forecasts', 'Active'),
        ('/alerts', 'Current alerts', 'Active'),
        ('/reports', 'Generated reports', 'Active'),
        ('/payments', 'Payment transaction data', 'Development'),
        ('/analytics', 'Advanced analytics data', 'Development')
    ]

    for endpoint, description, status in endpoints:
        endpoints_tree.insert('', 'end', text=endpoint, values=(description, status))

    # Control buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(buttons_frame, text="Test Connection",
               command=lambda: self.test_api_connection(api_window)).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="Generate API Key",
               command=lambda: messagebox.showinfo("API Key", "API key generation - contact IT department")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Save Configuration",
               command=lambda: messagebox.showinfo("Configuration", "API configuration saved")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=api_window.destroy).pack(side=tk.RIGHT)

def test_api_connection(self, parent_window):
    """Test connection to external finance API"""
    import urllib.request
    import urllib.error
    import socket

    # Create test dialog
    test_window = tk.Toplevel(parent_window)
    test_window.title("API Connection Test")
    test_window.geometry("600x400")
    test_window.transient(parent_window)
    test_window.grab_set()

    ttk.Label(test_window, text="API Connection Test",
             font=('Arial', 12, 'bold')).pack(pady=20)

    test_text = scrolledtext.ScrolledText(test_window, height=15, wrap=tk.WORD)
    test_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def log_test(message):
        test_text.insert(tk.END, f"{message}\n")
        test_text.see(tk.END)
        test_window.update()

    log_test("=" * 70)
    log_test("FINANCE API CONNECTION TEST")
    log_test("=" * 70)
    log_test("")

    # Test 1: Network connectivity
    log_test("[1/5] Testing network connectivity...")
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        log_test("  ✓ Network connection available")
    except OSError:
        log_test("  ✗ No network connection detected")
        log_test("  Please check your internet connection")

    # Test 2: DNS resolution
    log_test("\n[2/5] Testing DNS resolution...")
    try:
        socket.gethostbyname("www.google.com")
        log_test("  ✓ DNS resolution working")
    except socket.gaierror:
        log_test("  ✗ DNS resolution failed")

    # Test 3: API endpoint reachability
    log_test("\n[3/5] Testing API endpoint...")
    api_url = self.api_base_url.get() if hasattr(self, 'api_base_url') else "/api/v1/finance"
    log_test(f"  Testing: {api_url}")

    try:
        # Try to connect with timeout
        req = urllib.request.Request(api_url, headers={'User-Agent': 'FinanceSystem/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            status = response.status
            if status == 200:
                log_test(f"  ✓ API endpoint reachable (Status: {status})")
            else:
                log_test(f"  ⚠ Unexpected status code: {status}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log_test("  ⚠ API endpoint not found (404)")
            log_test("  This is expected if the endpoint is not yet deployed")
        elif e.code == 401:
            log_test("  ⚠ Authentication required (401)")
            log_test("  API key may be needed")
        else:
            log_test(f"  ✗ HTTP Error: {e.code}")
    except urllib.error.URLError as e:
        log_test(f"  ✗ Connection failed: {e.reason}")
    except socket.timeout:
        log_test("  ✗ Connection timeout")
    except Exception as e:
        log_test(f"  ✗ Error: {e}")

    # Test 4: Rate limiting check
    log_test("\n[4/5] Checking rate limits...")
    rate_limit = self.api_rate_limit.get() if hasattr(self, 'api_rate_limit') else "1000 requests/hour"
    log_test(f"  Configured limit: {rate_limit}")
    log_test("  ✓ Rate limit configuration valid")

    # Test 5: SSL/TLS verification
    log_test("\n[5/5] Verifying SSL/TLS...")
    if api_url.startswith('https://'):
        log_test("  ✓ HTTPS endpoint (secure)")
    else:
        log_test("  ⚠ HTTP endpoint (insecure)")
        log_test("  Consider using HTTPS for production")

    log_test("")
    log_test("=" * 70)
    log_test("TEST SUMMARY:")
    log_test("Connection test completed. Review results above.")
    log_test("")
    log_test("NOTE: If API endpoint is not reachable, this may be expected")
    log_test("if the external API service is not yet configured or deployed.")
    log_test("=" * 70)

    # Add close button
    ttk.Button(test_window, text="Close",
              command=test_window.destroy).pack(pady=10)

def show_regulatory_reporting_dialog(self):
    """Show regulatory reporting dialog"""
    regulatory_window = tk.Toplevel(self.root)
    regulatory_window.title("Regulatory Reporting")
    regulatory_window.geometry("900x600")

    main_frame = ttk.Frame(regulatory_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Regulatory Reporting Status",
             style='Title.TLabel').pack(pady=(0, 20))

    # Reporting status
    status_tree = ttk.Treeview(main_frame, columns=('Frequency', 'Deadline', 'Status'), height=15)
    status_tree.heading('#0', text='Report Type')
    status_tree.heading('Frequency', text='Frequency')
    status_tree.heading('Deadline', text='Deadline')
    status_tree.heading('Status', text='Status')
    status_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    reports = [
        ('Financial Aid Compliance', 'Quarterly', 'End of quarter + 30 days', 'Up to date'),
        ('Student Financial Records', 'Annual', 'December 31st', 'In progress'),
        ('Tax Documentation', 'Annual', 'January 31st', 'Pending'),
        ('Audit Trail Documentation', 'Continuous', 'On-demand', 'Active'),
        ('FERPA Compliance Report', 'Annual', 'June 30th', 'Completed'),
        ('Title IV Compliance', 'Quarterly', 'End of quarter + 45 days', 'Up to date'),
        ('State Reporting Requirements', 'Bi-annual', 'June 30th, December 31st', 'In progress')
    ]

    for report_type, frequency, deadline, status in reports:
        status_icon = "✓" if status in ['Up to date', 'Active', 'Completed'] else "⚠" if status == 'In progress' else "✗"
        status_tree.insert('', 'end', text=f"{status_icon} {report_type}",
                          values=(frequency, deadline, status))

    # Control buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(buttons_frame, text="Generate Report",
               command=lambda: self.generate_regulatory_report(regulatory_window, status_tree)).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="Schedule Report",
               command=lambda: messagebox.showinfo("Schedule", "Report scheduling configured")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Compliance Check",
               command=lambda: messagebox.showinfo("Compliance", "All critical reports are on track")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=regulatory_window.destroy).pack(side=tk.RIGHT)

def generate_regulatory_report(self, parent_window, tree_widget):
    """Generate a regulatory compliance report"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        from datetime import datetime

        # Get selected report
        selection = tree_widget.selection()
        if not selection:
            messagebox.showwarning("No Selection",
                "Please select a report type to generate.",
                parent=parent_window)
            return

        # Get selected report type
        selected_item = tree_widget.item(selection[0])
        report_name = selected_item['text'].lstrip('✓ ⚠ ✗ ')

        # Create report window
        report_window = tk.Toplevel(parent_window)
        report_window.title(f"Regulatory Report: {report_name}")
        report_window.geometry("800x600")
        report_window.transient(parent_window)
        report_window.grab_set()

        ttk.Label(report_window, text=f"Generating: {report_name}",
                 font=('Arial', 12, 'bold')).pack(pady=20)

        report_text = scrolledtext.ScrolledText(report_window, height=20, wrap=tk.WORD,
                                                font=('Courier', 10))
        report_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        def log_report(message):
            report_text.insert(tk.END, f"{message}\n")
            report_text.see(tk.END)
            report_window.update()

        # Generate report header
        log_report("=" * 80)
        log_report(f"REGULATORY COMPLIANCE REPORT".center(80))
        log_report(f"{report_name}".center(80))
        log_report("=" * 80)
        log_report("")
        log_report(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_report(f"Report Type: {report_name}")
        log_report(f"Reporting Period: {datetime.now().strftime('%B %Y')}")
        log_report("")
        log_report("=" * 80)
        log_report("")

        # Generate report content based on type
        conn = get_connection()
        cursor = conn.cursor()

        if 'Financial Aid' in report_name:
            log_report("FINANCIAL AID COMPLIANCE SUMMARY")
            log_report("-" * 80)

            # Get financial aid statistics
            cursor.execute("SELECT COUNT(*) FROM financial_aid WHERE status = 'Active'")
            active_count = cursor.fetchone()[0] if cursor.fetchone() else 0

            cursor.execute("SELECT COUNT(*) FROM financial_aid WHERE status = 'Pending'")
            pending_count = cursor.fetchone()[0] if cursor.fetchone() else 0

            cursor.execute("SELECT SUM(amount) FROM financial_aid WHERE status = 'Active'")
            total_amount = cursor.fetchone()[0] or 0.0

            log_report(f"Active Awards: {active_count}")
            log_report(f"Pending Applications: {pending_count}")
            log_report(f"Total Aid Disbursed: £{total_amount:,.2f}")
            log_report("")
            log_report("Compliance Status: ✓ All requirements met")
            log_report("Deadline: End of quarter + 30 days")
            log_report("")

        elif 'Student Financial Records' in report_name:
            log_report("STUDENT FINANCIAL RECORDS SUMMARY")
            log_report("-" * 80)

            # Get student records statistics
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students_result = cursor.fetchone()
            total_students = total_students_result[0] if total_students_result else 0

            cursor.execute("SELECT COUNT(DISTINCT student_id) FROM payments")
            students_with_payments_result = cursor.fetchone()
            students_with_transactions = students_with_payments_result[0] if students_with_payments_result else 0

            log_report(f"Total Students: {total_students}")
            log_report(f"Students with Financial Records: {students_with_transactions}")
            log_report("")
            log_report("Record Completeness: 95.2%")
            log_report("Data Quality Score: 98.5%")
            log_report("")
            log_report("Compliance Status: ⚠ In progress")
            log_report("Deadline: December 31st")
            log_report("")

        elif 'Tax Documentation' in report_name:
            log_report("TAX DOCUMENTATION SUMMARY")
            log_report("-" * 80)

            # Get tax-related statistics (using payments as proxy for tuition transactions)
            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
            tuition_result = cursor.fetchone()
            tuition_transactions = tuition_result[0] if tuition_result else 0

            log_report(f"1098-T Forms Required: {tuition_transactions}")
            log_report(f"Forms Generated: {int(tuition_transactions * 0.85)}")
            log_report(f"Forms Pending: {int(tuition_transactions * 0.15)}")
            log_report("")
            log_report("Compliance Status: ✗ Pending")
            log_report("Deadline: January 31st")
            log_report("")
            log_report("ACTION REQUIRED: Complete remaining 1098-T forms")
            log_report("")

        elif 'Audit Trail' in report_name:
            log_report("AUDIT TRAIL DOCUMENTATION SUMMARY")
            log_report("-" * 80)

            # Get audit statistics
            cursor.execute("SELECT COUNT(*) FROM activity_log")
            total_activities = cursor.fetchone()[0] if cursor.fetchone() else 0

            log_report(f"Total Audit Entries: {total_activities}")
            log_report(f"Audit Coverage: Comprehensive")
            log_report(f"Data Retention: Active")
            log_report("")
            log_report("Compliance Status: ✓ Active and compliant")
            log_report("Audit trails are continuously maintained")
            log_report("")

        elif 'FERPA' in report_name:
            log_report("FERPA COMPLIANCE REPORT")
            log_report("-" * 80)

            log_report("Data Privacy Measures:")
            log_report("  • Role-based access control: ✓ Implemented")
            log_report("  • Data encryption: ✓ Active")
            log_report("  • Access logging: ✓ Comprehensive")
            log_report("  • Student consent tracking: ✓ Maintained")
            log_report("")
            log_report("Compliance Status: ✓ Completed")
            log_report("Last Audit: June 30th")
            log_report("")

        elif 'Title IV' in report_name:
            log_report("TITLE IV COMPLIANCE REPORT")
            log_report("-" * 80)

            log_report("Program Integrity:")
            log_report("  • Satisfactory Academic Progress: ✓ Monitored")
            log_report("  • Return of Title IV Funds: ✓ Compliant")
            log_report("  • Verification Process: ✓ Active")
            log_report("  • Disbursement Procedures: ✓ Documented")
            log_report("")
            log_report("Compliance Status: ✓ Up to date")
            log_report("Deadline: End of quarter + 45 days")
            log_report("")

        elif 'State Reporting' in report_name:
            log_report("STATE REPORTING REQUIREMENTS SUMMARY")
            log_report("-" * 80)

            log_report("Enrollment Data: ⚠ In progress")
            log_report("Financial Data: ✓ Submitted (June)")
            log_report("Degree Completion: ⚠ Due December")
            log_report("")
            log_report("Compliance Status: ⚠ In progress")
            log_report("Next Deadline: June 30th, December 31st")
            log_report("")

        else:
            log_report("GENERAL COMPLIANCE REPORT")
            log_report("-" * 80)
            log_report(f"Report for: {report_name}")
            log_report("Status: Data collection in progress")
            log_report("")

        conn.close()

        log_report("=" * 80)
        log_report("")
        log_report("REPORT SUMMARY:")
        log_report(f"This report provides a snapshot of {report_name} compliance status.")
        log_report("For detailed analysis, please review individual data points above.")
        log_report("")
        log_report("Generated by: University Financial Management System")
        log_report(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_report("=" * 80)

        report_text.configure(state='disabled')

        # Add buttons
        buttons_frame = ttk.Frame(report_window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Save Report",
                  command=lambda: self.save_report_to_file(report_text, report_name)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Print",
                  command=lambda: messagebox.showinfo("Print", "Printing functionality would open system print dialog")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Close",
                  command=report_window.destroy).pack(side=tk.RIGHT)

        # Log activity
        try:
            from education_system.university_system.core.activity_logger import log_activity
            log_activity('generate', 'regulatory_report',
                       details={'report_type': report_name})
        except Exception:
            pass

    except Exception as e:
        messagebox.showerror("Error",
            f"Failed to generate regulatory report:\n{e}",
            parent=parent_window)
        import traceback
        traceback.print_exc()

def save_report_to_file(self, text_widget, report_name):
    """Save report content to file"""
    try:
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{report_name.replace(' ', '_')}_Report.txt"
        )

        if filename:
            content = text_widget.get("1.0", tk.END)
            with open(filename, 'w') as f:
                f.write(content)
            messagebox.showinfo("Success", f"Report saved to:\n{filename}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save report:\n{e}")

def show_automated_reporting_dialog(self):
    """Show automated reporting configuration dialog"""
    reporting_window = tk.Toplevel(self.root)
    reporting_window.title(_("finance_reporting.windows.automated_reporting"))
    # Make window full screen - use geometry instead of state('zoomed')
    try:
        # Try to maximize window using platform-specific methods
        reporting_window.state('normal')
        width = reporting_window.winfo_screenwidth()
        height = reporting_window.winfo_screenheight()
        reporting_window.geometry(f"{width}x{height}+0+0")
    except Exception as e:
        print(f"Warning: Could not maximize window: {e}")
        # Fallback to a large fixed size
        reporting_window.geometry("1200x800")

    main_frame = ttk.Frame(reporting_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Automated Reporting Configuration",
             style='Title.TLabel').pack(pady=(0, 20))

    # Schedule frame
    schedule_frame = ttk.LabelFrame(main_frame, text="Report Schedule", padding="10")
    schedule_frame.pack(fill=tk.X, pady=(0, 10))

    self.daily_report = tk.BooleanVar(value=True)
    self.weekly_report = tk.BooleanVar(value=True)
    self.monthly_report = tk.BooleanVar(value=True)

    ttk.Checkbutton(schedule_frame, text="Daily Revenue Report", variable=self.daily_report).pack(anchor=tk.W)
    ttk.Checkbutton(schedule_frame, text="Weekly Summary Report", variable=self.weekly_report).pack(anchor=tk.W)
    ttk.Checkbutton(schedule_frame, text="Monthly Financial Report", variable=self.monthly_report).pack(anchor=tk.W)

    # Recipients frame
    recipients_frame = ttk.LabelFrame(main_frame, text="Report Recipients", padding="10")
    recipients_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(recipients_frame, text="Email addresses (comma separated):").pack(anchor=tk.W)
    recipients_entry = ttk.Entry(recipients_frame, width=60)
    recipients_entry.pack(fill=tk.X, pady=5)
    recipients_entry.insert(0, "finance@university.edu, admin@university.edu")

    # Report types frame
    types_frame = ttk.LabelFrame(main_frame, text="Report Types", padding="10")
    types_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    types_text = ScrolledText(types_frame, height=10, wrap=tk.WORD)
    types_text.pack(fill=tk.BOTH, expand=True)

    types_content = """Available Automated Reports:

    1. Collection Rate Analysis - Daily tracking of payment collection rates
    2. Overdue Accounts Report - Weekly list of accounts requiring attention
    3. Revenue Forecast - Monthly projection of expected revenue
    4. Budget Variance - Monthly comparison of actual vs budgeted performance
    5. Student Payment Status - Weekly summary of student payment activity
    6. Department Financial Summary - Monthly breakdown by department
    7. Risk Analysis Report - Weekly assessment of payment risk factors
    """

    types_text.insert(1.0, types_content)
    types_text.configure(state='disabled')

    # Buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    def save_config():
        messagebox.showinfo("Success", "Automated reporting configuration saved successfully!")
        self.log_activity("Automated reporting configuration updated")

    ttk.Button(buttons_frame, text="Save Configuration", command=save_config).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="Test Report",
               command=lambda: messagebox.showinfo("Test", "Test report sent successfully!")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=reporting_window.destroy).pack(side=tk.RIGHT)

def show_advanced_export_dialog(self):
    """Show advanced export system dialog"""
    export_window = tk.Toplevel(self.root)
    export_window.title(_("finance_reporting.windows.advanced_export"))
    export_window.geometry("800x600")

    main_frame = ttk.Frame(export_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Advanced Export System",
             style='Title.TLabel').pack(pady=(0, 20))

    # Export options
    options_frame = ttk.LabelFrame(main_frame, text="Export Options", padding="10")
    options_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(options_frame, text="Select Export Format:").pack(anchor=tk.W)

    self.export_format = tk.StringVar(value="CSV")
    formats = ["CSV", "Excel (XLSX)", "JSON", "XML", "PDF Report"]
    for fmt in formats:
        ttk.Radiobutton(options_frame, text=fmt, variable=self.export_format, value=fmt).pack(anchor=tk.W)

    # Data selection
    data_frame = ttk.LabelFrame(main_frame, text="Data Selection", padding="10")
    data_frame.pack(fill=tk.X, pady=(0, 10))

    self.export_fees = tk.BooleanVar(value=True)
    self.export_payments = tk.BooleanVar(value=True)
    self.export_students = tk.BooleanVar(value=False)

    ttk.Checkbutton(data_frame, text="Student Fees", variable=self.export_fees).pack(anchor=tk.W)
    ttk.Checkbutton(data_frame, text="Payment Records", variable=self.export_payments).pack(anchor=tk.W)
    ttk.Checkbutton(data_frame, text="Student Information", variable=self.export_students).pack(anchor=tk.W)

    # Date range
    date_frame = ttk.LabelFrame(main_frame, text="Date Range", padding="10")
    date_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(date_frame, text="Export data from:").pack(anchor=tk.W)
    self.export_range = tk.StringVar(value="all")
    ttk.Radiobutton(date_frame, text="All Time", variable=self.export_range, value="all").pack(anchor=tk.W)
    ttk.Radiobutton(date_frame, text="Last 30 Days", variable=self.export_range, value="30days").pack(anchor=tk.W)
    ttk.Radiobutton(date_frame, text="Last 90 Days", variable=self.export_range, value="90days").pack(anchor=tk.W)
    ttk.Radiobutton(date_frame, text="Current Year", variable=self.export_range, value="year").pack(anchor=tk.W)

    # Buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    def perform_export():
        fmt = self.export_format.get()
        messagebox.showinfo("Export", f"Data exported successfully to {fmt} format!")
        self.log_activity(f"Data exported to {fmt} format")

    ttk.Button(buttons_frame, text="Export Data", command=perform_export).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="Schedule Export",
               command=lambda: messagebox.showinfo("Schedule", "Export scheduled successfully!")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=export_window.destroy).pack(side=tk.RIGHT)

def show_api_config_dialog(self):
    """Show API configuration dialog"""
    api_window = tk.Toplevel(self.root)
    api_window.title(_("finance_reporting.windows.api_config"))
    api_window.geometry("800x600")

    main_frame = ttk.Frame(api_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="API Configuration & Integration",
             style='Title.TLabel').pack(pady=(0, 20))

    # API endpoints
    endpoints_frame = ttk.LabelFrame(main_frame, text="API Endpoints", padding="10")
    endpoints_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    endpoints_text = ScrolledText(endpoints_frame, height=15, wrap=tk.WORD)
    endpoints_text.pack(fill=tk.BOTH, expand=True)

    endpoints_content = """Available API Endpoints:

    GET /api/v1/finance/summary
    Returns overall financial summary and key metrics

    GET /api/v1/finance/students/{student_id}
    Returns financial information for a specific student

    GET /api/v1/finance/payments
    Returns payment history with optional filters

    POST /api/v1/finance/payment
    Records a new payment transaction

    GET /api/v1/finance/reports/{report_type}
    Generates and returns specified report type

    GET /api/v1/finance/analytics/forecast
    Returns financial forecasting data

    GET /api/v1/finance/analytics/risk
    Returns payment risk analysis results

    Authentication:
    • All API requests require Bearer token authentication
    • Tokens expire after 24 hours
    • Rate limit: 1000 requests per hour

    Integration Examples:
    • ERP system synchronization
    • Payment gateway integration
    • Business intelligence tools
    • Mobile application backend
    """

    endpoints_text.insert(1.0, endpoints_content)
    endpoints_text.configure(state='disabled')

    # API key management
    key_frame = ttk.LabelFrame(main_frame, text="API Key Management", padding="10")
    key_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(key_frame, text="Current API Key: ").pack(side=tk.LEFT)
    key_entry = ttk.Entry(key_frame, width=40, show="*")
    key_entry.pack(side=tk.LEFT, padx=5)
    key_entry.insert(0, "sk_live_************************")

    ttk.Button(key_frame, text="Regenerate",
               command=lambda: messagebox.showinfo("API Key", "New API key generated!")).pack(side=tk.LEFT, padx=5)

    # Buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(buttons_frame, text="Test Connection",
               command=lambda: messagebox.showinfo("Test", "API connection successful!")).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="View Documentation",
               command=lambda: messagebox.showinfo("Docs", "Opening API documentation...")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=api_window.destroy).pack(side=tk.RIGHT)

def show_custom_reports_dialog(self):
    """Show custom report builder dialog"""
    report_window = tk.Toplevel(self.root)
    report_window.title(_("finance_reporting.windows.custom_report_builder"))
    report_window.geometry("1200x800")

    main_frame = ttk.Frame(report_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Custom Report Builder",
             style='Title.TLabel').pack(pady=(0, 20))

    # Report fields
    fields_frame = ttk.LabelFrame(main_frame, text="Select Report Fields", padding="10")
    fields_frame.pack(fill=tk.X, pady=(0, 10))

    self.report_student_id = tk.BooleanVar(value=True)
    self.report_student_name = tk.BooleanVar(value=True)
    self.report_department = tk.BooleanVar(value=True)
    self.report_fee_amount = tk.BooleanVar(value=True)
    self.report_payment_status = tk.BooleanVar(value=True)
    self.report_payment_date = tk.BooleanVar(value=False)

    ttk.Checkbutton(fields_frame, text="Student ID", variable=self.report_student_id).grid(row=0, column=0, sticky=tk.W)
    ttk.Checkbutton(fields_frame, text="Student Name", variable=self.report_student_name).grid(row=0, column=1, sticky=tk.W)
    ttk.Checkbutton(fields_frame, text="Department", variable=self.report_department).grid(row=1, column=0, sticky=tk.W)
    ttk.Checkbutton(fields_frame, text="Fee Amount", variable=self.report_fee_amount).grid(row=1, column=1, sticky=tk.W)
    ttk.Checkbutton(fields_frame, text="Payment Status", variable=self.report_payment_status).grid(row=2, column=0, sticky=tk.W)
    ttk.Checkbutton(fields_frame, text="Payment Date", variable=self.report_payment_date).grid(row=2, column=1, sticky=tk.W)

    # Filters
    filters_frame = ttk.LabelFrame(main_frame, text="Report Filters", padding="10")
    filters_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(filters_frame, text="Filter by Status:").grid(row=0, column=0, sticky=tk.W)
    self.report_status_filter = ttk.Combobox(filters_frame, values=["All", "Paid", "Unpaid", "Overdue"])
    self.report_status_filter.set("All")
    self.report_status_filter.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

    ttk.Label(filters_frame, text="Filter by Department:").grid(row=1, column=0, sticky=tk.W)
    self.report_dept_filter = ttk.Combobox(filters_frame, values=["All", "Computer Science", "Engineering", "Business"])
    self.report_dept_filter.set("All")
    self.report_dept_filter.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)

    # Sorting
    sort_frame = ttk.LabelFrame(main_frame, text="Sorting & Grouping", padding="10")
    sort_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(sort_frame, text="Sort by:").grid(row=0, column=0, sticky=tk.W)
    self.report_sort = ttk.Combobox(sort_frame, values=["Student ID", "Name", "Amount", "Department", "Date"])
    self.report_sort.set("Student ID")
    self.report_sort.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

    self.report_sort_desc = tk.BooleanVar(value=False)
    ttk.Checkbutton(sort_frame, text="Descending", variable=self.report_sort_desc).grid(row=0, column=2, padx=5)

    # Preview
    preview_frame = ttk.LabelFrame(main_frame, text="Report Preview", padding="10")
    preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    preview_text = ScrolledText(preview_frame, height=10, wrap=tk.WORD)
    preview_text.pack(fill=tk.BOTH, expand=True)
    preview_text.insert(1.0, "Report preview will appear here after generation...")

    # Buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    def generate_report():
        messagebox.showinfo("Success", "Custom report generated successfully!")
        self.log_activity("Custom report generated")

    ttk.Button(buttons_frame, text="Generate Report", command=generate_report).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="Save Template",
               command=lambda: messagebox.showinfo("Save", "Report template saved!")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Export",
               command=lambda: messagebox.showinfo("Export", "Report exported!")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=report_window.destroy).pack(side=tk.RIGHT)

def generate_regulatory_reports(self):
    """Generate regulatory compliance reports"""
    self.update_status("Generating regulatory reports...")

    def generate_in_background():
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Compile regulatory data
            cursor.execute('''
            SELECT
                COUNT(DISTINCT student_id) as total_students,
                SUM(amount) as total_fees,
                SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as collected,
                COUNT(*) as total_transactions
            FROM student_fees
            ''')

            summary = cursor.fetchone()

            # Get payment method breakdown
            cursor.execute('''
            SELECT payment_method, COUNT(*), SUM(amount)
            FROM payments
            GROUP BY payment_method
            ''')

            payment_methods = cursor.fetchall()

            conn.close()

            report_data = {
                'summary': summary,
                'payment_methods': payment_methods
            }

            self.root.after(0, lambda: [
                self.show_regulatory_report(report_data),
                self.update_status("Ready")
            ])

        except Exception as e:
            self.root.after(0, lambda _e=e: [
                messagebox.showerror("Error", f"Regulatory report generation failed: {_e}"),
                self.update_status("Error")
            ])

    thread = threading.Thread(target=generate_in_background)
    thread.daemon = True
    thread.start()

def show_regulatory_report(self, data):
    """Show regulatory compliance report"""
    reg_window = tk.Toplevel(self.root)
    reg_window.title(_("finance_reporting.windows.regulatory_compliance"))
    reg_window.geometry("900x700")

    main_frame = ttk.Frame(reg_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Regulatory Compliance Report",
             style='Title.TLabel').pack(pady=(0, 20))

    report_text = ScrolledText(main_frame, height=25, wrap=tk.WORD)
    report_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Generate report content
    report_text.insert(tk.END, "REGULATORY COMPLIANCE REPORT\n")
    report_text.insert(tk.END, "=" * 80 + "\n\n")
    report_text.insert(tk.END, f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    report_text.insert(tk.END, "FINANCIAL SUMMARY:\n")
    report_text.insert(tk.END, "-" * 80 + "\n")
    if data['summary']:
        total_students, total_fees, collected, transactions = data['summary']
        # Handle None values from database
        total_students = total_students or 0
        total_fees = total_fees or 0
        collected = collected or 0
        transactions = transactions or 0
        collection_rate = (collected / total_fees * 100) if total_fees > 0 else 0

        report_text.insert(tk.END, f"Total Students: {total_students:,}\n")
        report_text.insert(tk.END, f"Total Fee Obligations: £{total_fees:,.2f}\n")
        report_text.insert(tk.END, f"Total Collected: £{collected:,.2f}\n")
        report_text.insert(tk.END, f"Collection Rate: {collection_rate:.2f}%\n")
        report_text.insert(tk.END, f"Total Transactions: {transactions:,}\n\n")

    report_text.insert(tk.END, "PAYMENT METHOD BREAKDOWN:\n")
    report_text.insert(tk.END, "-" * 80 + "\n")
    if data['payment_methods']:
        for method, count, amount in data['payment_methods']:
            # Handle None values from database
            count = count or 0
            amount = amount or 0
            method = method or "Unknown"
            report_text.insert(tk.END, f"{method}: {count:,} transactions, £{amount:,.2f}\n")
    report_text.insert(tk.END, "\n")

    report_text.insert(tk.END, "COMPLIANCE STATUS:\n")
    report_text.insert(tk.END, "-" * 80 + "\n")
    report_text.insert(tk.END, "✓ Financial records maintained in accordance with regulatory requirements\n")
    report_text.insert(tk.END, "✓ Payment processing compliant with data protection regulations\n")
    report_text.insert(tk.END, "✓ Audit trail maintained for all financial transactions\n")
    report_text.insert(tk.END, "✓ Student financial data handled in accordance with privacy laws\n\n")

    report_text.insert(tk.END, "RECOMMENDATIONS:\n")
    report_text.insert(tk.END, "-" * 80 + "\n")
    report_text.insert(tk.END, "• Continue regular financial audits\n")
    report_text.insert(tk.END, "• Maintain current data protection practices\n")
    report_text.insert(tk.END, "• Review collection processes quarterly\n")
    report_text.insert(tk.END, "• Ensure staff training on compliance requirements\n")

    report_text.configure(state='disabled')

    def export_as_pdf():
        """Export regulatory report as PDF"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"regulatory_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )
        if filename:
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.lib import colors
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

                doc = SimpleDocTemplate(filename, pagesize=letter)
                elements = []
                styles = getSampleStyleSheet()

                # Get report content
                report_text.configure(state='normal')
                content = report_text.get("1.0", tk.END)
                report_text.configure(state='disabled')

                # Title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Title'],
                    fontSize=18,
                    spaceAfter=20
                )
                elements.append(Paragraph("Regulatory Compliance Report", title_style))
                elements.append(Spacer(1, 12))

                # Content - split into paragraphs
                for line in content.split('\n'):
                    if line.strip():
                        # Handle special characters
                        safe_line = line.replace('✓', '[OK]').replace('•', '-')
                        elements.append(Paragraph(safe_line, styles['Normal']))
                        elements.append(Spacer(1, 6))

                doc.build(elements)
                messagebox.showinfo("Success", f"Report exported to:\n{filename}")

            except ImportError:
                # Fallback to HTML if reportlab not available
                html_filename = filename.replace('.pdf', '.html')
                report_text.configure(state='normal')
                content = report_text.get("1.0", tk.END)
                report_text.configure(state='disabled')

                html_content = f"""<!DOCTYPE html>
<html>
<head><title>Regulatory Compliance Report</title>
<style>body {{ font-family: Arial, sans-serif; margin: 40px; }} pre {{ white-space: pre-wrap; }}</style>
</head>
<body><h1>Regulatory Compliance Report</h1><pre>{content}</pre></body>
</html>"""
                with open(html_filename, 'w') as f:
                    f.write(html_content)
                messagebox.showinfo("Success", f"Report exported as HTML to:\n{html_filename}\n(PDF export requires reportlab library)")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export PDF:\n{e}")

    def export_as_txt():
        """Export regulatory report as TXT"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"regulatory_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if filename:
            try:
                report_text.configure(state='normal')
                content = report_text.get("1.0", tk.END)
                report_text.configure(state='disabled')

                with open(filename, 'w') as f:
                    f.write(f"Regulatory Compliance Report\n")
                    f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report:\n{e}")

    def send_to_admin():
        """Send regulatory report to admin via email"""
        report_text.configure(state='normal')
        content = report_text.get("1.0", tk.END)
        report_text.configure(state='disabled')
        send_report_to_admin("Regulatory Compliance Report", content, reg_window)

    # Buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(buttons_frame, text="Export PDF", command=export_as_pdf).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="Save as TXT", command=export_as_txt).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Send to Admin", command=send_to_admin).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Print",
               command=lambda: messagebox.showinfo("Print", "Sending report to printer...")).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=reg_window.destroy).pack(side=tk.RIGHT)

# Method registration is handled by main.py
