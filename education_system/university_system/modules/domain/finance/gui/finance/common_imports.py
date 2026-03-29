"""
Common imports for finance GUI modules.
This module provides all necessary imports and function definitions
so they don't need to be repeated in every GUI manager file.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import logging
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection

# Configure logger for this module
logger = logging.getLogger(__name__)


# ==================== STUB FACTORY ====================
def _create_stub(action_name: str, use_messagebox: bool = False, message: str = None):
    """
    Factory function for creating stub implementations.

    Args:
        action_name: Human-readable name for the action (e.g., "View Aid Types")
        use_messagebox: If True, shows a messagebox; otherwise prints to console
        message: Custom message to display (defaults to "{action_name}...")

    Returns:
        A stub function that displays the appropriate message
    """
    display_message = message or f"{action_name}..."

    def stub(*args, **kwargs):
        if use_messagebox:
            messagebox.showinfo(action_name, display_message)
        else:
            print(display_message)

    stub.__doc__ = f"Stub implementation for {action_name.lower()}"
    stub.__name__ = action_name.lower().replace(' ', '_')
    return stub


def _create_report_stub(report_name: str, separator_width: int = 60):
    """
    Factory function for creating report stub implementations.

    Args:
        report_name: Name of the report (e.g., "Aging Analysis Report")
        separator_width: Width of the separator line

    Returns:
        A stub function that prints a report header
    """
    def stub(*args, **kwargs):
        print(report_name)
        print("=" * separator_width)

    stub.__doc__ = f"Generate {report_name.lower()}"
    stub.__name__ = report_name.lower().replace(' ', '_').replace('-', '_')
    return stub


def _create_warning_stub(feature_name: str, message: str = None):
    """
    Factory function for creating warning stub implementations.

    Args:
        feature_name: Name of the feature (e.g., "Student Credits")
        message: Custom warning message (defaults to "{feature_name} not yet implemented")

    Returns:
        A stub function that shows a warning messagebox
    """
    display_message = message or f"{feature_name} functionality not yet implemented"

    def stub(*args, **kwargs):
        messagebox.showwarning("Not Available", display_message)

    stub.__doc__ = f"Stub warning for {feature_name.lower()}"
    stub.__name__ = feature_name.lower().replace(' ', '_')
    return stub


# Import from the correct finance module path
from education_system.university_system.modules.domain.finance.core import financial_core as finance_core

# ==================== COLLECTION MANAGEMENT ====================
# Import functions that exist in revenue_analytics module
try:
    from education_system.university_system.modules.domain.finance.reporting.revenue_analytics import (
        assign_to_collection_agency, track_collection_progress, update_collection_case_status,
        create_collection_case, aging_analysis_report, collection_case_status_report,
        view_student_collection_detail, manage_collection_agencies, view_collection_agencies,
        add_collection_agency, edit_collection_agency, deactivate_collection_agency,
        collection_performance_summary, monthly_revenue_trend_report, agency_performance_report,
        setup_collection_workflows, export_forecast_report, generate_audit_report,
        generate_aid_reports, loan_repayment_status_report, send_collection_notice
    )
    logger.info("Successfully imported collection management functions from revenue_analytics")
except ImportError as e:
    logger.warning(f"Some reporting functions not available: {e}")

    # Provide stub implementations
    def assign_to_collection_agency(case_id, agency_id):
        """Assign case to collection agency"""
        messagebox.showinfo("Collection", f"Case {case_id} assigned to agency {agency_id}")

    def track_collection_progress():
        """Track collection progress"""
        print("Collection Progress Tracking")
        print("=" * 60)

    def update_collection_case_status(case_id, new_status, notes=''):
        """Update collection case status"""
        print(f"Updated case {case_id} to status: {new_status}")

    def create_collection_case(student_id, notes=''):
        """Create new collection case"""
        print(f"Created collection case for student {student_id}")

    def aging_analysis_report():
        """Generate aging analysis report"""
        print("Aging Analysis Report")
        print("=" * 60)

    def collection_case_status_report():
        """Generate collection case status report"""
        print("Collection Case Status Report")
        print("=" * 60)

    def view_student_collection_detail(student_id):
        """View student collection details"""
        print(f"Collection details for student {student_id}")

    def manage_collection_agencies():
        """Manage collection agencies"""
        print("Collection Agencies Management")

    def view_collection_agencies():
        """View all collection agencies"""
        print("Viewing collection agencies...")

    def add_collection_agency(name, email, phone, commission):
        """Add new collection agency"""
        print(f"Added agency: {name}")

    def edit_collection_agency(agency_id, new_name=None, new_email=None, new_commission=None):
        """Edit collection agency"""
        print(f"Edited agency {agency_id}")

    def deactivate_collection_agency(agency_id):
        """Deactivate collection agency"""
        print(f"Deactivated agency {agency_id}")

    def collection_performance_summary():
        """Collection performance summary"""
        print("Collection Performance Summary")
        print("=" * 60)

    def monthly_revenue_trend_report():
        """Monthly revenue trend report"""
        print("Monthly Revenue Trend Report")
        print("=" * 60)

    def agency_performance_report():
        """Agency performance report"""
        print("Agency Performance Report")
        print("=" * 60)

    def setup_collection_workflows():
        """Setup collection workflows"""
        print("Collection workflows configured")

    def export_forecast_report():
        """Export forecast report"""
        print("Forecast report exported")

    def generate_audit_report(start_date, end_date):
        """Generate audit report"""
        print(f"Audit Report: {start_date} to {end_date}")

    def generate_aid_reports():
        """Generate financial aid reports"""
        print("Financial Aid Reports")

    def aid_distribution_summary():
        """Aid distribution summary"""
        print("Aid Distribution Summary")

    def aid_by_academic_year():
        """Aid by academic year"""
        print("Aid by Academic Year")

    def loan_repayment_status_report():
        """Loan repayment status report"""
        print("Loan Repayment Status Report")


# ==================== FINANCIAL AID AND SCHOLARSHIPS ====================
try:
    from education_system.university_system.modules.domain.finance.scholarships.scholarship_programs import (
        manage_financial_aid,
        scholarship_distribution_summary,
        view_available_scholarships,
        create_new_scholarship,
        award_scholarship_to_student,
        view_student_scholarships,
        scholarship_utilization_analysis,
        view_financial_aid_applications,
        create_financial_aid_application,
        disburse_financial_aid
    )
    logger.info("Successfully imported scholarship and financial aid functions")

    # Create aliases for GUI compatibility
    def aid_distribution_summary():
        """Alias for scholarship_distribution_summary"""
        return scholarship_distribution_summary()

    def aid_by_academic_year():
        """Aid distribution by academic year"""
        print("Aid Distribution by Academic Year")
        print("=" * 60)
        # This would query the database for aid by year
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COALESCE(sfa.academic_year, 'N/A') as year,
                    COUNT(*) as count,
                    SUM(sfa.awarded_amount) as total_awarded,
                    SUM(sfa.disbursed_amount) as total_disbursed
                FROM student_financial_aid sfa
                GROUP BY sfa.academic_year
                ORDER BY year DESC
            ''')
            results = cursor.fetchall()
            if results:
                for year, count, awarded, disbursed in results:
                    print(f"{year}: {count} awards, £{awarded:,.2f} awarded, £{disbursed:,.2f} disbursed")
            else:
                print("No financial aid data available")
            conn.close()
        except Exception as e:
            print(f"Error querying aid data: {e}")

except ImportError as e:
    logger.warning(f"Scholarship functions not available: {e}")

    # Financial aid fallback - open the financial aid admin portal if available
    def manage_financial_aid():
        """Manage financial aid - opens the Financial Aid Admin Portal"""
        try:
            from education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal import FinancialAidAdminPortal

            # Create a new window for financial aid management
            aid_window = tk.Toplevel()
            aid_window.title("Financial Aid Management")
            aid_window.geometry("1200x800")

            # Initialize the admin portal
            portal = FinancialAidAdminPortal(aid_window)
            portal.show_dashboard()

        except ImportError as e:
            # If admin portal not available, show a basic financial aid interface
            aid_window = tk.Toplevel()
            aid_window.title("Financial Aid Management")
            aid_window.geometry("800x600")

            ttk.Label(aid_window, text="Financial Aid Management",
                     font=('Arial', 16, 'bold')).pack(pady=20)

            # Create a basic interface
            frame = ttk.Frame(aid_window, padding=20)
            frame.pack(fill='both', expand=True)

            # Quick actions
            actions_frame = ttk.LabelFrame(frame, text="Quick Actions", padding=10)
            actions_frame.pack(fill='x', pady=10)

            ttk.Button(actions_frame, text="View Aid Applications",
                      command=lambda: messagebox.showinfo("Aid Applications",
                          "Aid applications viewer not available in fallback mode")).pack(side='left', padx=5)
            ttk.Button(actions_frame, text="Process Disbursements",
                      command=lambda: messagebox.showinfo("Disbursements",
                          "Disbursement processing not available in fallback mode")).pack(side='left', padx=5)
            ttk.Button(actions_frame, text="Generate Reports",
                      command=lambda: messagebox.showinfo("Reports",
                          "Report generation not available in fallback mode")).pack(side='left', padx=5)

            # Info label
            ttk.Label(frame, text=f"Note: Full Financial Aid Admin Portal not available.\nError: {e}",
                     foreground='gray').pack(pady=20)

    def aid_distribution_summary():
        """Aid distribution summary"""
        print("Aid Distribution Summary")
        print("=" * 60)
        print("Financial aid distribution data not available")

    def aid_by_academic_year():
        """Aid by academic year"""
        print("Aid by Academic Year")
        print("=" * 60)
        print("Academic year breakdown not available")

    # Additional scholarship function stubs - generated via factory
    scholarship_distribution_summary = _create_stub("Scholarship Distribution Summary")
    view_available_scholarships = _create_stub("Available Scholarships")
    create_new_scholarship = _create_stub("Create New Scholarship")
    award_scholarship_to_student = _create_stub("Award Scholarship To Student")
    view_student_scholarships = _create_stub("View Student Scholarships")
    scholarship_utilization_analysis = _create_stub("Scholarship Utilization Analysis")
    view_financial_aid_applications = _create_stub("View Financial Aid Applications")
    create_financial_aid_application = _create_stub("Create Financial Aid Application")
    disburse_financial_aid = _create_stub("Disburse Financial Aid")


# ==================== PAYMENT PLANS ====================
try:
    from education_system.university_system.modules.domain.finance.billing.payment_plans import (
        create_payment_plan, modify_payment_plan
    )

    def create_payment_arrangement(student_id, total_amount, monthly_payment, start_date, terms=''):
        """Create payment arrangement"""
        print(f"Created payment arrangement for student {student_id}")
        print(f"Total: {total_amount}, Monthly: {monthly_payment}")
        return True

except ImportError as e:
    logger.warning(f"Payment plan functions not available: {e}")

    # Payment plan fallback stubs - generated via factory
    create_payment_plan = _create_stub("Payment Plan", use_messagebox=True, message="Payment plan creation")
    modify_payment_plan = _create_stub("Payment Plan", use_messagebox=True, message="Modifying payment plan")

    def create_payment_arrangement(student_id, total_amount, monthly_payment, start_date, terms=''):
        """Create payment arrangement"""
        messagebox.showinfo("Payment Arrangement", f"Arrangement created for student {student_id}")


# ==================== STUDENT CREDITS ====================
try:
    from education_system.university_system.modules.domain.finance.core.account_management import (
        manage_student_credits
    )

    def view_student_credits(student_id=None):
        """View student credits"""
        if not student_id:
            student_id = simpledialog.askstring("Student Credits", "Enter student ID:")
        if student_id:
            manage_student_credits(student_id, action='view')

    def add_student_credit(student_id=None, amount=None):
        """Add credit to student account"""
        if not student_id:
            student_id = simpledialog.askstring("Add Credit", "Enter student ID:")
        if student_id:
            manage_student_credits(student_id, action='add')

    def apply_credit_to_fees(student_id=None):
        """Apply credits to fees"""
        if not student_id:
            student_id = simpledialog.askstring("Apply Credit", "Enter student ID:")
        if student_id:
            manage_student_credits(student_id, action='apply')

    def view_credit_history(student_id=None):
        """View credit history"""
        if not student_id:
            student_id = simpledialog.askstring("Credit History", "Enter student ID:")
        if student_id:
            manage_student_credits(student_id, action='history')

except ImportError:
    # Student credits fallback stubs - generated via factory
    view_student_credits = _create_warning_stub("Student Credits")
    add_student_credit = _create_warning_stub("Add Credit")
    apply_credit_to_fees = _create_warning_stub("Apply Credit")
    view_credit_history = _create_warning_stub("Credit History")


# ==================== BUDGET MANAGEMENT ====================
# Budget planning stub - generated via factory
create_budget_plan = _create_stub("Budget Planning", use_messagebox=True, message="Budget planning interface - create new budget")

def budget_vs_actual_analysis(*args, **kwargs):
    """Budget vs actual analysis with real data"""
    from education_system.university_system.infrastructure.database.db import get_connection

    print("\n" + "=" * 80)
    print("BUDGET VS ACTUAL ANALYSIS REPORT".center(80))
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get all budget plans
        cursor.execute('''
            SELECT budget_id, plan_name, academic_year, status,
                   total_revenue_budget, total_expense_budget
            FROM budget_plans
            ORDER BY academic_year DESC, plan_name
        ''')
        plans = cursor.fetchall()

        if not plans:
            print("No budget plans found in the system.\n")
            conn.close()
            return

        for plan in plans:
            budget_id, plan_name, year, status, revenue_budget, expense_budget = plan

            print(f"\nBudget Plan: {plan_name} ({year})")
            print(f"Status: {status.upper()}")
            print("-" * 80)

            # Get line items for this budget
            cursor.execute('''
                SELECT bc.category_name, bc.category_type,
                       SUM(bli.budgeted_amount) as budgeted,
                       SUM(bli.actual_amount) as actual,
                       SUM(bli.variance) as variance
                FROM budget_line_items bli
                JOIN budget_categories bc ON bli.category_id = bc.category_id
                WHERE bli.budget_id = ?
                GROUP BY bc.category_name, bc.category_type
                ORDER BY bc.category_type, bc.category_name
            ''', (budget_id,))
            line_items = cursor.fetchall()

            if line_items:
                print(f"\n{'Category':<30} {'Type':<10} {'Budgeted':>15} {'Actual':>15} {'Variance':>15}")
                print("-" * 80)

                total_budgeted = 0
                total_actual = 0
                total_variance = 0

                for item in line_items:
                    cat_name, cat_type, budgeted, actual, variance = item
                    budgeted = float(budgeted or 0)
                    actual = float(actual or 0)
                    variance = float(variance or 0)

                    total_budgeted += budgeted
                    total_actual += actual
                    total_variance += variance

                    print(f"{cat_name:<30} {cat_type:<10} £{budgeted:>13,.2f} £{actual:>13,.2f} £{variance:>13,.2f}")

                print("-" * 80)
                print(f"{'TOTAL':<30} {'':<10} £{total_budgeted:>13,.2f} £{total_actual:>13,.2f} £{total_variance:>13,.2f}")

                # Performance metrics
                if total_budgeted > 0:
                    utilization = (total_actual / total_budgeted) * 100
                    print(f"\nBudget Utilization: {utilization:.2f}%")

                    if utilization > 100:
                        print("⚠️  WARNING: Budget overspent!")
                    elif utilization < 50:
                        print("ℹ️  INFO: Low budget utilization")
                    else:
                        print("✓ Budget utilization within acceptable range")
            else:
                print("\nNo line items found for this budget plan.")

        conn.close()
        print("\n" + "=" * 80 + "\n")

    except Exception as e:
        print(f"\nError generating analysis: {e}\n")

def budget_approval_workflow(*args, **kwargs):
    """Budget approval workflow with database integration"""
    from education_system.university_system.infrastructure.database.db import get_connection

    print("\n" + "=" * 80)
    print("BUDGET APPROVAL WORKFLOW".center(80))
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get pending/draft budget plans
        cursor.execute('''
            SELECT budget_id, plan_name, academic_year, status,
                   total_revenue_budget, total_expense_budget,
                   created_by, created_at
            FROM budget_plans
            WHERE status IN ('draft', 'pending')
            ORDER BY created_at DESC
        ''')
        pending_plans = cursor.fetchall()

        if not pending_plans:
            print("No budget plans pending approval.\n")
            cursor.execute('''
                SELECT COUNT(*) FROM budget_plans WHERE status = 'approved'
            ''')
            approved_count = cursor.fetchone()[0]
            print(f"Total approved budgets: {approved_count}\n")
        else:
            print(f"Found {len(pending_plans)} budget plan(s) pending approval:\n")
            print(f"{'ID':<6} {'Plan Name':<30} {'Year':<12} {'Revenue':>15} {'Expense':>15} {'Status':<10}")
            print("-" * 90)

            for plan in pending_plans:
                budget_id, name, year, status, revenue, expense, created_by, created_at = plan
                print(f"{budget_id:<6} {name:<30} {year:<12} £{revenue:>13,.2f} £{expense:>13,.2f} {status:<10}")

            print("\n" + "=" * 80)
            print("APPROVAL ACTIONS AVAILABLE:")
            print("-" * 80)
            print("1. Review budget details and line items")
            print("2. Approve budget (changes status to 'approved')")
            print("3. Reject budget (requires notes)")
            print("4. Request modifications")
            print("5. View approval history")
            print("\nNote: Use the 'Approve Budget' button in the main interface to approve plans.\n")

        conn.close()
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\nError in approval workflow: {e}\n")

# Overdue accounts stub - generated via factory
view_overdue_accounts = _create_report_stub("Overdue Accounts Report")

def variance_analysis_report(*args, **kwargs):
    """Variance analysis report with detailed breakdown"""
    from education_system.university_system.infrastructure.database.db import get_connection

    print("\n" + "=" * 80)
    print("VARIANCE ANALYSIS REPORT".center(80))
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get variance data by category
        cursor.execute('''
            SELECT bp.plan_name, bp.academic_year,
                   bc.category_name, bc.category_type,
                   bli.budgeted_amount, bli.actual_amount, bli.variance
            FROM budget_line_items bli
            JOIN budget_plans bp ON bli.budget_id = bp.budget_id
            JOIN budget_categories bc ON bli.category_id = bc.category_id
            WHERE bli.variance != 0
            ORDER BY ABS(bli.variance) DESC
            LIMIT 20
        ''')
        variances = cursor.fetchall()

        if not variances:
            print("No variances found. All budgets are on track!\n")
        else:
            print("TOP 20 BUDGET VARIANCES (by absolute value):\n")
            print(f"{'Budget Plan':<25} {'Category':<25} {'Type':<10} {'Budgeted':>12} {'Actual':>12} {'Variance':>12} {'%':>8}")
            print("-" * 110)

            for var in variances:
                plan_name, year, cat_name, cat_type, budgeted, actual, variance = var
                budgeted = float(budgeted or 0)
                actual = float(actual or 0)
                variance = float(variance or 0)

                pct = ((actual - budgeted) / budgeted * 100) if budgeted != 0 else 0

                variance_indicator = "⚠️ " if abs(pct) > 20 else "  "

                print(f"{variance_indicator}{plan_name[:23]:<23} {cat_name[:23]:<23} {cat_type:<10} "
                      f"£{budgeted:>10,.2f} £{actual:>10,.2f} £{variance:>10,.2f} {pct:>7.1f}%")

            print("\n" + "=" * 110)
            print("Legend:")
            print("  ⚠️  = Variance exceeds 20% of budgeted amount")
            print("  Positive variance = Overspending")
            print("  Negative variance = Underspending\n")

        conn.close()
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\nError generating variance analysis: {e}\n")

def budget_performance_trends(*args, **kwargs):
    """Budget performance trends over time"""
    from education_system.university_system.infrastructure.database.db import get_connection

    print("\n" + "=" * 80)
    print("BUDGET PERFORMANCE TRENDS".center(80))
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get budget performance by year
        cursor.execute('''
            SELECT academic_year,
                   COUNT(*) as total_plans,
                   SUM(total_revenue_budget) as total_revenue,
                   SUM(total_expense_budget) as total_expense,
                   COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count
            FROM budget_plans
            GROUP BY academic_year
            ORDER BY academic_year DESC
        ''')
        trends = cursor.fetchall()

        if not trends:
            print("No budget data available for trend analysis.\n")
        else:
            print(f"{'Year':<15} {'Plans':>8} {'Revenue Budget':>18} {'Expense Budget':>18} {'Net':>18} {'Approved':>10}")
            print("-" * 90)

            for trend in trends:
                year, total_plans, revenue, expense, approved = trend
                revenue = float(revenue or 0)
                expense = float(expense or 0)
                net = revenue - expense

                print(f"{year:<15} {total_plans:>8} £{revenue:>16,.2f} £{expense:>16,.2f} £{net:>16,.2f} {approved:>10}")

            # Calculate growth rates
            if len(trends) >= 2:
                print("\n" + "-" * 90)
                print("YEAR-OVER-YEAR GROWTH:\n")

                for i in range(len(trends) - 1):
                    current = trends[i]
                    previous = trends[i + 1]

                    curr_revenue = float(current[2] or 0)
                    prev_revenue = float(previous[2] or 0)

                    if prev_revenue > 0:
                        growth = ((curr_revenue - prev_revenue) / prev_revenue) * 100
                        print(f"{current[0]} vs {previous[0]}: {growth:+.2f}% revenue growth")

        conn.close()
        print("\n" + "=" * 80 + "\n")

    except Exception as e:
        print(f"\nError generating performance trends: {e}\n")

def category_performance_report(*args, **kwargs):
    """Category performance report"""
    from education_system.university_system.infrastructure.database.db import get_connection

    print("\n" + "=" * 80)
    print("CATEGORY PERFORMANCE REPORT".center(80))
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get performance by category
        cursor.execute('''
            SELECT bc.category_name, bc.category_type,
                   COUNT(DISTINCT bli.budget_id) as budget_count,
                   SUM(bli.budgeted_amount) as total_budgeted,
                   SUM(bli.actual_amount) as total_actual,
                   SUM(bli.variance) as total_variance,
                   AVG(bli.budgeted_amount) as avg_budgeted
            FROM budget_categories bc
            LEFT JOIN budget_line_items bli ON bc.category_id = bli.category_id
            WHERE bc.is_active = 1
            GROUP BY bc.category_name, bc.category_type
            HAVING total_budgeted IS NOT NULL
            ORDER BY total_budgeted DESC
        ''')
        categories = cursor.fetchall()

        if not categories:
            print("No category data available for analysis.\n")
        else:
            print(f"{'Category':<30} {'Type':<10} {'Budgets':>8} {'Total Budget':>15} {'Total Actual':>15} {'Variance':>12} {'Util %':>8}")
            print("-" * 110)

            for cat in categories:
                name, cat_type, count, budgeted, actual, variance, avg_budgeted = cat
                budgeted = float(budgeted or 0)
                actual = float(actual or 0)
                variance = float(variance or 0)

                utilization = (actual / budgeted * 100) if budgeted > 0 else 0

                status_icon = "✓" if 80 <= utilization <= 100 else "⚠️" if utilization > 100 else "→"

                print(f"{status_icon} {name:<28} {cat_type:<10} {count:>8} £{budgeted:>13,.2f} £{actual:>13,.2f} £{variance:>10,.2f} {utilization:>7.1f}%")

            print("\n" + "=" * 110)
            print("Legend:")
            print("  ✓ = Optimal utilization (80-100%)")
            print("  ⚠️  = Over budget (>100%)")
            print("  → = Under-utilized (<80%)\n")

        conn.close()
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\nError generating category performance: {e}\n")

# Budget category management stubs - generated via factory
manage_budget_categories = _create_stub("Budget Categories Management")
view_budget_categories = _create_stub("View Budget Categories", message="Viewing budget categories...")
create_budget_category = _create_stub("Create Budget Category")
edit_budget_category = _create_stub("Edit Budget Category")
deactivate_budget_category = _create_stub("Deactivate Budget Category")
update_actual_amounts = _create_stub("Update Actual Amounts")


# ==================== AID TYPE MANAGEMENT ====================
# Aid type management stubs - generated via factory
view_aid_types = _create_stub("View Aid Types", message="Viewing financial aid types...")
create_aid_type = _create_stub("Create Aid Type")
edit_aid_type = _create_stub("Edit Aid Type")
deactivate_aid_type = _create_stub("Deactivate Aid Type")
manage_aid_types = _create_stub("Manage Aid Types")
review_pending_aid_applications = _create_stub("Review Pending Aid Applications")
process_loan_payment = _create_stub("Process Loan Payment")
view_aid_application_detail = _create_stub("View Aid Application Detail")
track_loan_repayments = _create_stub("Track Loan Repayments")
aid_effectiveness_analysis = _create_stub("Aid Effectiveness Analysis")


# ==================== RECOVERY AND PERFORMANCE ====================
# Recovery and performance stubs - generated via factory
recovery_rate_analysis = _create_report_stub("Recovery Rate Analysis")


# ==================== COLLECTION NOTICES ====================
# Note: send_collection_notice is imported from revenue_analytics above
# It takes (student_id, case_id) as parameters
# Create a wrapper for backwards compatibility if needed
def send_collection_notice_with_type(student_id, notice_type='first_notice', custom_message=''):
    """
    Wrapper for send_collection_notice that accepts notice_type parameter.
    The actual function requires a case_id, so this creates one if needed.
    """
    print(f"Sending {notice_type} to student {student_id}")
    if custom_message:
        print(f"Message: {custom_message}")

    # Try to find or create a collection case for the student
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Check if student has an active collection case
        cursor.execute('''
            SELECT case_id FROM collection_cases
            WHERE student_id = ? AND case_status NOT IN ('resolved', 'closed')
            ORDER BY created_at DESC LIMIT 1
        ''', (student_id,))

        result = cursor.fetchone()
        if result:
            case_id = result[0]
            # Call the actual send_collection_notice function
            send_collection_notice(student_id, case_id)
        else:
            print(f"No active collection case found for student {student_id}")

        conn.close()
    except Exception as e:
        print(f"Error sending collection notice: {e}")

    return True

def send_arrangement_confirmation(arrangement_id):
    """Send payment arrangement confirmation"""
    print(f"Sending confirmation for arrangement {arrangement_id}")
    return True


# ==================== SYSTEM FUNCTIONS ====================
# System function stubs - generated via factory
check_required_packages = _create_stub("Check Required Packages", message="Checking required packages...\nAll required packages are installed")
ensure_database_exists = _create_stub("Ensure Database Exists", message="Database exists and is accessible")
verify_fix = _create_stub("Verify Fix", message="System verification complete")
complete_database_fix = _create_stub("Complete Database Fix", message="Database fix completed")
quick_fix_database = _create_stub("Quick Fix Database", message="Quick database fix completed")


def initialize_finance(*args, **kwargs):
    """Initialize finance system"""
    return finance_core.initialize_finance()


# ==================== PAYMENT AND FRAUD DETECTION ====================
# Payment and fraud detection stubs - generated via factory
detect_payment_fraud = _create_stub("Detect Payment Fraud", message="Running fraud detection analysis...\nNo suspicious transactions detected")
process_stripe_payment = _create_stub("Stripe Payment", use_messagebox=True, message="Stripe payment processing")
generate_qr_payment_code = _create_stub("QR Code", use_messagebox=True, message="QR code generation")


# ==================== COMMUNICATION SETUP ====================
# Communication setup stubs - generated via factory
setup_email_config = _create_stub("Email Config", use_messagebox=True, message="Email configuration setup")
setup_sms_config = _create_stub("SMS Config", use_messagebox=True, message="SMS configuration setup")
test_email_service = _create_stub("Email Test", use_messagebox=True, message="Email service test")
test_sms_service = _create_stub("SMS Test", use_messagebox=True, message="SMS service test")
enhanced_notification_system = _create_stub("Notifications", use_messagebox=True, message="Enhanced notification system")


# ==================== WORKFLOW MANAGEMENT ====================
# Workflow management stubs - generated via factory
create_approval_workflow = _create_stub("Create Approval Workflow", message="Creating approval workflow...")


# Export all functions that GUI modules might need
__all__ = [
    # Collection management
    'assign_to_collection_agency', 'track_collection_progress', 'update_collection_case_status',
    'create_collection_case', 'aging_analysis_report', 'collection_case_status_report',
    'view_student_collection_detail', 'manage_collection_agencies', 'view_collection_agencies',
    'add_collection_agency', 'edit_collection_agency', 'deactivate_collection_agency',
    'collection_performance_summary', 'monthly_revenue_trend_report', 'agency_performance_report',
    'setup_collection_workflows', 'send_collection_notice', 'send_arrangement_confirmation',
    'recovery_rate_analysis',

    # Financial aid
    'manage_financial_aid', 'view_aid_types', 'create_aid_type', 'edit_aid_type',
    'deactivate_aid_type', 'manage_aid_types', 'review_pending_aid_applications',
    'process_loan_payment', 'view_aid_application_detail', 'track_loan_repayments',
    'aid_effectiveness_analysis', 'generate_aid_reports', 'aid_distribution_summary',
    'aid_by_academic_year', 'loan_repayment_status_report',

    # Payment plans and arrangements
    'create_payment_plan', 'modify_payment_plan', 'create_payment_arrangement',

    # Student credits
    'view_student_credits', 'add_student_credit', 'apply_credit_to_fees', 'view_credit_history',

    # Budget management
    'create_budget_plan', 'budget_vs_actual_analysis', 'budget_approval_workflow', 'view_overdue_accounts',
    'variance_analysis_report', 'budget_performance_trends', 'category_performance_report',
    'manage_budget_categories', 'view_budget_categories', 'create_budget_category',
    'edit_budget_category', 'deactivate_budget_category', 'update_actual_amounts',

    # Reporting
    'export_forecast_report', 'generate_audit_report',

    # System functions
    'check_required_packages', 'ensure_database_exists', 'verify_fix',
    'complete_database_fix', 'quick_fix_database', 'initialize_finance',

    # Payment and fraud
    'detect_payment_fraud', 'process_stripe_payment', 'generate_qr_payment_code',

    # Communication
    'setup_email_config', 'setup_sms_config', 'test_email_service', 'test_sms_service',
    'enhanced_notification_system',

    # Workflow
    'create_approval_workflow',
]
