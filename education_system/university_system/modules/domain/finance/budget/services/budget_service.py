"""
Student Budget Tracker Service

Personal finance management for students including expense tracking,
meal plan monitoring, textbook cost comparison, and financial planning.

Features:
- Personal budget planning and tracking
- Expense categorization and reporting
- Meal plan usage and balance tracking
- Textbook cost comparison across vendors
- Savings goals and financial alerts
- Income tracking (work-study, scholarships, etc.)
"""

from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.exceptions import DatabaseError, ValidationError
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

class BudgetManager:
    """Manages student budget plans and tracking"""

    @staticmethod
    def create_tables() -> None:
        """Create all required tables for budget tracking"""
        try:
            with transaction() as conn:
                # Disable foreign key enforcement temporarily
                conn.execute('PRAGMA foreign_keys = OFF')

                # Student budgets table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_budgets (
                        budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        budget_name TEXT NOT NULL,
                        budget_type TEXT CHECK(budget_type IN ('monthly', 'weekly', 'semester', 'annual', 'custom')),
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        total_income REAL DEFAULT 0.0,
                        total_budget REAL NOT NULL,
                        allocated_amount REAL DEFAULT 0.0,
                        spent_amount REAL DEFAULT 0.0,
                        is_active BOOLEAN DEFAULT 1,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Budget categories table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_budget_categories (
                        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        budget_id INTEGER NOT NULL,
                        category_name TEXT NOT NULL,
                        category_type TEXT CHECK(category_type IN ('essential', 'discretionary', 'savings', 'debt')),
                        allocated_amount REAL NOT NULL,
                        spent_amount REAL DEFAULT 0.0,
                        color_code TEXT,
                        icon TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(budget_id, category_name)
                    )
                ''')

                # Expenses table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_expenses (
                        expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        budget_id INTEGER,
                        category_id INTEGER,
                        expense_date TEXT NOT NULL,
                        amount REAL NOT NULL,
                        merchant_name TEXT,
                        description TEXT,
                        payment_method TEXT CHECK(payment_method IN ('cash', 'debit', 'credit', 'meal-plan', 'financial-aid', 'other')),
                        receipt_url TEXT,
                        is_recurring BOOLEAN DEFAULT 0,
                        recurrence_pattern TEXT,
                        tags TEXT,
                        location TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Income tracking table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_income (
                        income_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        budget_id INTEGER,
                        income_date TEXT NOT NULL,
                        amount REAL NOT NULL,
                        source TEXT NOT NULL,
                        income_type TEXT CHECK(income_type IN ('work-study', 'scholarship', 'grant', 'loan', 'family', 'job', 'investment', 'other')),
                        description TEXT,
                        is_recurring BOOLEAN DEFAULT 0,
                        recurrence_pattern TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Meal plan tracking table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS meal_plan_tracking (
                        tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        meal_plan_id INTEGER,
                        academic_term TEXT NOT NULL,
                        plan_name TEXT NOT NULL,
                        plan_type TEXT CHECK(plan_type IN ('unlimited', 'block', 'declining-balance', 'hybrid')),
                        total_meals INTEGER DEFAULT 0,
                        used_meals INTEGER DEFAULT 0,
                        total_dollars REAL DEFAULT 0.0,
                        used_dollars REAL DEFAULT 0.0,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        weekly_average_meals REAL,
                        daily_average_dollars REAL,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # NOTE: meal plan transactions now use the unified 'transactions' table
                # with source_type = 'meal_plan'

                # Textbook listings table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS textbook_listings (
                        listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        isbn TEXT NOT NULL,
                        title TEXT NOT NULL,
                        author TEXT,
                        edition TEXT,
                        publisher TEXT,
                        course_code TEXT,
                        vendor TEXT NOT NULL,
                        condition TEXT CHECK(condition IN ('new', 'like-new', 'good', 'acceptable', 'digital')),
                        price REAL NOT NULL,
                        availability TEXT CHECK(availability IN ('in-stock', 'limited', 'out-of-stock', 'pre-order')),
                        shipping_cost REAL DEFAULT 0.0,
                        rental_option BOOLEAN DEFAULT 0,
                        rental_price REAL,
                        rental_period_days INTEGER,
                        digital_option BOOLEAN DEFAULT 0,
                        digital_price REAL,
                        url TEXT,
                        last_updated TEXT DEFAULT (date('now')),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Student textbook purchases
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS student_textbook_purchases (
                        purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        listing_id INTEGER,
                        isbn TEXT NOT NULL,
                        title TEXT NOT NULL,
                        course_code TEXT,
                        purchase_date TEXT NOT NULL,
                        vendor TEXT NOT NULL,
                        purchase_type TEXT CHECK(purchase_type IN ('buy-new', 'buy-used', 'rent', 'digital')),
                        price_paid REAL NOT NULL,
                        condition TEXT,
                        rental_due_date TEXT,
                        resale_value REAL,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Savings goals table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS savings_goals (
                        goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        goal_name TEXT NOT NULL,
                        target_amount REAL NOT NULL,
                        current_amount REAL DEFAULT 0.0,
                        target_date TEXT,
                        priority TEXT CHECK(priority IN ('low', 'medium', 'high')),
                        status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled')),
                        category TEXT,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Budget alerts and notifications
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS budget_alerts (
                        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        budget_id INTEGER,
                        category_id INTEGER,
                        alert_type TEXT CHECK(alert_type IN ('overspending', 'low-balance', 'goal-milestone', 'recurring-expense', 'custom')),
                        threshold_type TEXT CHECK(threshold_type IN ('percentage', 'amount')),
                        threshold_value REAL NOT NULL,
                        message TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        last_triggered TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                log_activity('create', 'database_tables', details={'module': 'budget', 'action': 'create_tables'})

        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating budget tables: {e}") from e

    @staticmethod
    def create_budget(student_id: str, budget_name: str, budget_type: str,
                     start_date: str, end_date: str, total_budget: float,
                     categories: List[Dict[str, Any]] = None) -> int:
        """Create a new budget plan"""
        conn = None
        try:
            conn = get_connection()
            # Disable FK checks — student_id is an auth username, not necessarily in students table
            conn.execute("PRAGMA foreign_keys=OFF")
            cursor = conn.execute('''
                INSERT INTO student_budgets (
                    student_id, budget_name, budget_type, start_date, end_date, total_budget
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, budget_name, budget_type, start_date, end_date, total_budget))

            budget_id = cursor.lastrowid

            if categories:
                total_allocated = 0
                for cat in categories:
                    conn.execute('''
                        INSERT INTO student_budget_categories (
                            budget_id, category_name, category_type, allocated_amount, color_code, icon
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (budget_id, cat['name'], cat.get('type', 'discretionary'),
                          cat['amount'], cat.get('color'), cat.get('icon')))
                    total_allocated += cat['amount']

                conn.execute('''
                    UPDATE student_budgets SET allocated_amount = ? WHERE budget_id = ?
                ''', (total_allocated, budget_id))

            conn.commit()
            try:
                log_activity('create', 'student_budget', details={'budget_id': budget_id, 'student_id': student_id, 'name': budget_name})
            except Exception:
                pass
            return budget_id

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise DatabaseError(f"Error creating budget: {e}") from e
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_student_budgets(student_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all budgets for a student"""
        with get_connection() as conn:
            # Ensure table exists with correct schema
            try:
                conn.execute("SELECT budget_id FROM student_budgets LIMIT 0")
            except Exception:
                # Table may not exist or has different schema — create it
                BudgetManager.create_tables()

            query = "SELECT * FROM student_budgets WHERE student_id = ?"
            params = [student_id]

            if active_only:
                query += " AND is_active = 1"

            query += " ORDER BY start_date DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_budget_summary(budget_id: int) -> Dict[str, Any]:
        """Get detailed budget summary with spending analysis"""
        with get_connection() as conn:
            # Get budget details
            cursor = conn.execute('''
                SELECT * FROM student_budgets WHERE budget_id = ?
            ''', (budget_id,))
            budget = dict(cursor.fetchone())

            # Get categories with spending
            cursor = conn.execute('''
                SELECT * FROM student_budget_categories WHERE budget_id = ?
                ORDER BY category_type, category_name
            ''', (budget_id,))
            budget['categories'] = [dict(row) for row in cursor.fetchall()]

            # Calculate statistics
            budget['remaining_budget'] = budget['total_budget'] - budget['spent_amount']
            budget['budget_utilization_pct'] = round((budget['spent_amount'] / budget['total_budget'] * 100), 2) if budget['total_budget'] > 0 else 0

            # Days remaining
            start = datetime.strptime(budget['start_date'], '%Y-%m-%d')
            end = datetime.strptime(budget['end_date'], '%Y-%m-%d')
            today = datetime.now()
            total_days = (end - start).days
            elapsed_days = (today - start).days
            remaining_days = (end - today).days

            budget['total_days'] = total_days
            budget['elapsed_days'] = elapsed_days
            budget['remaining_days'] = remaining_days
            budget['days_progress_pct'] = round((elapsed_days / total_days * 100), 2) if total_days > 0 else 0

            # Calculate recommended daily spending
            if remaining_days > 0 and budget['remaining_budget'] > 0:
                budget['recommended_daily_spending'] = round(budget['remaining_budget'] / remaining_days, 2)
            else:
                budget['recommended_daily_spending'] = 0

            return budget

class ExpenseManager:
    """Manages expense tracking and categorization"""

    @staticmethod
    def add_expense(student_id: str, amount: float, expense_date: str,
                   description: str = "", merchant_name: str = "",
                   payment_method: str = "cash", budget_id: int = None,
                   category_id: int = None, **kwargs) -> int:
        """Record a new expense"""
        conn = None
        try:
            conn = get_connection()
            conn.execute("PRAGMA foreign_keys=OFF")
            cursor = conn.execute('''
                INSERT INTO student_expenses (
                    student_id, budget_id, category_id, expense_date, amount,
                    merchant_name, description, payment_method, receipt_url,
                    is_recurring, recurrence_pattern, tags, location, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, budget_id, category_id, expense_date, amount,
                  merchant_name, description, payment_method, kwargs.get('receipt_url'),
                  kwargs.get('is_recurring', 0), kwargs.get('recurrence_pattern'),
                  kwargs.get('tags'), kwargs.get('location'), kwargs.get('notes')))

            expense_id = cursor.lastrowid

            if budget_id:
                conn.execute('''
                    UPDATE student_budgets SET spent_amount = spent_amount + ?,
                    updated_at = CURRENT_TIMESTAMP WHERE budget_id = ?
                ''', (amount, budget_id))

            if category_id:
                conn.execute('''
                    UPDATE student_budget_categories SET spent_amount = spent_amount + ?,
                    updated_at = CURRENT_TIMESTAMP WHERE category_id = ?
                ''', (amount, category_id))

            conn.commit()
            try:
                log_activity('create', 'student_expense', details={'expense_id': expense_id, 'student_id': student_id, 'amount': amount})
            except Exception:
                pass
            return expense_id

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise DatabaseError(f"Error adding expense: {e}") from e
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_student_expenses(student_id: str, start_date: str = None,
                            end_date: str = None, category_id: int = None) -> List[Dict[str, Any]]:
        """Get expenses for a student with optional filters"""
        with get_connection() as conn:
            query = '''
                SELECT e.*, c.category_name, c.category_type
                FROM student_expenses e
                LEFT JOIN student_budget_categories c ON e.category_id = c.category_id
                WHERE e.student_id = ?
            '''
            params = [student_id]

            if start_date:
                query += " AND e.expense_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND e.expense_date <= ?"
                params.append(end_date)
            if category_id:
                query += " AND e.category_id = ?"
                params.append(category_id)

            query += " ORDER BY e.expense_date DESC, e.created_at DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_spending_by_category(student_id: str, start_date: str,
                                end_date: str) -> List[Dict[str, Any]]:
        """Get spending breakdown by category"""
        with get_connection() as conn:
            # Check if student_budget_categories table has color_code column
            try:
                conn.execute("SELECT color_code FROM student_budget_categories LIMIT 0")
                color_col = "c.color_code"
            except Exception:
                color_col = "NULL as color_code"

            cursor = conn.execute(f'''
                SELECT
                    COALESCE(c.category_name, e.merchant_name, 'Uncategorized') as category_name,
                    c.category_type,
                    {color_col},
                    COUNT(*) as transaction_count,
                    SUM(e.amount) as total_amount,
                    AVG(e.amount) as average_amount,
                    MIN(e.amount) as min_amount,
                    MAX(e.amount) as max_amount
                FROM student_expenses e
                LEFT JOIN student_budget_categories c ON e.category_id = c.category_id
                WHERE e.student_id = ? AND e.expense_date BETWEEN ? AND ?
                GROUP BY COALESCE(c.category_id, e.merchant_name)
                ORDER BY total_amount DESC
            ''', (student_id, start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_spending_trends(student_id: str, days: int = 30) -> Dict[str, Any]:
        """Analyze spending trends over time"""
        with get_connection() as conn:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # Daily spending
            cursor = conn.execute('''
                SELECT expense_date, SUM(amount) as daily_total
                FROM student_expenses
                WHERE student_id = ? AND expense_date BETWEEN ? AND ?
                GROUP BY expense_date
                ORDER BY expense_date
            ''', (student_id, start_date, end_date))
            daily_spending = [dict(row) for row in cursor.fetchall()]

            # Overall statistics
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_transactions,
                    SUM(amount) as total_spent,
                    AVG(amount) as average_transaction,
                    MIN(amount) as min_transaction,
                    MAX(amount) as max_transaction
                FROM student_expenses
                WHERE student_id = ? AND expense_date BETWEEN ? AND ?
            ''', (student_id, start_date, end_date))
            stats = dict(cursor.fetchone())

            # Calculate daily average
            stats['average_daily_spending'] = round(stats['total_spent'] / days, 2) if days > 0 else 0

            return {
                'daily_spending': daily_spending,
                'statistics': stats,
                'period_days': days,
                'start_date': start_date,
                'end_date': end_date
            }

    @staticmethod
    def update_expense(expense_id: int, **updates) -> bool:
        """Update expense details"""
        try:
            with transaction() as conn:
                allowed_fields = ['amount', 'expense_date', 'merchant_name', 'description',
                                'payment_method', 'category_id', 'receipt_url', 'tags',
                                'location', 'notes']

                update_fields = {k: v for k, v in updates.items() if k in allowed_fields}
                if not update_fields:
                    return False

                set_clause = ", ".join([validate_identifier(k, "column") + " = ?" for k in update_fields.keys()])
                set_clause += ", updated_at = CURRENT_TIMESTAMP"
                values = list(update_fields.values()) + [expense_id]

                conn.execute("UPDATE student_expenses SET " + set_clause + " WHERE expense_id = ?", values)
                log_activity('update', 'student_expense', details={'expense_id': expense_id})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error updating expense: {e}") from e

    @staticmethod
    def delete_expense(expense_id: int) -> bool:
        """Delete an expense"""
        try:
            with transaction() as conn:
                # Get expense details first
                cursor = conn.execute('''
                    SELECT amount, budget_id, category_id FROM student_expenses WHERE expense_id = ?
                ''', (expense_id,))
                expense = cursor.fetchone()
                if not expense:
                    return False

                # Update budget and category amounts
                if expense['budget_id']:
                    conn.execute('''
                        UPDATE student_budgets SET spent_amount = spent_amount - ?
                        WHERE budget_id = ?
                    ''', (expense['amount'], expense['budget_id']))

                if expense['category_id']:
                    conn.execute('''
                        UPDATE student_budget_categories SET spent_amount = spent_amount - ?
                        WHERE category_id = ?
                    ''', (expense['amount'], expense['category_id']))

                # Delete expense
                conn.execute('DELETE FROM student_expenses WHERE expense_id = ?', (expense_id,))
                log_activity('delete', 'student_expense', details={'expense_id': expense_id})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error deleting expense: {e}") from e

class IncomeManager:
    """Manages income tracking"""

    @staticmethod
    def add_income(student_id: str, amount: float, income_date: str,
                  source: str, income_type: str, budget_id: int = None,
                  description: str = "", **kwargs) -> int:
        """Record income"""
        conn = None
        try:
            conn = get_connection()
            conn.execute("PRAGMA foreign_keys=OFF")
            cursor = conn.execute('''
                INSERT INTO student_income (
                    student_id, budget_id, income_date, amount, source, income_type,
                    description, is_recurring, recurrence_pattern, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, budget_id, income_date, amount, source, income_type,
                  description, kwargs.get('is_recurring', 0),
                  kwargs.get('recurrence_pattern'), kwargs.get('notes')))

            income_id = cursor.lastrowid

            if budget_id:
                conn.execute('''
                    UPDATE student_budgets SET total_income = total_income + ?
                    WHERE budget_id = ?
                ''', (amount, budget_id))

            conn.commit()
            try:
                log_activity('create', 'student_income', details={'income_id': income_id, 'student_id': student_id, 'amount': amount})
            except Exception:
                pass
            return income_id

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise DatabaseError(f"Error adding income: {e}") from e
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_student_income(student_id: str, start_date: str = None,
                          end_date: str = None) -> List[Dict[str, Any]]:
        """Get income records for a student"""
        with get_connection() as conn:
            query = "SELECT * FROM student_income WHERE student_id = ?"
            params = [student_id]

            if start_date:
                query += " AND income_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND income_date <= ?"
                params.append(end_date)

            query += " ORDER BY income_date DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

class MealPlanManager:
    """Manages meal plan tracking and usage"""

    @staticmethod
    def create_meal_plan_tracking(student_id: str, plan_name: str, plan_type: str,
                                 academic_term: str, start_date: str, end_date: str,
                                 total_meals: int = 0, total_dollars: float = 0.0) -> int:
        """Initialize meal plan tracking"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO meal_plan_tracking (
                        student_id, academic_term, plan_name, plan_type, total_meals,
                        total_dollars, start_date, end_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, academic_term, plan_name, plan_type, total_meals,
                      total_dollars, start_date, end_date))

                tracking_id = cursor.lastrowid
                log_activity('create', 'meal_plan_tracking',
                           details={'student_id': student_id, 'plan': plan_name})
                return tracking_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating meal plan tracking: {e}") from e

    @staticmethod
    def log_meal_transaction(tracking_id: int, student_id: str, transaction_date: str,
                            transaction_time: str, location: str, meal_type: str,
                            meals_used: int = 0, dollars_used: float = 0.0,
                            description: str = "") -> int:
        """Log meal plan transaction"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO transactions (
                        source_type, reference_id, student_id, created_at, transaction_time,
                        location, transaction_type, quantity_change, amount, description
                    ) VALUES ('meal_plan', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (tracking_id, student_id, transaction_date, transaction_time,
                      location, meal_type, meals_used, dollars_used, description))

                transaction_id = cursor.lastrowid

                # Update tracking totals
                conn.execute('''
                    UPDATE meal_plan_tracking
                    SET used_meals = used_meals + ?,
                        used_dollars = used_dollars + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE tracking_id = ?
                ''', (meals_used, dollars_used, tracking_id))

                # Recalculate averages
                conn.execute('''
                    UPDATE meal_plan_tracking
                    SET weekly_average_meals = (
                        SELECT AVG(daily_meals) FROM (
                            SELECT date(created_at) as day, COUNT(*) as daily_meals
                            FROM transactions
                            WHERE source_type = 'meal_plan' AND reference_id = ?
                            GROUP BY day
                        )
                    ) * 7,
                    daily_average_dollars = (
                        SELECT AVG(daily_dollars) FROM (
                            SELECT date(created_at) as day, SUM(amount) as daily_dollars
                            FROM transactions
                            WHERE source_type = 'meal_plan' AND reference_id = ?
                            GROUP BY day
                        )
                    )
                    WHERE tracking_id = ?
                ''', (tracking_id, tracking_id, tracking_id))

                return transaction_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error logging meal transaction: {e}") from e

    @staticmethod
    def get_meal_plan_status(student_id: str, active_only: bool = True) -> Dict[str, Any]:
        """Get current meal plan status with projections"""
        with get_connection() as conn:
            query = "SELECT * FROM meal_plan_tracking WHERE student_id = ?"
            params = [student_id]

            if active_only:
                query += " AND is_active = 1"

            query += " ORDER BY start_date DESC LIMIT 1"
            cursor = conn.execute(query, params)
            plan = cursor.fetchone()

            if not plan:
                return {}

            plan_dict = dict(plan)

            # Calculate remaining
            plan_dict['remaining_meals'] = plan['total_meals'] - plan['used_meals']
            plan_dict['remaining_dollars'] = plan['total_dollars'] - plan['used_dollars']

            # Calculate usage percentages
            plan_dict['meals_used_pct'] = round((plan['used_meals'] / plan['total_meals'] * 100), 2) if plan['total_meals'] > 0 else 0
            plan_dict['dollars_used_pct'] = round((plan['used_dollars'] / plan['total_dollars'] * 100), 2) if plan['total_dollars'] > 0 else 0

            # Days remaining
            today = datetime.now()
            end_date = datetime.strptime(plan['end_date'], '%Y-%m-%d')
            days_remaining = (end_date - today).days

            start_date = datetime.strptime(plan['start_date'], '%Y-%m-%d')
            total_days = (end_date - start_date).days
            elapsed_days = (today - start_date).days

            plan_dict['days_remaining'] = days_remaining
            plan_dict['days_elapsed'] = elapsed_days
            plan_dict['total_days'] = total_days

            # Projections
            if days_remaining > 0:
                plan_dict['projected_meals_per_day'] = round(plan_dict['remaining_meals'] / days_remaining, 2)
                plan_dict['projected_dollars_per_day'] = round(plan_dict['remaining_dollars'] / days_remaining, 2)
            else:
                plan_dict['projected_meals_per_day'] = 0
                plan_dict['projected_dollars_per_day'] = 0

            # Usage pace analysis
            days_progress_pct = (elapsed_days / total_days * 100) if total_days > 0 else 0
            plan_dict['days_progress_pct'] = round(days_progress_pct, 2)

            if plan_dict['meals_used_pct'] > days_progress_pct + 10:
                plan_dict['meals_pace'] = 'fast'
            elif plan_dict['meals_used_pct'] < days_progress_pct - 10:
                plan_dict['meals_pace'] = 'slow'
            else:
                plan_dict['meals_pace'] = 'on-track'

            if plan_dict['dollars_used_pct'] > days_progress_pct + 10:
                plan_dict['dollars_pace'] = 'fast'
            elif plan_dict['dollars_used_pct'] < days_progress_pct - 10:
                plan_dict['dollars_pace'] = 'slow'
            else:
                plan_dict['dollars_pace'] = 'on-track'

            return plan_dict

    @staticmethod
    def get_meal_history(student_id: str, tracking_id: int = None,
                        days: int = 7) -> List[Dict[str, Any]]:
        """Get meal transaction history"""
        with get_connection() as conn:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            query = '''
                SELECT * FROM transactions
                WHERE source_type = 'meal_plan' AND student_id = ? AND created_at BETWEEN ? AND ?
            '''
            params = [student_id, start_date, end_date]

            if tracking_id:
                query += " AND reference_id = ?"
                params.append(tracking_id)

            query += " ORDER BY created_at DESC, transaction_time DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

