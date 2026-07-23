from education_system.post_18.university_system.infrastructure.database.db import get_connection


def generate_budget_reports():
    """Generate budget reports"""
    from education_system.post_18.university_system.modules.domain.finance.reporting.budget_analysis import budget_performance_trends
    while True:
        print("\n" + "=" * 40)
        print("BUDGET REPORTS")
        print("=" * 40)
        print("1. Budget Summary Report")
        print("2. Variance Analysis Report")
        print("3. Budget Performance Trends")
        print("4. Category Performance Report")
        print("5. Return to Budget Menu")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            budget_summary_report()
        elif choice == '2':
            variance_analysis_report()
        elif choice == '3':
            budget_performance_trends()
        elif choice == '4':
            category_performance_report()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

def budget_summary_report():
    """Generate budget summary report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT bp.budget_id, bp.plan_name, bp.academic_year, bp.status,
               bp.total_revenue_budget, bp.total_expense_budget,
               (bp.total_revenue_budget - bp.total_expense_budget) as net_budget
        FROM budget_plans bp
        ORDER BY bp.academic_year DESC, bp.plan_name
        ''')

        budgets = cursor.fetchall()

        if not budgets:
            print("No budget plans found.")
            return

        print("\nBudget Summary Report:")
        print("=" * 100)
        print(f"{'ID':<5} {'Plan Name':<25} {'Academic Year':<15} {'Status':<10} {'Revenue':<12} {'Expenses':<12} {'Net':<12}")
        print("-" * 100)

        total_revenue = 0
        total_expenses = 0

        for budget in budgets:
            budget_id, plan_name, academic_year, status, revenue, expenses, net = budget

            print(f"{budget_id:<5} {plan_name:<25} {academic_year:<15} {status:<10} £{revenue or 0:<11.2f} £{expenses or 0:<11.2f} £{net or 0:<11.2f}")

            if status == 'active':
                total_revenue += revenue or 0
                total_expenses += expenses or 0

        print("-" * 100)
        print(f"Active Budgets Total: Revenue £{total_revenue:,.2f}, Expenses £{total_expenses:,.2f}, Net £{total_revenue - total_expenses:,.2f}")
        print("=" * 100)

        conn.close()

    except Exception as e:
        print(f"Error generating budget summary report: {e}")

def variance_analysis_report():
    """Generate variance analysis report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        budget_id = input("Enter budget ID for variance analysis: ").strip()

        cursor.execute('''
        SELECT bc.category_name, bc.category_type, bli.budgeted_amount,
               bli.actual_amount, (bli.actual_amount - bli.budgeted_amount) as variance
        FROM budget_line_items bli
        JOIN budget_categories bc ON bli.category_id = bc.category_id
        WHERE bli.budget_id = ?
        ORDER BY ABS(bli.actual_amount - bli.budgeted_amount) DESC
        ''', (budget_id,))

        variances = cursor.fetchall()

        if not variances:
            print("No variance data found for this budget.")
            return

        print(f"\nVariance Analysis Report - Budget ID: {budget_id}")
        print("=" * 90)
        print(f"{'Category':<30} {'Type':<8} {'Budget':<12} {'Actual':<12} {'Variance':<12} {'% Variance':<12}")
        print("-" * 90)

        for variance in variances:
            category, cat_type, budgeted, actual, var_amount = variance
            actual = actual or 0
            var_amount = var_amount or (actual - budgeted)

            if budgeted != 0:
                percent_var = (var_amount / budgeted) * 100
            else:
                percent_var = 0

            print(f"{category:<30} {cat_type:<8} £{budgeted:<11.2f} £{actual:<11.2f} £{var_amount:<11.2f} {percent_var:>10.1f}%")

        print("=" * 90)

        # Highlight significant variances
        print("\nSignificant Variances (>10%):")
        for variance in variances:
            category, cat_type, budgeted, actual, var_amount = variance
            actual = actual or 0
            var_amount = var_amount or (actual - budgeted)

            if budgeted != 0:
                percent_var = abs(var_amount / budgeted) * 100
                if percent_var > 10:
                    print(f"- {category}: {percent_var:.1f}% variance")

        conn.close()

    except Exception as e:
        print(f"Error generating variance analysis report: {e}")

def category_performance_report():
    """Generate category performance report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT bc.category_name, bc.category_type,
               COUNT(bli.line_item_id) as usage_count,
               AVG(bli.budgeted_amount) as avg_budgeted,
               AVG(bli.actual_amount) as avg_actual,
               AVG(CASE WHEN bli.budgeted_amount > 0
                   THEN (bli.actual_amount - bli.budgeted_amount) / bli.budgeted_amount * 100
                   ELSE 0 END) as avg_variance_percent
        FROM budget_categories bc
        LEFT JOIN budget_line_items bli ON bc.category_id = bli.category_id
        WHERE bc.is_active = 1
        GROUP BY bc.category_id, bc.category_name, bc.category_type
        ORDER BY bc.category_type, usage_count DESC
        ''')

        categories = cursor.fetchall()

        if not categories:
            print("No category performance data found.")
            return

        print("\nCategory Performance Report:")
        print("=" * 100)
        print(f"{'Category':<30} {'Type':<8} {'Usage':<6} {'Avg Budget':<12} {'Avg Actual':<12} {'Avg Variance':<12}")
        print("-" * 100)

        for category in categories:
            name, cat_type, usage, avg_budget, avg_actual, avg_variance = category

            print(f"{name:<30} {cat_type:<8} {usage or 0:<6} £{avg_budget or 0:<11.2f} £{avg_actual or 0:<11.2f} {avg_variance or 0:>10.1f}%")

        print("=" * 100)

        conn.close()

    except Exception as e:
        print(f"Error generating category performance report: {e}")
