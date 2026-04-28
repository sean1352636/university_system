"""
Budget Tracker CLI Interface

Command-line interface for student budget management, expense tracking,
meal plan monitoring, and textbook cost comparison.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.finance.budget.services.budget_service import (
    BudgetManager,
    ExpenseManager,
    IncomeManager,
    MealPlanManager,
    TextbookComparisonManager,
    SavingsGoalManager
)
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

try:
    from education_system.university_system.infrastructure.shared_context import get_auth
except ImportError:
    get_auth = lambda: None

logger = logging.getLogger(__name__)

# Global auth instance
auth = None


def set_auth(auth_instance: Any) -> None:
    """Set the global auth instance for the module."""
    global auth
    auth = auth_instance


class BudgetTrackerCLI:
    """CLI interface for budget tracking functionality."""

    def __init__(self):
        """Initialize the Budget Tracker CLI."""
        self.auth = get_auth()
        if not self.auth:
            logger.warning("Auth instance not available")

    def display_menu(self) -> None:
        """Display the main budget tracker menu."""
        global auth
        if not auth:
            auth = get_auth()

        if not auth or not getattr(auth, 'current_user', None):
            print("\n" + "=" * 60)
            print("You must be logged in to access Budget Tracker features.")
            print("=" * 60)
            input("Press Enter to continue...")
            return

        current_user = auth.current_user
        user_id = current_user.get('id') or current_user.get('username')
        user_role = current_user.get('role', 'student')

        while True:
            print("\n" + "=" * 70)
            print(" " * 25 + "BUDGET TRACKER")
            print("=" * 70)
            print(f"User: {current_user.get('username', 'Unknown')} | Role: {user_role.capitalize()}")
            print("=" * 70)

            print("\n[Budget Management]")
            print("1. Create Budget Plan")
            print("2. View My Budgets")
            print("3. View Budget Summary")
            print("4. Add Budget Category")

            print("\n[Expense Tracking]")
            print("5. Add Expense")
            print("6. View Expenses")
            print("7. Update Expense")
            print("8. Delete Expense")
            print("9. View Spending by Category")
            print("10. View Spending Trends")

            print("\n[Income Tracking]")
            print("11. Add Income")
            print("12. View Income History")

            print("\n[Meal Plan Management]")
            print("13. Setup Meal Plan Tracking")
            print("14. Log Meal Transaction")
            print("15. View Meal Plan Status")
            print("16. View Meal History")

            print("\n[Textbook Comparison]")
            print("17. Compare Textbook Prices")
            print("18. Record Textbook Purchase")
            print("19. View My Textbooks")
            print("20. Get Best Deals for Course")

            print("\n[Savings Goals]")
            print("21. Create Savings Goal")
            print("22. Update Goal Progress")
            print("23. View My Goals")

            print("\n[Reports & Analytics]")
            print("24. Financial Summary Report")
            print("25. Budget vs Actual Analysis")

            print("\n0. Back to Main Menu")
            print("=" * 70)

            choice = input("\nSelect option: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.create_budget_menu(user_id)
            elif choice == '2':
                self.view_budgets_menu(user_id)
            elif choice == '3':
                self.view_budget_summary_menu(user_id)
            elif choice == '4':
                self.add_budget_category_menu(user_id)
            elif choice == '5':
                self.add_expense_menu(user_id)
            elif choice == '6':
                self.view_expenses_menu(user_id)
            elif choice == '7':
                self.update_expense_menu(user_id)
            elif choice == '8':
                self.delete_expense_menu(user_id)
            elif choice == '9':
                self.view_spending_by_category_menu(user_id)
            elif choice == '10':
                self.view_spending_trends_menu(user_id)
            elif choice == '11':
                self.add_income_menu(user_id)
            elif choice == '12':
                self.view_income_menu(user_id)
            elif choice == '13':
                self.setup_meal_plan_menu(user_id)
            elif choice == '14':
                self.log_meal_transaction_menu(user_id)
            elif choice == '15':
                self.view_meal_plan_status_menu(user_id)
            elif choice == '16':
                self.view_meal_history_menu(user_id)
            elif choice == '17':
                self.compare_textbook_prices_menu()
            elif choice == '18':
                self.record_textbook_purchase_menu(user_id)
            elif choice == '19':
                self.view_textbooks_menu(user_id)
            elif choice == '20':
                self.get_best_deals_menu()
            elif choice == '21':
                self.create_savings_goal_menu(user_id)
            elif choice == '22':
                self.update_goal_progress_menu(user_id)
            elif choice == '23':
                self.view_savings_goals_menu(user_id)
            elif choice == '24':
                self.financial_summary_menu(user_id)
            elif choice == '25':
                self.budget_vs_actual_menu(user_id)
            else:
                print("\nInvalid choice. Please try again.")

    # Budget Management Methods
    def create_budget_menu(self, student_id: str) -> None:
        """Create a new budget plan."""
        print("\n" + "=" * 60)
        print("CREATE NEW BUDGET PLAN")
        print("=" * 60)

        budget_name = input("\nBudget name: ").strip()
        if not budget_name:
            print("Budget name cannot be empty.")
            return

        print("\nBudget Type Options:")
        print("1. Monthly")
        print("2. Weekly")
        print("3. Semester")
        print("4. Annual")
        print("5. Custom")
        type_choice = input("Select type: ").strip()
        type_map = {'1': 'monthly', '2': 'weekly', '3': 'semester', '4': 'annual', '5': 'custom'}
        budget_type = type_map.get(type_choice, 'monthly')

        start_date = input("Start date (YYYY-MM-DD) [today]: ").strip()
        if not start_date:
            start_date = datetime.now().strftime('%Y-%m-%d')

        if budget_type == 'monthly':
            end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=30)).strftime('%Y-%m-%d')
        elif budget_type == 'weekly':
            end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')
        elif budget_type == 'semester':
            end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=120)).strftime('%Y-%m-%d')
        elif budget_type == 'annual':
            end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=365)).strftime('%Y-%m-%d')
        else:
            end_date = input("End date (YYYY-MM-DD): ").strip()

        total_budget = input("Total budget amount ($): ").strip()
        try:
            total_budget = float(total_budget)
        except ValueError:
            print("Invalid amount.")
            return

        # Ask if they want to add categories
        add_categories = input("\nAdd budget categories now? (y/n): ").strip().lower() == 'y'
        categories = []

        if add_categories:
            print("\nAdd categories (enter blank name to finish):")
            while True:
                cat_name = input("  Category name: ").strip()
                if not cat_name:
                    break

                print("  Category type: 1=Essential, 2=Discretionary, 3=Savings, 4=Debt")
                cat_type_choice = input("  Type: ").strip()
                cat_type_map = {'1': 'essential', '2': 'discretionary', '3': 'savings', '4': 'debt'}
                cat_type = cat_type_map.get(cat_type_choice, 'discretionary')

                cat_amount = input("  Allocated amount ($): ").strip()
                try:
                    cat_amount = float(cat_amount)
                except ValueError:
                    print("  Invalid amount, skipping category.")
                    continue

                cat_color = input("  Color code (hex, e.g., #FF5733) [optional]: ").strip() or None
                cat_icon = input("  Icon (emoji or text) [optional]: ").strip() or None

                categories.append({
                    'name': cat_name,
                    'type': cat_type,
                    'amount': cat_amount,
                    'color': cat_color,
                    'icon': cat_icon
                })

        try:
            budget_id = BudgetManager.create_budget(
                student_id=student_id,
                budget_name=budget_name,
                budget_type=budget_type,
                start_date=start_date,
                end_date=end_date,
                total_budget=total_budget,
                categories=categories if categories else None
            )
            print(f"\n✓ Budget created successfully! (Budget ID: {budget_id})")
        except Exception as e:
            print(f"\n✗ Error creating budget: {e}")

        input("\nPress Enter to continue...")

    def view_budgets_menu(self, student_id: str) -> None:
        """View all budgets for a student."""
        print("\n" + "=" * 60)
        print("MY BUDGET PLANS")
        print("=" * 60)

        try:
            budgets = BudgetManager.get_student_budgets(student_id, active_only=False)

            if not budgets:
                print("\nNo budget plans found.")
            else:
                for i, budget in enumerate(budgets, 1):
                    status = "ACTIVE" if budget['is_active'] else "INACTIVE"
                    print(f"\n{i}. {budget['budget_name']} [{status}]")
                    print(f"   Budget ID: {budget['budget_id']}")
                    print(f"   Type: {budget['budget_type'].capitalize()}")
                    print(f"   Period: {budget['start_date']} to {budget['end_date']}")
                    print(f"   Total Budget: £{budget['total_budget']:.2f}")
                    print(f"   Spent: £{budget['spent_amount']:.2f}")
                    remaining = budget['total_budget'] - budget['spent_amount']
                    print(f"   Remaining: £{remaining:.2f}")
                    print(f"   Created: {budget['created_at']}")

        except Exception as e:
            print(f"\n✗ Error retrieving budgets: {e}")

        input("\nPress Enter to continue...")

    def view_budget_summary_menu(self, student_id: str) -> None:
        """View detailed budget summary."""
        print("\n" + "=" * 60)
        print("BUDGET SUMMARY")
        print("=" * 60)

        try:
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if not budgets:
                print("\nNo active budgets found.")
                input("\nPress Enter to continue...")
                return

            for i, budget in enumerate(budgets, 1):
                print(f"{i}. {budget['budget_name']} (ID: {budget['budget_id']})")

            choice = input("\nSelect budget to view (or press Enter to cancel): ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(budgets)):
                return

            budget_id = budgets[int(choice) - 1]['budget_id']
            summary = BudgetManager.get_budget_summary(budget_id)

            print("\n" + "=" * 60)
            print(f"BUDGET: {summary['budget_name']}")
            print("=" * 60)
            print(f"\nType: {summary['budget_type'].capitalize()}")
            print(f"Period: {summary['start_date']} to {summary['end_date']}")
            print(f"\nFinancial Summary:")
            print(f"  Total Budget: £{summary['total_budget']:.2f}")
            print(f"  Allocated: £{summary['allocated_amount']:.2f}")
            print(f"  Spent: £{summary['spent_amount']:.2f}")
            print(f"  Remaining: £{summary['remaining_budget']:.2f}")
            print(f"  Budget Utilization: {summary['budget_utilization_pct']:.1f}%")

            print(f"\nTime Analysis:")
            print(f"  Total Days: {summary['total_days']}")
            print(f"  Elapsed Days: {summary['elapsed_days']}")
            print(f"  Remaining Days: {summary['remaining_days']}")
            print(f"  Time Progress: {summary['days_progress_pct']:.1f}%")
            print(f"  Recommended Daily Spending: £{summary['recommended_daily_spending']:.2f}")

            if summary['categories']:
                print("\n" + "-" * 60)
                print("BUDGET CATEGORIES")
                print("-" * 60)
                for cat in summary['categories']:
                    spent_pct = (cat['spent_amount'] / cat['allocated_amount'] * 100) if cat['allocated_amount'] > 0 else 0
                    remaining = cat['allocated_amount'] - cat['spent_amount']
                    status = "✓" if spent_pct <= 100 else "⚠"
                    print(f"\n{status} {cat['category_name']} ({cat['category_type']})")
                    print(f"  Allocated: £{cat['allocated_amount']:.2f}")
                    print(f"  Spent: £{cat['spent_amount']:.2f} ({spent_pct:.1f}%)")
                    print(f"  Remaining: £{remaining:.2f}")

        except Exception as e:
            print(f"\n✗ Error retrieving budget summary: {e}")

        input("\nPress Enter to continue...")

    def add_budget_category_menu(self, student_id: str) -> None:
        """Add a category to an existing budget."""
        print("\n" + "=" * 60)
        print("ADD BUDGET CATEGORY")
        print("=" * 60)

        try:
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if not budgets:
                print("\nNo active budgets found. Create a budget first.")
                input("\nPress Enter to continue...")
                return

            for i, budget in enumerate(budgets, 1):
                print(f"{i}. {budget['budget_name']} (ID: {budget['budget_id']})")

            choice = input("\nSelect budget (or press Enter to cancel): ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(budgets)):
                return

            budget_id = budgets[int(choice) - 1]['budget_id']

            cat_name = input("\nCategory name: ").strip()
            if not cat_name:
                return

            print("Category type: 1=Essential, 2=Discretionary, 3=Savings, 4=Debt")
            cat_type_choice = input("Type: ").strip()
            cat_type_map = {'1': 'essential', '2': 'discretionary', '3': 'savings', '4': 'debt'}
            cat_type = cat_type_map.get(cat_type_choice, 'discretionary')

            cat_amount = input("Allocated amount ($): ").strip()
            try:
                cat_amount = float(cat_amount)
            except ValueError:
                print("Invalid amount.")
                return

            from education_system.university_system.infrastructure.database.db import transaction
            with transaction() as conn:
                conn.execute('''
                    INSERT INTO student_budget_categories (
                        budget_id, category_name, category_type, allocated_amount
                    ) VALUES (?, ?, ?, ?)
                ''', (budget_id, cat_name, cat_type, cat_amount))

                conn.execute('''
                    UPDATE student_budgets
                    SET allocated_amount = allocated_amount + ?
                    WHERE budget_id = ?
                ''', (cat_amount, budget_id))

            print(f"\n✓ Category '{cat_name}' added successfully!")

        except Exception as e:
            print(f"\n✗ Error adding category: {e}")

        input("\nPress Enter to continue...")

    # Expense Tracking Methods
    def add_expense_menu(self, student_id: str) -> None:
        """Add a new expense."""
        print("\n" + "=" * 60)
        print("ADD EXPENSE")
        print("=" * 60)

        amount = input("\nAmount ($): ").strip()
        try:
            amount = float(amount)
        except ValueError:
            print("Invalid amount.")
            return

        expense_date = input("Date (YYYY-MM-DD) [today]: ").strip()
        if not expense_date:
            expense_date = datetime.now().strftime('%Y-%m-%d')

        merchant = input("Merchant/Vendor: ").strip()
        description = input("Description: ").strip()

        print("\nPayment Method:")
        print("1. Cash")
        print("2. Debit")
        print("3. Credit")
        print("4. Meal Plan")
        print("5. Financial Aid")
        print("6. Other")
        payment_choice = input("Select: ").strip()
        payment_map = {'1': 'cash', '2': 'debit', '3': 'credit', '4': 'meal-plan', '5': 'financial-aid', '6': 'other'}
        payment_method = payment_map.get(payment_choice, 'cash')

        # Select budget and category
        budget_id = None
        category_id = None

        link_budget = input("\nLink to budget? (y/n): ").strip().lower() == 'y'
        if link_budget:
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if budgets:
                for i, budget in enumerate(budgets, 1):
                    print(f"{i}. {budget['budget_name']}")
                budget_choice = input("Select budget: ").strip()
                if budget_choice.isdigit() and 1 <= int(budget_choice) <= len(budgets):
                    budget_id = budgets[int(budget_choice) - 1]['budget_id']

                    # Show categories for selected budget
                    with get_connection() as conn:
                        categories = conn.execute('''
                            SELECT * FROM student_budget_categories WHERE budget_id = ?
                        ''', (budget_id,)).fetchall()

                    if categories:
                        print("\nCategories:")
                        for i, cat in enumerate(categories, 1):
                            print(f"{i}. {cat['category_name']}")
                        cat_choice = input("Select category: ").strip()
                        if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(categories):
                            category_id = categories[int(cat_choice) - 1]['category_id']

        location = input("\nLocation (optional): ").strip() or None
        tags = input("Tags (comma-separated, optional): ").strip() or None
        notes = input("Notes (optional): ").strip() or None

        try:
            expense_id = ExpenseManager.add_expense(
                student_id=student_id,
                amount=amount,
                expense_date=expense_date,
                description=description,
                merchant_name=merchant,
                payment_method=payment_method,
                budget_id=budget_id,
                category_id=category_id,
                location=location,
                tags=tags,
                notes=notes
            )
            print(f"\n✓ Expense added successfully! (Expense ID: {expense_id})")
        except Exception as e:
            print(f"\n✗ Error adding expense: {e}")

        input("\nPress Enter to continue...")

    def view_expenses_menu(self, student_id: str) -> None:
        """View expense history."""
        print("\n" + "=" * 60)
        print("EXPENSE HISTORY")
        print("=" * 60)

        start_date = input("\nStart date (YYYY-MM-DD) [30 days ago]: ").strip()
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        end_date = input("End date (YYYY-MM-DD) [today]: ").strip()
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        try:
            expenses = ExpenseManager.get_student_expenses(student_id, start_date, end_date)

            if not expenses:
                print("\nNo expenses found for the selected period.")
            else:
                total = sum(e['amount'] for e in expenses)
                print(f"\n{len(expenses)} expenses found | Total: £{total:.2f}")
                print("-" * 60)

                for expense in expenses[:20]:  # Show first 20
                    cat_name = expense.get('category_name', 'Uncategorized')
                    print(f"\n{expense['expense_date']} | £{expense['amount']:.2f}")
                    print(f"  {expense['description']}")
                    if expense['merchant_name']:
                        print(f"  Merchant: {expense['merchant_name']}")
                    print(f"  Category: {cat_name}")
                    print(f"  Payment: {expense['payment_method']}")
                    if expense['location']:
                        print(f"  Location: {expense['location']}")

                if len(expenses) > 20:
                    print(f"\n... and {len(expenses) - 20} more expenses")

        except Exception as e:
            print(f"\n✗ Error retrieving expenses: {e}")

        input("\nPress Enter to continue...")

    def update_expense_menu(self, student_id: str) -> None:
        """Update an expense."""
        print("\n" + "=" * 60)
        print("UPDATE EXPENSE")
        print("=" * 60)

        expense_id = input("\nExpense ID: ").strip()
        if not expense_id.isdigit():
            print("Invalid expense ID.")
            return

        expense_id = int(expense_id)

        print("\nLeave fields blank to keep current values:")
        amount = input("New amount ($): ").strip()
        description = input("New description: ").strip()
        merchant = input("New merchant: ").strip()
        notes = input("New notes: ").strip()

        updates = {}
        if amount:
            try:
                updates['amount'] = float(amount)
            except ValueError:
                pass
        if description:
            updates['description'] = description
        if merchant:
            updates['merchant_name'] = merchant
        if notes:
            updates['notes'] = notes

        if not updates:
            print("\nNo updates provided.")
            return

        try:
            success = ExpenseManager.update_expense(expense_id, **updates)
            if success:
                print("\n✓ Expense updated successfully!")
            else:
                print("\n✗ Expense not found or no changes made.")
        except Exception as e:
            print(f"\n✗ Error updating expense: {e}")

        input("\nPress Enter to continue...")

    def delete_expense_menu(self, student_id: str) -> None:
        """Delete an expense."""
        print("\n" + "=" * 60)
        print("DELETE EXPENSE")
        print("=" * 60)

        expense_id = input("\nExpense ID: ").strip()
        if not expense_id.isdigit():
            print("Invalid expense ID.")
            return

        expense_id = int(expense_id)

        confirm = input(f"Are you sure you want to delete expense {expense_id}? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Deletion cancelled.")
            return

        try:
            success = ExpenseManager.delete_expense(expense_id)
            if success:
                print("\n✓ Expense deleted successfully!")
            else:
                print("\n✗ Expense not found.")
        except Exception as e:
            print(f"\n✗ Error deleting expense: {e}")

        input("\nPress Enter to continue...")

    def view_spending_by_category_menu(self, student_id: str) -> None:
        """View spending breakdown by category."""
        print("\n" + "=" * 60)
        print("SPENDING BY CATEGORY")
        print("=" * 60)

        start_date = input("\nStart date (YYYY-MM-DD) [30 days ago]: ").strip()
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        end_date = input("End date (YYYY-MM-DD) [today]: ").strip()
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        try:
            breakdown = ExpenseManager.get_spending_by_category(student_id, start_date, end_date)

            if not breakdown:
                print("\nNo spending data found for the selected period.")
            else:
                total = sum(cat['total_amount'] for cat in breakdown)
                print(f"\nPeriod: {start_date} to {end_date}")
                print(f"Total Spending: £{total:.2f}")
                print("-" * 60)

                for cat in breakdown:
                    pct = (cat['total_amount'] / total * 100) if total > 0 else 0
                    print(f"\n{cat['category_name']} ({cat['category_type'] or 'N/A'})")
                    print(f"  Total: £{cat['total_amount']:.2f} ({pct:.1f}%)")
                    print(f"  Transactions: {cat['transaction_count']}")
                    print(f"  Average: £{cat['average_amount']:.2f}")
                    print(f"  Range: £{cat['min_amount']:.2f} - £{cat['max_amount']:.2f}")

        except Exception as e:
            print(f"\n✗ Error retrieving spending breakdown: {e}")

        input("\nPress Enter to continue...")

    def view_spending_trends_menu(self, student_id: str) -> None:
        """View spending trends over time."""
        print("\n" + "=" * 60)
        print("SPENDING TRENDS")
        print("=" * 60)

        days = input("\nAnalyze past (days) [30]: ").strip()
        try:
            days = int(days) if days else 30
        except ValueError:
            days = 30

        try:
            trends = ExpenseManager.get_spending_trends(student_id, days=days)
            stats = trends['statistics']

            print(f"\nPeriod: {trends['start_date']} to {trends['end_date']} ({trends['period_days']} days)")
            print("-" * 60)
            print("\nOverall Statistics:")
            print(f"  Total Spent: £{stats['total_spent']:.2f}")
            print(f"  Total Transactions: {stats['total_transactions']}")
            print(f"  Average Transaction: £{stats['average_transaction']:.2f}")
            print(f"  Average Daily Spending: £{stats['average_daily_spending']:.2f}")
            print(f"  Transaction Range: £{stats['min_transaction']:.2f} - £{stats['max_transaction']:.2f}")

            if trends['daily_spending']:
                print("\nDaily Spending (Last 7 days):")
                for day in trends['daily_spending'][-7:]:
                    print(f"  {day['expense_date']}: £{day['daily_total']:.2f}")

        except Exception as e:
            print(f"\n✗ Error retrieving spending trends: {e}")

        input("\nPress Enter to continue...")

    # Income Tracking Methods
    def add_income_menu(self, student_id: str) -> None:
        """Add income record."""
        print("\n" + "=" * 60)
        print("ADD INCOME")
        print("=" * 60)

        amount = input("\nAmount ($): ").strip()
        try:
            amount = float(amount)
        except ValueError:
            print("Invalid amount.")
            return

        income_date = input("Date (YYYY-MM-DD) [today]: ").strip()
        if not income_date:
            income_date = datetime.now().strftime('%Y-%m-%d')

        source = input("Source (e.g., Work-Study Job, Parents): ").strip()
        if not source:
            print("Source is required.")
            return

        print("\nIncome Type:")
        print("1. Work-Study")
        print("2. Scholarship")
        print("3. Grant")
        print("4. Loan")
        print("5. Family")
        print("6. Job")
        print("7. Investment")
        print("8. Other")
        type_choice = input("Select: ").strip()
        type_map = {'1': 'work-study', '2': 'scholarship', '3': 'grant', '4': 'loan',
                   '5': 'family', '6': 'job', '7': 'investment', '8': 'other'}
        income_type = type_map.get(type_choice, 'other')

        description = input("Description (optional): ").strip()

        # Link to budget
        budget_id = None
        link_budget = input("\nLink to budget? (y/n): ").strip().lower() == 'y'
        if link_budget:
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if budgets:
                for i, budget in enumerate(budgets, 1):
                    print(f"{i}. {budget['budget_name']}")
                budget_choice = input("Select budget: ").strip()
                if budget_choice.isdigit() and 1 <= int(budget_choice) <= len(budgets):
                    budget_id = budgets[int(budget_choice) - 1]['budget_id']

        try:
            income_id = IncomeManager.add_income(
                student_id=student_id,
                amount=amount,
                income_date=income_date,
                source=source,
                income_type=income_type,
                budget_id=budget_id,
                description=description
            )
            print(f"\n✓ Income added successfully! (Income ID: {income_id})")
        except Exception as e:
            print(f"\n✗ Error adding income: {e}")

        input("\nPress Enter to continue...")

    def view_income_menu(self, student_id: str) -> None:
        """View income history."""
        print("\n" + "=" * 60)
        print("INCOME HISTORY")
        print("=" * 60)

        start_date = input("\nStart date (YYYY-MM-DD) [30 days ago]: ").strip()
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        end_date = input("End date (YYYY-MM-DD) [today]: ").strip()
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        try:
            income_records = IncomeManager.get_student_income(student_id, start_date, end_date)

            if not income_records:
                print("\nNo income records found for the selected period.")
            else:
                total = sum(i['amount'] for i in income_records)
                print(f"\n{len(income_records)} income records found | Total: £{total:.2f}")
                print("-" * 60)

                for income in income_records:
                    print(f"\n{income['income_date']} | £{income['amount']:.2f}")
                    print(f"  Source: {income['source']}")
                    print(f"  Type: {income['income_type']}")
                    if income['description']:
                        print(f"  Description: {income['description']}")

        except Exception as e:
            print(f"\n✗ Error retrieving income: {e}")

        input("\nPress Enter to continue...")

    # Meal Plan Methods
    def setup_meal_plan_menu(self, student_id: str) -> None:
        """Setup meal plan tracking."""
        print("\n" + "=" * 60)
        print("SETUP MEAL PLAN TRACKING")
        print("=" * 60)

        plan_name = input("\nPlan name (e.g., Unlimited Plus): ").strip()
        if not plan_name:
            print("Plan name is required.")
            return

        print("\nPlan Type:")
        print("1. Unlimited")
        print("2. Block (fixed meals)")
        print("3. Declining Balance (dollars)")
        print("4. Hybrid")
        type_choice = input("Select: ").strip()
        type_map = {'1': 'unlimited', '2': 'block', '3': 'declining-balance', '4': 'hybrid'}
        plan_type = type_map.get(type_choice, 'block')

        academic_term = input("Academic term (e.g., Fall 2026): ").strip()
        start_date = input("Start date (YYYY-MM-DD): ").strip()
        end_date = input("End date (YYYY-MM-DD): ").strip()

        total_meals = 0
        total_dollars = 0.0

        if plan_type in ('block', 'hybrid', 'unlimited'):
            meals = input("Total meals (0 if unlimited): ").strip()
            total_meals = int(meals) if meals.isdigit() else 0

        if plan_type in ('declining-balance', 'hybrid'):
            dollars = input("Total dollars ($): ").strip()
            try:
                total_dollars = float(dollars)
            except ValueError:
                total_dollars = 0.0

        try:
            tracking_id = MealPlanManager.create_meal_plan_tracking(
                student_id=student_id,
                plan_name=plan_name,
                plan_type=plan_type,
                academic_term=academic_term,
                start_date=start_date,
                end_date=end_date,
                total_meals=total_meals,
                total_dollars=total_dollars
            )
            print(f"\n✓ Meal plan tracking created! (Tracking ID: {tracking_id})")
        except Exception as e:
            print(f"\n✗ Error creating meal plan tracking: {e}")

        input("\nPress Enter to continue...")

    def log_meal_transaction_menu(self, student_id: str) -> None:
        """Log a meal plan transaction."""
        print("\n" + "=" * 60)
        print("LOG MEAL TRANSACTION")
        print("=" * 60)

        # Get active meal plan
        with get_connection() as conn:
            tracking = conn.execute('''
                SELECT * FROM meal_plan_tracking
                WHERE student_id = ? AND is_active = 1
                ORDER BY start_date DESC LIMIT 1
            ''', (student_id,)).fetchone()

        if not tracking:
            print("\nNo active meal plan found. Setup tracking first.")
            input("\nPress Enter to continue...")
            return

        tracking_id = tracking['tracking_id']
        print(f"\nActive Plan: {tracking['plan_name']}")

        location = input("\nDining location: ").strip()
        if not location:
            print("Location is required.")
            return

        print("\nMeal Type:")
        print("1. Breakfast")
        print("2. Lunch")
        print("3. Dinner")
        print("4. Snack")
        print("5. Guest Meal")
        meal_choice = input("Select: ").strip()
        meal_map = {'1': 'breakfast', '2': 'lunch', '3': 'dinner', '4': 'snack', '5': 'guest-meal'}
        meal_type = meal_map.get(meal_choice, 'lunch')

        transaction_date = input("Date (YYYY-MM-DD) [today]: ").strip()
        if not transaction_date:
            transaction_date = datetime.now().strftime('%Y-%m-%d')

        transaction_time = input("Time (HH:MM) [now]: ").strip()
        if not transaction_time:
            transaction_time = datetime.now().strftime('%H:%M')

        meals_used = 0
        dollars_used = 0.0

        if tracking['plan_type'] in ('block', 'unlimited', 'hybrid'):
            meals = input("Meals used [1]: ").strip()
            meals_used = int(meals) if meals.isdigit() else 1

        if tracking['plan_type'] in ('declining-balance', 'hybrid'):
            dollars = input("Dollars used ($): ").strip()
            try:
                dollars_used = float(dollars)
            except ValueError:
                dollars_used = 0.0

        description = input("Description (optional): ").strip()

        try:
            transaction_id = MealPlanManager.log_meal_transaction(
                tracking_id=tracking_id,
                student_id=student_id,
                transaction_date=transaction_date,
                transaction_time=transaction_time,
                location=location,
                meal_type=meal_type,
                meals_used=meals_used,
                dollars_used=dollars_used,
                description=description
            )
            print(f"\n✓ Meal transaction logged! (Transaction ID: {transaction_id})")
        except Exception as e:
            print(f"\n✗ Error logging meal transaction: {e}")

        input("\nPress Enter to continue...")

    def view_meal_plan_status_menu(self, student_id: str) -> None:
        """View current meal plan status."""
        print("\n" + "=" * 60)
        print("MEAL PLAN STATUS")
        print("=" * 60)

        try:
            status = MealPlanManager.get_meal_plan_status(student_id, active_only=True)

            if not status:
                print("\nNo active meal plan found.")
            else:
                print(f"\nPlan: {status['plan_name']} ({status['plan_type']})")
                print(f"Term: {status['academic_term']}")
                print(f"Period: {status['start_date']} to {status['end_date']}")

                if status['total_meals'] > 0:
                    print(f"\nMeals:")
                    print(f"  Total: {status['total_meals']}")
                    print(f"  Used: {status['used_meals']}")
                    print(f"  Remaining: {status['remaining_meals']}")
                    print(f"  Usage: {status['meals_used_pct']:.1f}%")
                    print(f"  Pace: {status['meals_pace'].upper()}")

                if status['total_dollars'] > 0:
                    print(f"\nDollars:")
                    print(f"  Total: £{status['total_dollars']:.2f}")
                    print(f"  Used: £{status['used_dollars']:.2f}")
                    print(f"  Remaining: £{status['remaining_dollars']:.2f}")
                    print(f"  Usage: {status['dollars_used_pct']:.1f}%")
                    print(f"  Pace: {status['dollars_pace'].upper()}")

                print(f"\nTime:")
                print(f"  Days Remaining: {status['days_remaining']}")
                print(f"  Progress: {status['days_progress_pct']:.1f}%")

                if status.get('projected_meals_per_day'):
                    print(f"\nProjections:")
                    print(f"  Recommended meals/day: {status['projected_meals_per_day']:.1f}")
                if status.get('projected_dollars_per_day'):
                    print(f"  Recommended $/day: £{status['projected_dollars_per_day']:.2f}")

                if status.get('weekly_average_meals'):
                    print(f"\nAverages:")
                    print(f"  Meals/week: {status['weekly_average_meals']:.1f}")
                if status.get('daily_average_dollars'):
                    print(f"  Dollars/day: £{status['daily_average_dollars']:.2f}")

        except Exception as e:
            print(f"\n✗ Error retrieving meal plan status: {e}")

        input("\nPress Enter to continue...")

    def view_meal_history_menu(self, student_id: str) -> None:
        """View meal transaction history."""
        print("\n" + "=" * 60)
        print("MEAL TRANSACTION HISTORY")
        print("=" * 60)

        days = input("\nShow past (days) [7]: ").strip()
        try:
            days = int(days) if days else 7
        except ValueError:
            days = 7

        try:
            history = MealPlanManager.get_meal_history(student_id, days=days)

            if not history:
                print(f"\nNo meal transactions found in the past {days} days.")
            else:
                print(f"\n{len(history)} transactions found")
                print("-" * 60)

                for txn in history:
                    print(f"\n{txn['transaction_date']} {txn['transaction_time']} - {txn['location']}")
                    print(f"  Type: {txn['meal_type']}")
                    if txn['meals_used'] > 0:
                        print(f"  Meals: {txn['meals_used']}")
                    if txn['dollars_used'] > 0:
                        print(f"  Dollars: £{txn['dollars_used']:.2f}")
                    if txn['description']:
                        print(f"  Note: {txn['description']}")

        except Exception as e:
            print(f"\n✗ Error retrieving meal history: {e}")

        input("\nPress Enter to continue...")

    # Textbook Methods
    def compare_textbook_prices_menu(self) -> None:
        """Compare textbook prices."""
        print("\n" + "=" * 60)
        print("COMPARE TEXTBOOK PRICES")
        print("=" * 60)

        print("\nSearch by:")
        print("1. ISBN")
        print("2. Course Code")
        choice = input("Select: ").strip()

        isbn = None
        course_code = None

        if choice == '1':
            isbn = input("\nISBN: ").strip()
        elif choice == '2':
            course_code = input("\nCourse code (e.g., CS101): ").strip()
        else:
            print("Invalid choice.")
            return

        try:
            listings = TextbookComparisonManager.compare_textbook_prices(isbn=isbn, course_code=course_code)

            if not listings:
                print("\nNo listings found.")
            else:
                print(f"\n{len(listings)} listings found")
                print("-" * 60)

                for listing in listings[:10]:
                    total_cost = listing['price'] + listing['shipping_cost']
                    print(f"\n{listing['title']}")
                    if listing['author']:
                        print(f"  Author: {listing['author']}")
                    print(f"  ISBN: {listing['isbn']}")
                    print(f"  Vendor: {listing['vendor']}")
                    print(f"  Condition: {listing['condition']}")
                    print(f"  Price: £{listing['price']:.2f} + £{listing['shipping_cost']:.2f} shipping = £{total_cost:.2f}")
                    print(f"  Availability: {listing['availability']}")

                    if listing['rental_option']:
                        print(f"  Rental: £{listing['rental_price']:.2f} ({listing['rental_period_days']} days)")
                    if listing['digital_option']:
                        print(f"  Digital: £{listing['digital_price']:.2f}")

        except Exception as e:
            print(f"\n✗ Error comparing textbook prices: {e}")

        input("\nPress Enter to continue...")

    def record_textbook_purchase_menu(self, student_id: str) -> None:
        """Record a textbook purchase."""
        print("\n" + "=" * 60)
        print("RECORD TEXTBOOK PURCHASE")
        print("=" * 60)

        isbn = input("\nISBN: ").strip()
        title = input("Title: ").strip()
        vendor = input("Vendor: ").strip()

        if not all([isbn, title, vendor]):
            print("ISBN, title, and vendor are required.")
            return

        print("\nPurchase Type:")
        print("1. Buy New")
        print("2. Buy Used")
        print("3. Rent")
        print("4. Digital")
        type_choice = input("Select: ").strip()
        type_map = {'1': 'buy-new', '2': 'buy-used', '3': 'rent', '4': 'digital'}
        purchase_type = type_map.get(type_choice, 'buy-used')

        price = input("Price paid ($): ").strip()
        try:
            price = float(price)
        except ValueError:
            print("Invalid price.")
            return

        purchase_date = input("Purchase date (YYYY-MM-DD) [today]: ").strip()
        if not purchase_date:
            purchase_date = datetime.now().strftime('%Y-%m-%d')

        course_code = input("Course code (optional): ").strip() or None

        try:
            purchase_id = TextbookComparisonManager.record_textbook_purchase(
                student_id=student_id,
                isbn=isbn,
                title=title,
                vendor=vendor,
                purchase_type=purchase_type,
                price_paid=price,
                purchase_date=purchase_date,
                course_code=course_code
            )
            print(f"\n✓ Textbook purchase recorded! (Purchase ID: {purchase_id})")
        except Exception as e:
            print(f"\n✗ Error recording purchase: {e}")

        input("\nPress Enter to continue...")

    def view_textbooks_menu(self, student_id: str) -> None:
        """View purchased textbooks."""
        print("\n" + "=" * 60)
        print("MY TEXTBOOKS")
        print("=" * 60)

        try:
            textbooks = TextbookComparisonManager.get_student_textbooks(student_id)

            if not textbooks:
                print("\nNo textbook purchases found.")
            else:
                total_spent = sum(t['price_paid'] for t in textbooks)
                print(f"\n{len(textbooks)} textbooks | Total spent: £{total_spent:.2f}")
                print("-" * 60)

                for book in textbooks:
                    print(f"\n{book['title']}")
                    print(f"  ISBN: {book['isbn']}")
                    if book['course_code']:
                        print(f"  Course: {book['course_code']}")
                    print(f"  Purchased: {book['purchase_date']}")
                    print(f"  Vendor: {book['vendor']}")
                    print(f"  Type: {book['purchase_type']}")
                    print(f"  Price: £{book['price_paid']:.2f}")
                    if book['rental_due_date']:
                        print(f"  Rental Due: {book['rental_due_date']}")

        except Exception as e:
            print(f"\n✗ Error retrieving textbooks: {e}")

        input("\nPress Enter to continue...")

    def get_best_deals_menu(self) -> None:
        """Get best textbook deals for a course."""
        print("\n" + "=" * 60)
        print("BEST TEXTBOOK DEALS FOR COURSE")
        print("=" * 60)

        course_code = input("\nCourse code (e.g., CS101): ").strip()
        if not course_code:
            return

        try:
            deals = TextbookComparisonManager.get_best_textbook_deals(course_code)

            if not deals['books']:
                print(f"\nNo textbooks found for course {course_code}.")
            else:
                print(f"\nCourse: {deals['course_code']}")
                print(f"Books Required: {len(deals['books'])}")
                print(f"Total Cost (All New): £{deals['total_cost_new']:.2f}")
                print(f"Total Cost (Best Deals): £{deals['total_cost_best_deals']:.2f}")
                print(f"Potential Savings: £{deals['potential_savings']:.2f}")
                print("-" * 60)

                for book in deals['books']:
                    print(f"\n{book['title']}")
                    print(f"  ISBN: {book['isbn']}")
                    print(f"  Best New: £{book['best_new']:.2f}" if book['best_new'] else "  Best New: N/A")
                    print(f"  Best Used: £{book['best_used']:.2f}" if book['best_used'] else "  Best Used: N/A")
                    print(f"  Best Rental: £{book['best_rental']:.2f}" if book['best_rental'] else "  Best Rental: N/A")
                    print(f"  Best Digital: £{book['best_digital']:.2f}" if book['best_digital'] else "  Best Digital: N/A")
                    print(f"  ★ RECOMMENDED: {book['recommended_option']} - £{book['recommended_price']:.2f}")

        except Exception as e:
            print(f"\n✗ Error retrieving best deals: {e}")

        input("\nPress Enter to continue...")

    # Savings Goals Methods
    def create_savings_goal_menu(self, student_id: str) -> None:
        """Create a savings goal."""
        print("\n" + "=" * 60)
        print("CREATE SAVINGS GOAL")
        print("=" * 60)

        goal_name = input("\nGoal name (e.g., Spring Break Trip): ").strip()
        if not goal_name:
            print("Goal name is required.")
            return

        target_amount = input("Target amount ($): ").strip()
        try:
            target_amount = float(target_amount)
        except ValueError:
            print("Invalid amount.")
            return

        target_date = input("Target date (YYYY-MM-DD) [optional]: ").strip() or None

        print("\nPriority:")
        print("1. Low")
        print("2. Medium")
        print("3. High")
        priority_choice = input("Select [2]: ").strip()
        priority_map = {'1': 'low', '2': 'medium', '3': 'high'}
        priority = priority_map.get(priority_choice, 'medium')

        category = input("Category (e.g., Travel, Emergency Fund) [optional]: ").strip()
        description = input("Description [optional]: ").strip()

        try:
            goal_id = SavingsGoalManager.create_goal(
                student_id=student_id,
                goal_name=goal_name,
                target_amount=target_amount,
                target_date=target_date,
                priority=priority,
                category=category,
                description=description
            )
            print(f"\n✓ Savings goal created! (Goal ID: {goal_id})")
        except Exception as e:
            print(f"\n✗ Error creating savings goal: {e}")

        input("\nPress Enter to continue...")

    def update_goal_progress_menu(self, student_id: str) -> None:
        """Update savings goal progress."""
        print("\n" + "=" * 60)
        print("UPDATE GOAL PROGRESS")
        print("=" * 60)

        try:
            goals = SavingsGoalManager.get_student_goals(student_id, active_only=True)

            if not goals:
                print("\nNo active savings goals found.")
                input("\nPress Enter to continue...")
                return

            for i, goal in enumerate(goals, 1):
                print(f"{i}. {goal['goal_name']} - £{goal['current_amount']:.2f} / £{goal['target_amount']:.2f} ({goal['progress_pct']:.1f}%)")

            choice = input("\nSelect goal: ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(goals)):
                return

            goal_id = goals[int(choice) - 1]['goal_id']

            amount = input("\nAmount to add ($): ").strip()
            try:
                amount = float(amount)
            except ValueError:
                print("Invalid amount.")
                return

            success = SavingsGoalManager.update_goal_progress(goal_id, amount)
            if success:
                print(f"\n✓ Goal progress updated! Added £{amount:.2f}")

                # Check if goal completed
                updated_goals = SavingsGoalManager.get_student_goals(student_id, active_only=False)
                updated_goal = next((g for g in updated_goals if g['goal_id'] == goal_id), None)
                if updated_goal and updated_goal['status'] == 'completed':
                    print(f"\n🎉 Congratulations! You've reached your goal '{updated_goal['goal_name']}'!")
            else:
                print("\n✗ Failed to update goal progress.")

        except Exception as e:
            print(f"\n✗ Error updating goal progress: {e}")

        input("\nPress Enter to continue...")

    def view_savings_goals_menu(self, student_id: str) -> None:
        """View savings goals."""
        print("\n" + "=" * 60)
        print("MY SAVINGS GOALS")
        print("=" * 60)

        show_all = input("\nShow completed goals too? (y/n) [n]: ").strip().lower() == 'y'

        try:
            goals = SavingsGoalManager.get_student_goals(student_id, active_only=not show_all)

            if not goals:
                print("\nNo savings goals found.")
            else:
                for goal in goals:
                    status_icon = "✓" if goal['status'] == 'completed' else "⏳"
                    print(f"\n{status_icon} {goal['goal_name']} [{goal['priority'].upper()}]")
                    print(f"   Goal ID: {goal['goal_id']}")
                    print(f"   Target: £{goal['target_amount']:.2f}")
                    print(f"   Saved: £{goal['current_amount']:.2f}")
                    print(f"   Remaining: £{goal['remaining_amount']:.2f}")
                    print(f"   Progress: {goal['progress_pct']:.1f}%")

                    if goal.get('target_date'):
                        print(f"   Target Date: {goal['target_date']}")
                        if goal.get('days_remaining'):
                            print(f"   Days Remaining: {goal['days_remaining']}")
                        if goal.get('required_daily_savings'):
                            print(f"   Required Daily Savings: £{goal['required_daily_savings']:.2f}")

                    if goal['category']:
                        print(f"   Category: {goal['category']}")
                    if goal['description']:
                        print(f"   Description: {goal['description']}")
                    print(f"   Status: {goal['status'].capitalize()}")

        except Exception as e:
            print(f"\n✗ Error retrieving savings goals: {e}")

        input("\nPress Enter to continue...")

    # Reports & Analytics
    def financial_summary_menu(self, student_id: str) -> None:
        """Display comprehensive financial summary."""
        print("\n" + "=" * 60)
        print("FINANCIAL SUMMARY REPORT")
        print("=" * 60)

        try:
            # Get active budget
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if budgets:
                budget = budgets[0]
                summary = BudgetManager.get_budget_summary(budget['budget_id'])

                print("\nCurrent Budget:")
                print(f"  {summary['budget_name']} ({summary['budget_type']})")
                print(f"  Total: £{summary['total_budget']:.2f}")
                print(f"  Spent: £{summary['spent_amount']:.2f}")
                print(f"  Remaining: £{summary['remaining_budget']:.2f}")
                print(f"  Utilization: {summary['budget_utilization_pct']:.1f}%")

            # Recent expenses
            recent_expenses = ExpenseManager.get_student_expenses(student_id,
                start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            if recent_expenses:
                total_expenses = sum(e['amount'] for e in recent_expenses)
                print(f"\nRecent Expenses (30 days):")
                print(f"  Total: £{total_expenses:.2f}")
                print(f"  Transactions: {len(recent_expenses)}")
                print(f"  Average: £{total_expenses / len(recent_expenses):.2f}")

            # Recent income
            recent_income = IncomeManager.get_student_income(student_id,
                start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            if recent_income:
                total_income = sum(i['amount'] for i in recent_income)
                print(f"\nRecent Income (30 days):")
                print(f"  Total: £{total_income:.2f}")
                print(f"  Sources: {len(recent_income)}")

                # Net income
                if recent_expenses:
                    net = total_income - total_expenses
                    print(f"\nNet Income (30 days): £{net:.2f}")

            # Savings goals
            goals = SavingsGoalManager.get_student_goals(student_id, active_only=True)
            if goals:
                total_goal_target = sum(g['target_amount'] for g in goals)
                total_goal_saved = sum(g['current_amount'] for g in goals)
                print(f"\nSavings Goals:")
                print(f"  Active Goals: {len(goals)}")
                print(f"  Total Target: £{total_goal_target:.2f}")
                print(f"  Total Saved: £{total_goal_saved:.2f}")
                print(f"  Remaining: £{total_goal_target - total_goal_saved:.2f}")

            # Meal plan
            meal_status = MealPlanManager.get_meal_plan_status(student_id)
            if meal_status:
                print(f"\nMeal Plan: {meal_status['plan_name']}")
                if meal_status.get('remaining_meals'):
                    print(f"  Meals Remaining: {meal_status['remaining_meals']}")
                if meal_status.get('remaining_dollars'):
                    print(f"  Dollars Remaining: £{meal_status['remaining_dollars']:.2f}")

        except Exception as e:
            print(f"\n✗ Error generating financial summary: {e}")

        input("\nPress Enter to continue...")

    def budget_vs_actual_menu(self, student_id: str) -> None:
        """Compare budgeted vs actual spending."""
        print("\n" + "=" * 60)
        print("BUDGET VS ACTUAL ANALYSIS")
        print("=" * 60)

        try:
            budgets = BudgetManager.get_student_budgets(student_id, active_only=True)
            if not budgets:
                print("\nNo active budgets found.")
                input("\nPress Enter to continue...")
                return

            for i, budget in enumerate(budgets, 1):
                print(f"{i}. {budget['budget_name']}")

            choice = input("\nSelect budget: ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(budgets)):
                return

            budget_id = budgets[int(choice) - 1]['budget_id']
            summary = BudgetManager.get_budget_summary(budget_id)

            print("\n" + "=" * 60)
            print(f"BUDGET VS ACTUAL: {summary['budget_name']}")
            print("=" * 60)

            print(f"\nOverall Performance:")
            print(f"  Budgeted: £{summary['total_budget']:.2f}")
            print(f"  Spent: £{summary['spent_amount']:.2f}")
            print(f"  Variance: £{summary['remaining_budget']:.2f}")
            print(f"  Utilization: {summary['budget_utilization_pct']:.1f}%")

            print(f"\nTime Progress: {summary['days_progress_pct']:.1f}%")
            print(f"Spending Progress: {summary['budget_utilization_pct']:.1f}%")

            if summary['budget_utilization_pct'] > summary['days_progress_pct'] + 10:
                print("⚠ WARNING: Spending ahead of schedule!")
            elif summary['budget_utilization_pct'] < summary['days_progress_pct'] - 10:
                print("✓ Good: Spending below pace")
            else:
                print("✓ On track")

            if summary['categories']:
                print("\n" + "-" * 60)
                print("CATEGORY BREAKDOWN")
                print("-" * 60)

                for cat in summary['categories']:
                    spent_pct = (cat['spent_amount'] / cat['allocated_amount'] * 100) if cat['allocated_amount'] > 0 else 0
                    variance = cat['allocated_amount'] - cat['spent_amount']

                    status = "✓" if spent_pct <= 100 else "⚠"
                    print(f"\n{status} {cat['category_name']}")
                    print(f"  Budgeted: £{cat['allocated_amount']:.2f}")
                    print(f"  Spent: £{cat['spent_amount']:.2f} ({spent_pct:.1f}%)")
                    print(f"  Variance: £{variance:.2f}")

                    if spent_pct > 100:
                        print(f"  ⚠ OVER BUDGET by £{-variance:.2f}")
                    elif spent_pct > 90:
                        print(f"  ⚠ Near limit")

        except Exception as e:
            print(f"\n✗ Error generating budget vs actual analysis: {e}")

        input("\nPress Enter to continue...")


# Module entry point function for CLI integration
def display_budget_tracker_menu() -> None:
    """Display the budget tracker menu."""
    cli = BudgetTrackerCLI()
    cli.display_menu()


# Backward compatibility alias
def run():
    """Run the Budget Tracker CLI."""
    display_budget_tracker_menu()


if __name__ == "__main__":
    run()
