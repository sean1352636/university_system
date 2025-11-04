from __future__ import annotations

import logging
import random
from datetime import datetime

from . import restaurant_context as ctx
from university_system.modules.core.services.restaurant_misc.restaurant_context import (
    backup_before_operation,
    expense_analytics,
    export_expense_report,
    get_db_connection,
)
from university_system.modules.core.services.restaurant_misc.audit import log_audit_action

def profit_loss_statement():
    """Generate profit and loss statement"""
    try:
        start_date = input("Enter start date (YYYY-MM-DD): ")
        end_date = input("Enter end date (YYYY-MM-DD): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Revenue
        cursor.execute('''
            SELECT SUM(total_price) as total_revenue
            FROM restaurant_orders
            WHERE DATE(order_time) BETWEEN ? AND ? AND status = 'Completed'
        ''', (start_date, end_date))

        revenue = cursor.fetchone()[0] or 0

        # Cost of Goods Sold (estimated from menu items cost)
        cursor.execute('''
            SELECT SUM(oi.quantity * mi.cost_price) as cogs
            FROM restaurant_order_items oi
            JOIN menu_items mi ON oi.item_id = mi.item_id
            JOIN restaurant_orders o ON oi.order_id = o.order_id
            WHERE DATE(o.order_time) BETWEEN ? AND ? AND o.status = 'Completed'
            AND mi.cost_price IS NOT NULL
        ''', (start_date, end_date))

        cogs = cursor.fetchone()[0] or 0

        # Operating Expenses
        cursor.execute('''
            SELECT 
                category,
                SUM(amount) as total
            FROM restaurant_expenses
            WHERE DATE(expense_date) BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
        ''', (start_date, end_date))

        expenses = cursor.fetchall()
        total_expenses = sum(exp[1] for exp in expenses)

        # Calculate metrics
        gross_profit = revenue - cogs
        operating_profit = gross_profit - total_expenses
        gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
        operating_margin = (operating_profit / revenue * 100) if revenue > 0 else 0

        print(f"\n" + "="*80)
        print(f"PROFIT & LOSS STATEMENT")
        print(f"Period: {start_date} to {end_date}")
        print("="*80)

        print(f"REVENUE:")
        print(f"Total Sales Revenue: £{revenue:,.2f}")

        print(f"\nCOST OF GOODS SOLD:")
        print(f"Direct Costs: £{cogs:,.2f}")
        print(f"Gross Profit: £{gross_profit:,.2f}")
        print(f"Gross Margin: {gross_margin:.1f}%")

        print(f"\nOPERATING EXPENSES:")
        for category, amount in expenses:
            print(f"  {category}: £{amount:,.2f}")
        print(f"Total Operating Expenses: £{total_expenses:,.2f}")

        print(f"\nPROFITABILITY:")
        print(f"Operating Profit: £{operating_profit:,.2f}")
        print(f"Operating Margin: {operating_margin:.1f}%")

        print("="*80)

        conn.close()

    except Exception as e:
        logging.error(f"Error in profit_loss_statement: {e}")
        print(f"An error occurred: {e}")

def expense_tracking():
    """Expense tracking and management"""
    try:
        print("\n" + "="*50)
        print("EXPENSE TRACKING")
        print("="*50)

        print("\nOptions:")
        print("1. Add new expense")
        print("2. View expenses")
        print("3. Expense analytics")
        print("4. Export expense report")
        print("5. Return to financial menu")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            add_expense()
        elif choice == '2':
            view_expenses()
        elif choice == '3':
            expense_analytics()
        elif choice == '4':
            export_expense_report()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in expense_tracking: {e}")
        print(f"An error occurred: {e}")

def add_expense():
    """Add new expense"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to add expenses.")
        return

    if not ctx.auth.check_permission('manage_finances'):
        print("You don't have permission to add expenses.")
        return

    try:
        backup_before_operation('add_expense')

        print("\n" + "="*50)
        print("ADD NEW EXPENSE")
        print("="*50)

        # Generate expense ID
        conn = get_db_connection()
        cursor = conn.cursor()

        expense_id = f"EXP{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        print("Expense categories:")
        print("1. Food & Beverages")
        print("2. Staff Wages")
        print("3. Utilities")
        print("4. Rent")
        print("5. Equipment")
        print("6. Marketing")
        print("7. Maintenance")
        print("8. Insurance")
        print("9. Other")

        category_choice = input("Choose category (1-9): ")
        categories = {
            '1': 'Food & Beverages',
            '2': 'Staff Wages',
            '3': 'Utilities',
            '4': 'Rent',
            '5': 'Equipment',
            '6': 'Marketing',
            '7': 'Maintenance',
            '8': 'Insurance'
        }

        if category_choice == '9':
            category = input("Enter custom category: ").strip()
        else:
            category = categories.get(category_choice, 'Other')

        description = input("Enter expense description: ").strip()
        if not description:
            print("Description is required.")
            conn.close()
            return

        try:
            amount = float(input("Enter amount (£): "))
            if amount <= 0:
                raise ValueError
        except ValueError:
            print("Invalid amount.")
            conn.close()
            return

        expense_date = input("Enter expense date (YYYY-MM-DD) or press Enter for today: ").strip()
        if not expense_date:
            expense_date = datetime.now().strftime('%Y-%m-%d')
        else:
            try:
                datetime.strptime(expense_date, '%Y-%m-%d')
            except ValueError:
                print("Invalid date format.")
                conn.close()
                return

        print("\nPayment methods:")
        print("1. Cash")
        print("2. Card")
        print("3. Bank Transfer")
        print("4. Cheque")

        payment_choice = input("Choose payment method (1-4): ")
        payment_methods = {
            '1': 'Cash',
            '2': 'Card',
            '3': 'Bank Transfer',
            '4': 'Cheque'
        }
        payment_method = payment_methods.get(payment_choice, 'Cash')

        vendor = input("Enter vendor/supplier name: ").strip()
        receipt_path = input("Enter receipt file path (optional): ").strip()

        # Insert expense
        cursor.execute('''
            INSERT INTO restaurant_expenses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            expense_id, category, description, amount, expense_date, payment_method,
            vendor, receipt_path, ctx.auth.current_user['id'], 'Approved',
            datetime.now().strftime('%Y-%m-%d'), ctx.auth.current_user['id']
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Expense added successfully!")
        print(f"Expense ID: {expense_id}")
        print(f"Category: {category}")
        print(f"Description: {description}")
        print(f"Amount: £{amount:.2f}")
        print(f"Date: {expense_date}")
        print(f"Payment Method: {payment_method}")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'ADD_EXPENSE',
            'restaurant_expenses',
            expense_id,
            None,
            {'category': category, 'amount': amount, 'description': description}
        )

    except Exception as e:
        logging.error(f"Error in add_expense: {e}")
        print(f"An error occurred: {e}")

def view_expenses():
    """View expenses with filtering"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All expenses (last 50)")
        print("2. By category")
        print("3. By date range")
        print("4. This month")
        print("5. Pending approval")

        filter_choice = input("Choose filter (1-5): ")

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_expenses ORDER BY expense_date DESC LIMIT 50')
        elif filter_choice == '2':
            category = input("Enter category: ")
            cursor.execute('SELECT * FROM restaurant_expenses WHERE category = ? ORDER BY expense_date DESC', 
                          (category,))
        elif filter_choice == '3':
            start_date = input("Enter start date (YYYY-MM-DD): ")
            end_date = input("Enter end date (YYYY-MM-DD): ")
            cursor.execute('''
                SELECT * FROM restaurant_expenses 
                WHERE DATE(expense_date) BETWEEN ? AND ? 
                ORDER BY expense_date DESC
            ''', (start_date, end_date))
        elif filter_choice == '4':
            current_month = datetime.now().strftime('%Y-%m')
            cursor.execute('''
                SELECT * FROM restaurant_expenses 
                WHERE strftime('%Y-%m', expense_date) = ?
                ORDER BY expense_date DESC
            ''', (current_month,))
        elif filter_choice == '5':
            cursor.execute('SELECT * FROM restaurant_expenses WHERE status = ? ORDER BY expense_date DESC', 
                          ('Pending',))

        expenses = cursor.fetchall()

        if not expenses:
            print("No expenses found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("EXPENSES")
        print("="*120)
        print(f"{'Expense ID':<15} {'Date':<12} {'Category':<15} {'Description':<25} {'Amount':<10} {'Vendor':<15} {'Status':<10}")
        print("-"*120)

        total_amount = 0
        for expense in expenses:
            expense_date = expense[4][:10] if expense[4] else 'N/A'
            description = expense[2][:24] if len(expense[2]) > 24 else expense[2]
            vendor = expense[6][:14] if expense[6] and len(expense[6]) > 14 else (expense[6] or 'N/A')

            print(f"{expense[0]:<15} {expense_date:<12} {expense[1]:<15} {description:<25} £{expense[3]:<9.2f} {vendor:<15} {expense[9]:<10}")
            total_amount += expense[3]

        print("-"*120)
        print(f"{'TOTAL':<67} £{total_amount:<9.2f}")
        print("="*120)

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_expenses: {e}")
        print(f"An error occurred: {e}")

def budget_management():
    """Budget management functionality"""
    try:
        print("\n" + "="*50)
        print("BUDGET MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View budgets")
        print("2. Create budget")
        print("3. Update budget")
        print("4. Budget vs actual analysis")
        print("5. Return to financial menu")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            view_budgets()
        elif choice == '2':
            create_budget()
        elif choice == '3':
            update_budget()
        elif choice == '4':
            budget_vs_actual()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in budget_management: {e}")
        print(f"An error occurred: {e}")

def view_budgets():
    """View all budgets - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*80)
        print("BUDGET OVERVIEW")
        print("="*80)

        print("\nFilter options:")
        print("1. All budgets")
        print("2. Current period budgets")
        print("3. By category")
        print("4. Over budget items")

        filter_choice = input("Choose filter (1-4): ")

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_budgets ORDER BY period_start DESC')
        elif filter_choice == '2':
            current_date = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT * FROM restaurant_budgets 
                WHERE ? BETWEEN period_start AND period_end 
                ORDER BY category
            ''', (current_date,))
        elif filter_choice == '3':
            category = input("Enter category: ")
            cursor.execute('SELECT * FROM restaurant_budgets WHERE category = ? ORDER BY period_start DESC', 
                          (category,))
        elif filter_choice == '4':
            cursor.execute('SELECT * FROM restaurant_budgets WHERE spent_amount > allocated_amount ORDER BY (spent_amount - allocated_amount) DESC')

        budgets = cursor.fetchall()

        if not budgets:
            print("No budgets found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("BUDGETS")
        print("="*120)
        print(f"{'Budget ID':<12} {'Category':<15} {'Period':<20} {'Allocated':<12} {'Spent':<12} {'Remaining':<12} {'% Used':<8}")
        print("-"*120)

        total_allocated = 0
        total_spent = 0

        for budget in budgets:
            allocated = budget[4]
            spent = budget[5]
            remaining = allocated - spent
            pct_used = (spent / allocated * 100) if allocated > 0 else 0
            period = f"{budget[2]} to {budget[3]}"

            total_allocated += allocated
            total_spent += spent

            print(f"{budget[0]:<12} {budget[1]:<15} {period:<20} £{allocated:<11.2f} £{spent:<11.2f} £{remaining:<11.2f} {pct_used:<7.1f}%")

        print("-"*120)
        print(f"{'TOTALS':<47} £{total_allocated:<11.2f} £{total_spent:<11.2f} £{total_allocated - total_spent:<11.2f}")
        print("="*120)

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_budgets: {e}")
        print(f"An error occurred: {e}")

def create_budget():
    """Create new budget - FIXED"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to create budgets.")
        return

    if not ctx.auth.check_permission('manage_finances'):
        print("You don't have permission to create budgets.")
        return

    try:
        backup_before_operation('create_budget')

        print("\n" + "="*50)
        print("CREATE NEW BUDGET")
        print("="*50)

        # Generate budget ID
        budget_id = f"BUD{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        print("Budget categories:")
        print("1. Food & Beverages")
        print("2. Staff Wages")
        print("3. Utilities")
        print("4. Rent")
        print("5. Equipment")
        print("6. Marketing")
        print("7. Maintenance")
        print("8. Other")

        category_choice = input("Choose category (1-8): ")
        categories = {
            '1': 'Food & Beverages',
            '2': 'Staff Wages',
            '3': 'Utilities',
            '4': 'Rent',
            '5': 'Equipment',
            '6': 'Marketing',
            '7': 'Maintenance'
        }

        if category_choice == '8':
            category = input("Enter custom category: ").strip()
        else:
            category = categories.get(category_choice, 'Other')

        period_start = input("Enter period start date (YYYY-MM-DD): ")
        try:
            datetime.strptime(period_start, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            return

        period_end = input("Enter period end date (YYYY-MM-DD): ")
        try:
            datetime.strptime(period_end, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            return

        try:
            allocated_amount = float(input("Enter allocated amount (£): "))
            if allocated_amount <= 0:
                raise ValueError
        except ValueError:
            print("Invalid amount.")
            return

        notes = input("Enter notes (optional): ").strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Create budget
        cursor.execute('''
            INSERT INTO restaurant_budgets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            budget_id, category, period_start, period_end, allocated_amount, 0,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ctx.auth.current_user['id'], notes
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Budget created successfully!")
        print(f"Budget ID: {budget_id}")
        print(f"Category: {category}")
        print(f"Period: {period_start} to {period_end}")
        print(f"Allocated Amount: £{allocated_amount:.2f}")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'CREATE_BUDGET',
            'restaurant_budgets',
            budget_id,
            None,
            {'category': category, 'allocated_amount': allocated_amount, 'period': f"{period_start} to {period_end}"}
        )

    except Exception as e:
        logging.error(f"Error in create_budget: {e}")
        print(f"An error occurred: {e}")

def update_budget():
    """Update existing budget - FIXED"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to update budgets.")
        return

    if not ctx.auth.check_permission('manage_finances'):
        print("You don't have permission to update budgets.")
        return

    try:
        backup_before_operation('update_budget')

        budget_id = input("Enter budget ID to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_budgets WHERE budget_id = ?', (budget_id,))
        budget = cursor.fetchone()

        if not budget:
            print("Budget not found.")
            conn.close()
            return

        print(f"\nCurrent Budget Information:")
        print(f"Category: {budget[1]}")
        print(f"Period: {budget[2]} to {budget[3]}")
        print(f"Allocated Amount: £{budget[4]:.2f}")
        print(f"Spent Amount: £{budget[5]:.2f}")

        print("\nWhat would you like to update?")
        print("1. Allocated amount")
        print("2. Period dates")
        print("3. Add expense to budget")
        print("4. Cancel")

        choice = input("Choose option (1-4): ")

        if choice == '1':
            try:
                new_amount = float(input("Enter new allocated amount (£): "))
                if new_amount <= 0:
                    raise ValueError

                cursor.execute('UPDATE restaurant_budgets SET allocated_amount = ? WHERE budget_id = ?',
                              (new_amount, budget_id))
                print("Allocated amount updated successfully.")

            except ValueError:
                print("Invalid amount.")
                conn.close()
                return

        elif choice == '2':
            new_start = input("Enter new start date (YYYY-MM-DD): ")
            new_end = input("Enter new end date (YYYY-MM-DD): ")

            try:
                datetime.strptime(new_start, '%Y-%m-%d')
                datetime.strptime(new_end, '%Y-%m-%d')

                cursor.execute('''
                    UPDATE restaurant_budgets 
                    SET period_start = ?, period_end = ? 
                    WHERE budget_id = ?
                ''', (new_start, new_end, budget_id))
                print("Period dates updated successfully.")

            except ValueError:
                print("Invalid date format.")
                conn.close()
                return

        elif choice == '3':
            try:
                expense_amount = float(input("Enter expense amount to add (£): "))
                new_spent = budget[5] + expense_amount

                cursor.execute('UPDATE restaurant_budgets SET spent_amount = ? WHERE budget_id = ?',
                              (new_spent, budget_id))
                print(f"Added £{expense_amount:.2f} to spent amount.")

            except ValueError:
                print("Invalid amount.")
                conn.close()
                return

        elif choice == '4':
            print("Update cancelled.")
            conn.close()
            return

        conn.commit()
        conn.close()

        print("✅ Budget updated successfully!")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'UPDATE_BUDGET',
            'restaurant_budgets',
            budget_id,
            None,
            {'action': choice}
        )

    except Exception as e:
        logging.error(f"Error in update_budget: {e}")
        print(f"An error occurred: {e}")

def budget_vs_actual():
    """Budget vs actual analysis - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*80)
        print("BUDGET VS ACTUAL ANALYSIS")
        print("="*80)

        # Get current period budgets
        current_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT budget_id, category, allocated_amount, spent_amount,
                   period_start, period_end
            FROM restaurant_budgets 
            WHERE ? BETWEEN period_start AND period_end
            ORDER BY category
        ''', (current_date,))

        current_budgets = cursor.fetchall()

        if not current_budgets:
            print("No active budgets found for current period.")

            # Show recent budgets instead
            cursor.execute('''
                SELECT budget_id, category, allocated_amount, spent_amount,
                       period_start, period_end
                FROM restaurant_budgets 
                ORDER BY period_start DESC
                LIMIT 10
            ''')

            current_budgets = cursor.fetchall()
            print(f"Showing most recent budgets:")

        if not current_budgets:
            print("No budgets found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("BUDGET PERFORMANCE")
        print("="*120)
        print(f"{'Category':<20} {'Allocated':<12} {'Spent':<12} {'Variance':<12} {'% Used':<8} {'Status':<15}")
        print("-"*120)

        total_allocated = 0
        total_spent = 0
        over_budget_count = 0

        for budget in current_budgets:
            allocated = budget[2]
            spent = budget[3]
            variance = spent - allocated
            pct_used = (spent / allocated * 100) if allocated > 0 else 0

            total_allocated += allocated
            total_spent += spent

            if variance > 0:
                status = "🔴 OVER BUDGET"
                over_budget_count += 1
            elif pct_used > 90:
                status = "🟡 NEAR LIMIT"
            elif pct_used > 75:
                status = "🟢 ON TRACK"
            else:
                status = "🔵 UNDER BUDGET"

            print(f"{budget[1]:<20} £{allocated:<11.2f} £{spent:<11.2f} £{variance:<11.2f} {pct_used:<7.1f}% {status:<15}")

        print("-"*120)
        total_variance = total_spent - total_allocated
        total_pct = (total_spent / total_allocated * 100) if total_allocated > 0 else 0

        print(f"{'TOTALS':<20} £{total_allocated:<11.2f} £{total_spent:<11.2f} £{total_variance:<11.2f} {total_pct:<7.1f}%")
        print("="*120)

        # Summary insights
        print(f"\nBUDGET INSIGHTS:")
        print("-"*40)
        print(f"Total Categories: {len(current_budgets)}")
        print(f"Over Budget: {over_budget_count}")
        print(f"Overall Budget Usage: {total_pct:.1f}%")

        if total_variance > 0:
            print(f"Total Overspend: £{total_variance:.2f}")
        else:
            print(f"Under Budget by: £{abs(total_variance):.2f}")

        # Recommendations
        if over_budget_count > 0:
            print(f"\n⚠️  RECOMMENDATIONS:")
            print("• Review over-budget categories immediately")
            print("• Implement cost control measures")
            print("• Consider budget reallocation if necessary")
        elif total_pct < 50:
            print(f"\n💡 RECOMMENDATIONS:")
            print("• Budget utilization is low - consider reallocating funds")
            print("• Review if budget estimates were too conservative")

        conn.close()

    except Exception as e:
        logging.error(f"Error in budget_vs_actual: {e}")
        print(f"An error occurred: {e}")