class TextbookComparisonManager:
    """Manages textbook price comparison"""

    @staticmethod
    def add_textbook_listing(isbn: str, title: str, vendor: str, price: float,
                            condition: str, availability: str, **kwargs) -> int:
        """Add textbook listing"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO textbook_listings (
                        isbn, title, author, edition, publisher, course_code, vendor,
                        condition, price, availability, shipping_cost, rental_option,
                        rental_price, rental_period_days, digital_option, digital_price, url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (isbn, title, kwargs.get('author'), kwargs.get('edition'),
                      kwargs.get('publisher'), kwargs.get('course_code'), vendor,
                      condition, price, availability, kwargs.get('shipping_cost', 0.0),
                      kwargs.get('rental_option', 0), kwargs.get('rental_price'),
                      kwargs.get('rental_period_days'), kwargs.get('digital_option', 0),
                      kwargs.get('digital_price'), kwargs.get('url')))

                listing_id = cursor.lastrowid
                log_activity('create', 'textbook_listing',
                           details={'isbn': isbn, 'vendor': vendor})
                return listing_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error adding textbook listing: {e}") from e

    @staticmethod
    def compare_textbook_prices(isbn: str = None, course_code: str = None) -> List[Dict[str, Any]]:
        """Compare textbook prices across vendors"""
        with get_connection() as conn:
            # Search textbook_listings first
            query = "SELECT * FROM textbook_listings WHERE 1=1"
            params = []

            if isbn:
                query += " AND isbn = ?"
                params.append(isbn)
            if course_code:
                query += " AND course_code = ?"
                params.append(course_code)

            query += " ORDER BY price ASC"
            cursor = conn.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]

            # Also search the textbooks table
            tb_query = "SELECT * FROM textbooks WHERE 1=1"
            tb_params = []

            if isbn:
                tb_query += " AND isbn = ?"
                tb_params.append(isbn)
            if course_code:
                tb_query += " AND module_code = ?"
                tb_params.append(course_code)

            tb_query += " ORDER BY price ASC"
            cursor = conn.execute(tb_query, tb_params)
            for row in cursor.fetchall():
                row = dict(row)
                results.append({
                    'title': row['title'],
                    'vendor': row.get('publisher', 'N/A'),
                    'condition': 'new',
                    'price': row.get('price', 0.0),
                    'shipping_cost': 0.0,
                    'course_code': row.get('module_code', ''),
                    'isbn': row.get('isbn', ''),
                })

            return results

    @staticmethod
    def get_best_textbook_deals(course_code: str) -> Dict[str, Any]:
        """Get best deals for textbooks needed for a course"""
        with get_connection() as conn:
            # Get unique ISBNs for course
            cursor = conn.execute('''
                SELECT DISTINCT isbn, title FROM textbook_listings WHERE course_code = ?
            ''', (course_code,))
            books = cursor.fetchall()

            deals = []
            total_cost_new = 0
            total_cost_best = 0

            for book in books:
                isbn = book['isbn']

                # Get best price for each purchase type
                cursor = conn.execute('''
                    SELECT
                        MIN(CASE WHEN condition = 'new' THEN price + shipping_cost END) as best_new,
                        MIN(CASE WHEN condition IN ('like-new', 'good', 'acceptable') THEN price + shipping_cost END) as best_used,
                        MIN(rental_price) as best_rental,
                        MIN(digital_price) as best_digital
                    FROM textbook_listings
                    WHERE isbn = ? AND availability IN ('in-stock', 'limited')
                ''', (isbn,))
                prices = dict(cursor.fetchone())

                # Find overall best option
                options = []
                if prices['best_new']:
                    options.append(('buy-new', prices['best_new']))
                    total_cost_new += prices['best_new']
                if prices['best_used']:
                    options.append(('buy-used', prices['best_used']))
                if prices['best_rental']:
                    options.append(('rental', prices['best_rental']))
                if prices['best_digital']:
                    options.append(('digital', prices['best_digital']))

                best_option = min(options, key=lambda x: x[1]) if options else ('N/A', 0)
                total_cost_best += best_option[1]

                deals.append({
                    'isbn': isbn,
                    'title': book['title'],
                    'best_new': prices['best_new'],
                    'best_used': prices['best_used'],
                    'best_rental': prices['best_rental'],
                    'best_digital': prices['best_digital'],
                    'recommended_option': best_option[0],
                    'recommended_price': best_option[1]
                })

            return {
                'course_code': course_code,
                'books': deals,
                'total_cost_new': round(total_cost_new, 2),
                'total_cost_best_deals': round(total_cost_best, 2),
                'potential_savings': round(total_cost_new - total_cost_best, 2)
            }

    @staticmethod
    def record_textbook_purchase(student_id: str, isbn: str, title: str,
                                vendor: str, purchase_type: str, price_paid: float,
                                purchase_date: str, **kwargs) -> int:
        """Record student textbook purchase"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO student_textbook_purchases (
                        student_id, listing_id, isbn, title, course_code, purchase_date,
                        vendor, purchase_type, price_paid, condition, rental_due_date,
                        resale_value, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, kwargs.get('listing_id'), isbn, title,
                      kwargs.get('course_code'), purchase_date, vendor, purchase_type,
                      price_paid, kwargs.get('condition'), kwargs.get('rental_due_date'),
                      kwargs.get('resale_value'), kwargs.get('notes')))

                purchase_id = cursor.lastrowid
                log_activity('create', 'textbook_purchase',
                           details={'student_id': student_id, 'isbn': isbn})
                return purchase_id

        except sqlite3.Error as e:
            raise DatabaseError(f"Error recording textbook purchase: {e}") from e

    @staticmethod
    def get_student_textbooks(student_id: str) -> List[Dict[str, Any]]:
        """Get student's textbook purchases"""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM student_textbook_purchases
                WHERE student_id = ?
                ORDER BY purchase_date DESC
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]

