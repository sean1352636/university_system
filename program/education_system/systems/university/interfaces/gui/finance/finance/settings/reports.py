"""Report menu analysis and monthly revenue trend report."""

import sys
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

from education_system.systems.university.infrastructure.i18n import get_text as _

from education_system.systems.university.interfaces.gui.finance.finance.common_imports import (
    monthly_revenue_trend_report,
)


class ReportsMixin:
    """Admin/reports menu analysis and the monthly-revenue-trend wrapper."""

    def update_admin_menu_with_missing_functions(self):
        """Update admin menu to include missing GUI functions"""
        try:
            # Define admin functions that should be available
            expected_functions = {
                'System Management': [
                    ('gui_initialize_system', 'Initialize System'),
                    ('gui_create_sample_students', 'Create Sample Data'),
                    ('gui_setup_automated_notifications', 'Setup Notifications'),
                    ('gui_send_automated_notifications', 'Send Notifications'),
                    ('gui_view_audit_logs', 'View Audit Logs'),
                    ('gui_system_settings', 'System Settings'),
                    ('launch_reporting_gui', 'Advanced Reporting GUI'),
                    ('gui_verify_fix', 'Database Verification'),
                    ('gui_check_required_packages', 'Check Packages'),
                    ('gui_setup_collection_workflows', 'Setup Workflows'),
                    ('gui_setup_email_config', 'Email Config'),
                    ('gui_setup_sms_config', 'SMS Config'),
                    ('gui_test_email_service', 'Test Email'),
                    ('gui_test_sms_service', 'Test SMS'),
                ],
                'Database Operations': [
                    ('initialize_database', 'Initialize Database'),
                    ('clean_database', 'Clean Database'),
                    ('backup_database', 'Backup Database'),
                    ('show_database_stats', 'Database Statistics'),
                ]
            }

            # Check which functions exist
            missing_functions = []
            available_functions = []

            for category, functions in expected_functions.items():
                for func_name, display_name in functions:
                    # Check if function exists in this class or gui object
                    if hasattr(self, func_name):
                        available_functions.append((category, func_name, display_name))
                    elif hasattr(self.gui, func_name):
                        available_functions.append((category, func_name, display_name))
                    elif hasattr(self.gui, 'collections') and hasattr(self.gui.collections, func_name):
                        available_functions.append((category, func_name, display_name))
                    elif hasattr(self.gui, 'db_manager') and hasattr(self.gui.db_manager, func_name):
                        available_functions.append((category, func_name, display_name))
                    elif hasattr(self.gui, 'report_manager') and hasattr(self.gui.report_manager, func_name):
                        available_functions.append((category, func_name, display_name))
                    else:
                        missing_functions.append((category, func_name, display_name))

            # Display report
            report = _("finance_gui.settings.admin_menu_analysis_report_title") + "\n"
            report += "=" * 60 + "\n\n"
            report += _("finance_gui.settings.available_functions_label", count=len(available_functions)) + "\n"
            report += _("finance_gui.settings.missing_functions_label", count=len(missing_functions)) + "\n\n"

            if missing_functions:
                report += _("finance_gui.settings.missing_functions_section") + "\n"
                report += "-" * 60 + "\n"
                for category, func_name, display_name in missing_functions:
                    report += f"  [{category}] {func_name} - {display_name}\n"
                report += "\n"

            report += _("finance_gui.settings.available_functions_section") + "\n"
            report += "-" * 60 + "\n"
            current_category = None
            for category, func_name, display_name in sorted(available_functions):
                if category != current_category:
                    report += f"\n{category}:\n"
                    current_category = category
                report += f"  \u2713 {display_name}\n"

            # Show report
            result_window = tk.Toplevel(self.gui.root)
            result_window.title(_("finance_gui.settings.admin_menu_analysis_title"))
            result_window.geometry("700x500")

            text_widget = ScrolledText(result_window, font=('Courier', 10), wrap='word')
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state='disabled')

            close_btn = ttk.Button(result_window, text=_("finance_gui.settings.btn_close"), command=result_window.destroy)
            close_btn.pack(pady=5)

            self.update_status(_("finance_gui.settings.admin_menu_analysis_completed"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_analyze_admin_menu", error=str(e)))
            print(f"Admin menu analysis error: {e}")


    def update_reports_menu_with_missing_functions(self):
        """Update reports menu to include missing GUI functions"""
        try:
            # Define report functions that should be available
            expected_functions = {
                'Financial Reports': [
                    ('gui_revenue_summary_report', 'Revenue Summary'),
                    ('gui_outstanding_fees_report', 'Outstanding Fees'),
                    ('gui_payment_collection_report', 'Payment Collection'),
                    ('gui_student_account_summary', 'Student Accounts'),
                    ('gui_fee_type_analysis', 'Fee Type Analysis'),
                    ('gui_monthly_revenue_trend_report', 'Monthly Revenue Trend'),
                    ('gui_payment_method_analysis', 'Payment Methods'),
                ],
                'Collection Reports': [
                    ('gui_aging_analysis_report', 'Aging Analysis'),
                    ('gui_collection_case_status_report', 'Collection Cases'),
                    ('gui_recovery_rate_analysis', 'Recovery Rate'),
                    ('gui_agency_performance_report', 'Agency Performance'),
                ],
                'Budget & Performance': [
                    ('gui_variance_analysis_report', 'Variance Analysis'),
                    ('gui_budget_performance_trends', 'Budget Performance'),
                    ('gui_category_performance_report', 'Category Performance'),
                    ('gui_budget_vs_actual_analysis', 'Budget vs Actual'),
                ],
                'Forecasting & Analytics': [
                    ('gui_generate_revenue_forecast', 'Revenue Forecast'),
                    ('gui_generate_predictive_analytics', 'Predictive Analytics'),
                    ('gui_generate_cash_flow_analysis', 'Cash Flow Analysis'),
                    ('gui_generate_enrollment_projections', 'Enrollment Projections'),
                    ('gui_generate_risk_analysis', 'Risk Analysis'),
                    ('gui_detect_payment_fraud', 'Payment Fraud Detection'),
                ],
                'Financial Aid Reports': [
                    ('gui_generate_aid_reports', 'Aid Reports'),
                    ('gui_scholarship_reports', 'Scholarship Reports'),
                ],
                'Audit & Compliance': [
                    ('gui_generate_audit_report', 'Audit Report'),
                    ('gui_view_audit_logs', 'Audit Logs'),
                ]
            }

            # Check which functions exist
            missing_functions = []
            available_functions = []

            for category, functions in expected_functions.items():
                for func_name, display_name in functions:
                    # Check if function exists in various managers
                    found = False
                    if hasattr(self, func_name):
                        found = True
                    elif hasattr(self.gui, func_name):
                        found = True
                    elif hasattr(self.gui, 'report_manager') and hasattr(self.gui.report_manager, func_name):
                        found = True
                    elif hasattr(self.gui, 'budget_manager') and hasattr(self.gui.budget_manager, func_name):
                        found = True
                    elif hasattr(self.gui, 'analytics') and hasattr(self.gui.analytics, func_name):
                        found = True
                    elif hasattr(self.gui, 'collections') and hasattr(self.gui.collections, func_name):
                        found = True

                    if found:
                        available_functions.append((category, func_name, display_name))
                    else:
                        missing_functions.append((category, func_name, display_name))

            # Display report
            report = _("finance_gui.settings.reports_menu_analysis_report_title") + "\n"
            report += "=" * 60 + "\n\n"
            report += _("finance_gui.settings.available_functions_label", count=len(available_functions)) + "\n"
            report += _("finance_gui.settings.missing_functions_label", count=len(missing_functions)) + "\n\n"

            if missing_functions:
                report += _("finance_gui.settings.missing_functions_section") + "\n"
                report += "-" * 60 + "\n"
                for category, func_name, display_name in missing_functions:
                    report += f"  [{category}] {func_name} - {display_name}\n"
                report += "\n"

            report += _("finance_gui.settings.available_functions_by_category") + "\n"
            report += "-" * 60 + "\n"
            current_category = None
            for category, func_name, display_name in sorted(available_functions):
                if category != current_category:
                    report += f"\n{category}:\n"
                    current_category = category
                report += f"  \u2713 {display_name}\n"

            # Show report
            result_window = tk.Toplevel(self.gui.root)
            result_window.title(_("finance_gui.settings.reports_menu_analysis_title"))
            result_window.geometry("700x600")

            text_widget = ScrolledText(result_window, font=('Courier', 10), wrap='word')
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state='disabled')

            # Add buttons frame
            btn_frame = ttk.Frame(result_window)
            btn_frame.pack(fill='x', padx=10, pady=5)

            ttk.Button(btn_frame, text=_("finance_gui.settings.btn_close"), command=result_window.destroy).pack(side='left', padx=5)

            if missing_functions:
                def export_missing():
                    """Export missing functions list"""
                    try:
                        filename = filedialog.asksaveasfilename(
                            defaultextension=".txt",
                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                        )
                        if filename:
                            with open(filename, 'w') as f:
                                f.write(_("finance_gui.settings.missing_report_functions_title") + "\n")
                                f.write("=" * 60 + "\n\n")
                                for category, func_name, display_name in missing_functions:
                                    f.write(f"{category}: {func_name} - {display_name}\n")
                            messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.export_success_msg", filename=filename))
                    except Exception as e:
                        messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.export_failed", error=str(e)))

                ttk.Button(btn_frame, text=_("finance_gui.settings.export_missing_btn"), command=export_missing).pack(side='left', padx=5)

            self.update_status(_("finance_gui.settings.reports_menu_analysis_completed"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_analyze_reports_menu", error=str(e)))
            print(f"Reports menu analysis error: {e}")

    # Additional missing GUI functions from the original finance.py


    def gui_monthly_revenue_trend_report(self):
        """GUI wrapper for monthly_revenue_trend_report"""
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            monthly_revenue_trend_report()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            self.show_tab('reports')  # Reports tab
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert('1.0', output)
            self.update_status(_("finance_gui.settings.monthly_revenue_trend_generated"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_generate_monthly_revenue", error=str(e)))