class SavingsGoalManager:
    """Manages savings goals"""

    @staticmethod
    def create_goal(student_id: str, goal_name: str, target_amount: float,
                   target_date: str = None, priority: str = 'medium',
                   category: str = "", description: str = "") -> int:
        """Create savings goal"""
        conn = None
        try:
            conn = get_connection()
            conn.execute("PRAGMA foreign_keys=OFF")
            cursor = conn.execute('''
                INSERT INTO savings_goals (
                    student_id, goal_name, target_amount, target_date,
                    priority, category, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, goal_name, target_amount, target_date,
                  priority, category, description))

            goal_id = cursor.lastrowid
            conn.commit()
            try:
                log_activity('create', 'savings_goal', details={'goal_id': goal_id, 'student_id': student_id, 'goal': goal_name})
            except Exception:
                pass
            return goal_id

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise DatabaseError(f"Error creating savings goal: {e}") from e
        finally:
            if conn:
                conn.close()

    @staticmethod
    def update_goal_progress(goal_id: int, amount: float) -> bool:
        """Update savings goal progress"""
        try:
            with transaction() as conn:
                # Get current amount and target
                cursor = conn.execute('''
                    SELECT current_amount, target_amount FROM savings_goals WHERE goal_id = ?
                ''', (goal_id,))
                goal = cursor.fetchone()
                if not goal:
                    return False

                new_amount = goal['current_amount'] + amount

                # Update status if goal reached
                status = 'completed' if new_amount >= goal['target_amount'] else 'active'

                conn.execute('''
                    UPDATE savings_goals
                    SET current_amount = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE goal_id = ?
                ''', (new_amount, status, goal_id))

                log_activity('update', 'savings_goal',
                           details={'amount_added': amount, 'new_total': new_amount})
                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Error updating savings goal: {e}") from e

    @staticmethod
    def get_student_goals(student_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get student's savings goals"""
        with get_connection() as conn:
            query = "SELECT * FROM savings_goals WHERE student_id = ?"
            params = [student_id]

            if active_only:
                query += " AND status = 'active'"

            query += " ORDER BY priority DESC, target_date ASC"
            cursor = conn.execute(query, params)

            goals = []
            for row in cursor.fetchall():
                goal = dict(row)
                goal['progress_pct'] = round((goal['current_amount'] / goal['target_amount'] * 100), 2) if goal['target_amount'] > 0 else 0
                goal['remaining_amount'] = goal['target_amount'] - goal['current_amount']

                if goal['target_date']:
                    today = datetime.now()
                    target = datetime.strptime(goal['target_date'], '%Y-%m-%d')
                    days_remaining = (target - today).days
                    goal['days_remaining'] = days_remaining

                    if days_remaining > 0 and goal['remaining_amount'] > 0:
                        goal['required_daily_savings'] = round(goal['remaining_amount'] / days_remaining, 2)

                goals.append(goal)

            return goals

# Initialize tables on module import
try:
    BudgetManager.create_tables()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Could not create budget tables: {e}")
