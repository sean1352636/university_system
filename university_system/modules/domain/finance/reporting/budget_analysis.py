from university_system.infrastructure.database.db import sqlite3
import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
import json
import hashlib
import hmac
import requests
import smtplib
import ssl
import threading
import schedule
import time
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
from flask import Flask, request, jsonify
import qrcode
from io import BytesIO
import base64
from university_system.infrastructure.email import send_email
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.infrastructure.database.db import get_connection
from university_system.utils.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

auth = get_auth()
app = Flask(__name__)

# Initialize security headers for all responses
try:
    from university_system.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available

# Encryption key for sensitive data
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': 'pk_test_...',
        'secret_key': 'sk_test_...',
        'webhook_secret': 'whsec_...'
    },
    'paypal': {
        'client_id': 'your_paypal_client_id',
        'client_secret': 'your_paypal_client_secret',
        'environment': 'sandbox'  # or 'live'
    }
}

# Currency exchange API configuration
# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
PAYMENT_GATEWAYS = {
    'stripe': {'public_key': '', 'secret_key': '', 'webhook_secret': ''},
    'paypal': {'client_id': '', 'client_secret': '', 'environment': 'sandbox'}
}
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')



def manage_budgets():
    """Budget management system"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage budgets.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to manage budgets.")
        return
    
    while True:
        print("\n" + "=" * 50)
        print("BUDGET MANAGEMENT SYSTEM")
        print("=" * 50)
        print("1. Create New Budget Plan")
        print("2. View Budget Plans")
        print("3. Update Budget Plan")
        print("4. Budget vs Actual Analysis")
        print("5. Budget Categories Management")
        print("6. Generate Budget Reports")
        print("7. Budget Approval Workflow")
        print("8. Return to Finance Menu")
        
        choice = input("Enter your choice (1-8): ").strip()
        
        if choice == '1':
            create_budget_plan()
        elif choice == '2':
            view_budget_plans()
        elif choice == '3':
            update_budget_plan()
        elif choice == '4':
            budget_vs_actual_analysis()
        elif choice == '5':
            manage_budget_categories()
        elif choice == '6':
            generate_budget_reports()
        elif choice == '7':
            budget_approval_workflow()
        elif choice == '8':
            return
        else:
            print("Invalid choice. Please try again.")

def create_budget_plan():
    """Create a new budget plan"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCreating New Budget Plan")
        print("=" * 30)
        
        # Get budget details
        plan_name = input("Enter budget plan name: ").strip()
        if not plan_name:
            print("Budget plan name is required.")
            return
        
        # Get academic year
        current_year = datetime.now().year
        default_academic_year = f"{current_year}-{current_year+1}"
        academic_year = input(f"Enter academic year ({default_academic_year}): ").strip()
        if not academic_year:
            academic_year = default_academic_year
        
        # Get currency
        currency = input("Enter currency (GBP): ").strip().upper()
        if not currency:
            currency = 'GBP'
        
        # Create budget plan
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO budget_plans 
        (plan_name, academic_year, currency, status, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (plan_name, academic_year, currency, 'draft', 
              auth.current_user['username'], now, now))
        
        budget_id = cursor.lastrowid
        
        print(f"\nBudget plan '{plan_name}' created with ID: {budget_id}")
        
        # Add budget line items
        add_budget_line_items(budget_id)
        
        conn.commit()
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def add_budget_line_items(budget_id):
    """Add line items to a budget plan"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get budget categories
        cursor.execute('''
        SELECT category_id, category_name, category_type, parent_category_id
        FROM budget_categories
        WHERE is_active = 1
        ORDER BY category_type, category_name
        ''')
        
        categories = cursor.fetchall()
        
        if not categories:
            print("No budget categories available. Please create categories first.")
            return
        
        print(f"\nAdding line items to budget plan...")
        print("Available categories:")
        
        revenue_categories = [c for c in categories if c[2] == 'revenue']
        expense_categories = [c for c in categories if c[2] == 'expense']
        
        print("\nRevenue Categories:")
        for i, (cat_id, cat_name, cat_type, parent_id) in enumerate(revenue_categories, 1):
            print(f"  R{i}. {cat_name}")
        
        print("\nExpense Categories:")
        for i, (cat_id, cat_name, cat_type, parent_id) in enumerate(expense_categories, 1):
            print(f"  E{i}. {cat_name}")
        
        total_revenue_budget = 0
        total_expense_budget = 0
        
        while True:
            print(f"\nCurrent totals - Revenue: £{total_revenue_budget:.2f}, Expenses: £{total_expense_budget:.2f}")
            
            category_choice = input("Enter category (R1, E1, etc.) or 'done' to finish: ").strip().upper()
            
            if category_choice == 'DONE':
                break
            
            # Parse category choice
            if category_choice.startswith('R'):
                try:
                    index = int(category_choice[1:]) - 1
                    if 0 <= index < len(revenue_categories):
                        selected_category = revenue_categories[index]
                    else:
                        print("Invalid revenue category selection.")
                        continue
                except ValueError:
                    print("Invalid format. Use R1, R2, etc.")
                    continue
            elif category_choice.startswith('E'):
                try:
                    index = int(category_choice[1:]) - 1
                    if 0 <= index < len(expense_categories):
                        selected_category = expense_categories[index]
                    else:
                        print("Invalid expense category selection.")
                        continue
                except ValueError:
                    print("Invalid format. Use E1, E2, etc.")
                    continue
            else:
                print("Invalid format. Use R1 for revenue or E1 for expense categories.")
                continue
            
            category_id, category_name, category_type = selected_category[0], selected_category[1], selected_category[2]
            
            # Get budgeted amount
            while True:
                try:
                    amount = float(input(f"Enter budgeted amount for {category_name}: £"))
                    if amount < 0:
                        print("Amount cannot be negative.")
                        continue
                    break
                except ValueError:
                    print("Invalid input. Please enter a valid amount.")
            
            # Get notes
            notes = input("Enter notes (optional): ").strip()
            
            # Insert line item
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO budget_line_items 
            (budget_id, category_id, budgeted_amount, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (budget_id, category_id, amount, notes, now, now))
            
            print(f"Added {category_name}: £{amount:.2f}")
            
            # Update totals
            if category_type == 'revenue':
                total_revenue_budget += amount
            else:
                total_expense_budget += amount
        
        # Update budget plan totals
        cursor.execute('''
        UPDATE budget_plans 
        SET total_revenue_budget = ?, total_expense_budget = ?, updated_at = ?
        WHERE budget_id = ?
        ''', (total_revenue_budget, total_expense_budget, 
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), budget_id))
        
        print(f"\nBudget plan completed!")
        print(f"Total Revenue Budget: £{total_revenue_budget:.2f}")
        print(f"Total Expense Budget: £{total_expense_budget:.2f}")
        print(f"Net Budget: £{total_revenue_budget - total_expense_budget:.2f}")
        
        conn.commit()
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_budget_plans():
    """View all budget plans"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT budget_id, plan_name, academic_year, currency, status,
               total_revenue_budget, total_expense_budget, created_by, created_at
        FROM budget_plans
        ORDER BY created_at DESC
        ''')
        
        plans = cursor.fetchall()
        
        if not plans:
            print("No budget plans found.")
            conn.close()
            return
        
        print(f"\nBudget Plans:")
        print("=" * 120)
        print(f"{'ID':<5} {'Plan Name':<25} {'Academic Year':<15} {'Status':<10} {'Revenue':<12} {'Expenses':<12} {'Net':<12} {'Created By':<15}")
        print("-" * 120)
        
        for plan in plans:
            budget_id, plan_name, academic_year, currency, status, revenue, expenses, created_by, created_at = plan
            net_budget = (revenue or 0) - (expenses or 0)
            
            print(f"{budget_id:<5} {plan_name:<25} {academic_year:<15} {status:<10} £{revenue or 0:<11.2f} £{expenses or 0:<11.2f} £{net_budget:<11.2f} {created_by:<15}")
        
        print("=" * 120)
        
        # Detailed view option
        view_detail = input("\nView detailed budget plan? Enter Budget ID (or press Enter to skip): ").strip()
        
        if view_detail:
            view_budget_plan_detail(view_detail)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_budget_plan_detail(budget_id):
    """View detailed budget plan information"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get budget plan info
        cursor.execute('''
        SELECT plan_name, academic_year, currency, status, 
               total_revenue_budget, total_expense_budget, created_by, created_at
        FROM budget_plans
        WHERE budget_id = ?
        ''', (budget_id,))
        
        plan = cursor.fetchone()
        
        if not plan:
            print(f"Budget plan {budget_id} not found.")
            return
        
        plan_name, academic_year, currency, status, revenue_budget, expense_budget, created_by, created_at = plan
        
        print(f"\nBudget Plan Details - ID: {budget_id}")
        print("=" * 50)
        print(f"Plan Name: {plan_name}")
        print(f"Academic Year: {academic_year}")
        print(f"Currency: {currency}")
        print(f"Status: {status}")
        print(f"Created By: {created_by}")
        print(f"Created: {created_at}")
        print(f"\nTotals:")
        print(f"Revenue Budget: £{revenue_budget or 0:.2f}")
        print(f"Expense Budget: £{expense_budget or 0:.2f}")
        print(f"Net Budget: £{(revenue_budget or 0) - (expense_budget or 0):.2f}")
        
        # Get line items
        cursor.execute('''
        SELECT bc.category_name, bc.category_type, bli.budgeted_amount, 
               bli.actual_amount, bli.variance, bli.notes
        FROM budget_line_items bli
        JOIN budget_categories bc ON bli.category_id = bc.category_id
        WHERE bli.budget_id = ?
        ORDER BY bc.category_type, bc.category_name
        ''')
        
        line_items = cursor.fetchall()
        
        if line_items:
            print(f"\nLine Items:")
            print("-" * 80)
            print(f"{'Category':<30} {'Type':<8} {'Budget':<12} {'Actual':<12} {'Variance':<12}")
            print("-" * 80)
            
            for item in line_items:
                category, cat_type, budgeted, actual, variance, notes = item
                
                print(f"{category:<30} {cat_type:<8} £{budgeted:<11.2f} £{actual or 0:<11.2f} £{variance or 0:<11.2f}")
            
            print("-" * 80)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def update_budget_plan():
    """Update an existing budget plan"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get budget ID
        budget_id = input("Enter budget plan ID to update: ").strip()
        
        # Get budget details
        cursor.execute('''
        SELECT plan_name, academic_year, status, total_revenue_budget, total_expense_budget
        FROM budget_plans
        WHERE budget_id = ?
        ''', (budget_id,))
        
        budget = cursor.fetchone()
        
        if not budget:
            print("Budget plan not found.")
            return
        
        plan_name, academic_year, status, revenue_budget, expense_budget = budget
        
        print(f"\nUpdating Budget Plan: {plan_name} ({academic_year})")
        print(f"Current Status: {status}")
        print(f"Revenue Budget: £{revenue_budget or 0:.2f}")
        print(f"Expense Budget: £{expense_budget or 0:.2f}")
        
        print("\nUpdate Options:")
        print("1. Update plan details")
        print("2. Update line items")
        print("3. Change status")
        print("4. Update actual amounts")
        
        choice = input("Select option (1-4): ").strip()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if choice == '1':
            # Update plan details
            new_name = input(f"Enter new plan name (current: {plan_name}): ").strip()
            if not new_name:
                new_name = plan_name
            
            cursor.execute('''
            UPDATE budget_plans 
            SET plan_name = ?, updated_at = ?
            WHERE budget_id = ?
            ''', (new_name, now, budget_id))
            
            print("Plan details updated")
            
        elif choice == '2':
            # Update line items
            update_budget_line_items(budget_id)
            
        elif choice == '3':
            # Change status
            statuses = ['draft', 'approved', 'active', 'closed']
            print("Available statuses:")
            for i, stat in enumerate(statuses, 1):
                print(f"{i}. {stat.title()}")
            
            status_choice = input("Select new status (1-4): ").strip()
            try:
                status_index = int(status_choice) - 1
                if 0 <= status_index < len(statuses):
                    new_status = statuses[status_index]
                    
                    cursor.execute('''
                    UPDATE budget_plans 
                    SET status = ?, updated_at = ?
                    WHERE budget_id = ?
                    ''', (new_status, now, budget_id))
                    
                    print(f"Status updated to {new_status}")
            except ValueError:
                print("Invalid selection")
                
        elif choice == '4':
            # Update actual amounts
            update_actual_amounts(budget_id)
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error updating budget plan: {e}")

def update_budget_line_items(budget_id):
    """Update budget line items"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current line items
        cursor.execute('''
        SELECT bli.line_item_id, bc.category_name, bli.budgeted_amount, bli.actual_amount
        FROM budget_line_items bli
        JOIN budget_categories bc ON bli.category_id = bc.category_id
        WHERE bli.budget_id = ?
        ORDER BY bc.category_type, bc.category_name
        ''', (budget_id,))
        
        line_items = cursor.fetchall()
        
        if not line_items:
            print("No line items found for this budget.")
            return
        
        print(f"\nCurrent Line Items:")
        for i, (item_id, category_name, budgeted, actual) in enumerate(line_items, 1):
            print(f"{i}. {category_name}: Budgeted £{budgeted:.2f}, Actual £{actual or 0:.2f}")
        
        item_choice = input(f"Select line item to update (1-{len(line_items)}): ").strip()
        try:
            item_index = int(item_choice) - 1
            if 0 <= item_index < len(line_items):
                selected_item = line_items[item_index]
                item_id = selected_item[0]
                category_name = selected_item[1]
                current_budgeted = selected_item[2]
            else:
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return
        
        print(f"\nUpdating {category_name}")
        print(f"Current budgeted amount: £{current_budgeted:.2f}")
        
        new_amount = input("Enter new budgeted amount: £").strip()
        try:
            new_budgeted = float(new_amount)
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            UPDATE budget_line_items 
            SET budgeted_amount = ?, updated_at = ?
            WHERE line_item_id = ?
            ''', (new_budgeted, now, item_id))
            
            print(f"Line item updated: {category_name} = £{new_budgeted:.2f}")
            
            # Recalculate budget totals
            recalculate_budget_totals(budget_id)
            
        except ValueError:
            print("Invalid amount entered.")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error updating line items: {e}")

def recalculate_budget_totals(budget_id):
    """Recalculate budget plan totals"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Calculate revenue total
        cursor.execute('''
        SELECT SUM(bli.budgeted_amount)
        FROM budget_line_items bli
        JOIN budget_categories bc ON bli.category_id = bc.category_id
        WHERE bli.budget_id = ? AND bc.category_type = 'revenue'
        ''', (budget_id,))
        
        revenue_total = cursor.fetchone()[0] or 0
        
        # Calculate expense total
        cursor.execute('''
        SELECT SUM(bli.budgeted_amount)
        FROM budget_line_items bli
        JOIN budget_categories bc ON bli.category_id = bc.category_id
        WHERE bli.budget_id = ? AND bc.category_type = 'expense'
        ''', (budget_id,))
        
        expense_total = cursor.fetchone()[0] or 0
        
        # Update budget plan
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE budget_plans 
        SET total_revenue_budget = ?, total_expense_budget = ?, updated_at = ?
        WHERE budget_id = ?
        ''', (revenue_total, expense_total, now, budget_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error recalculating budget totals: {e}")

def budget_vs_actual_analysis():
    """Analyze budget vs actual performance"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get budget ID
        budget_id = input("Enter budget plan ID for analysis: ").strip()
        
        # Get budget plan details
        cursor.execute('''
        SELECT plan_name, academic_year, total_revenue_budget, total_expense_budget
        FROM budget_plans
        WHERE budget_id = ?
        ''', (budget_id,))
        
        budget = cursor.fetchone()
        
        if not budget:
            print("Budget plan not found.")
            return
        
        plan_name, academic_year, revenue_budget, expense_budget = budget
        
        # Get line item analysis
        cursor.execute('''
        SELECT bc.category_name, bc.category_type, bli.budgeted_amount, 
               bli.actual_amount, bli.variance
        FROM budget_line_items bli
        JOIN budget_categories bc ON bli.category_id = bc.category_id
        WHERE bli.budget_id = ?
        ORDER BY bc.category_type, ABS(bli.variance) DESC
        ''')
        
        line_items = cursor.fetchall()
        
        print(f"\nBudget vs Actual Analysis: {plan_name} ({academic_year})")
        print("=" * 100)
        print(f"{'Category':<30} {'Type':<8} {'Budget':<12} {'Actual':<12} {'Variance':<12} {'% Variance':<12}")
        print("-" * 100)
        
        total_revenue_actual = 0
        total_expense_actual = 0
        total_revenue_variance = 0
        total_expense_variance = 0
        
        for item in line_items:
            category, cat_type, budgeted, actual, variance = item
            actual = actual or 0
            variance = variance or (actual - budgeted)
            
            if budgeted != 0:
                percent_variance = (variance / budgeted) * 100
            else:
                percent_variance = 0
            
            print(f"{category:<30} {cat_type:<8} £{budgeted:<11.2f} £{actual:<11.2f} £{variance:<11.2f} {percent_variance:>10.1f}%")
            
            if cat_type == 'revenue':
                total_revenue_actual += actual
                total_revenue_variance += variance
            else:
                total_expense_actual += actual
                total_expense_variance += variance
        
        print("-" * 100)
        print(f"{'REVENUE TOTALS':<30} {'Total':<8} £{revenue_budget or 0:<11.2f} £{total_revenue_actual:<11.2f} £{total_revenue_variance:<11.2f}")
        print(f"{'EXPENSE TOTALS':<30} {'Total':<8} £{expense_budget or 0:<11.2f} £{total_expense_actual:<11.2f} £{total_expense_variance:<11.2f}")
        
        net_budget = (revenue_budget or 0) - (expense_budget or 0)
        net_actual = total_revenue_actual - total_expense_actual
        net_variance = net_actual - net_budget
        
        print(f"{'NET TOTALS':<30} {'Net':<8} £{net_budget:<11.2f} £{net_actual:<11.2f} £{net_variance:<11.2f}")
        print("=" * 100)
        
        # Performance summary
        revenue_performance = (total_revenue_actual / (revenue_budget or 1)) * 100
        expense_performance = (total_expense_actual / (expense_budget or 1)) * 100
        
        print(f"\nPerformance Summary:")
        print(f"Revenue Performance: {revenue_performance:.1f}% of budget")
        print(f"Expense Performance: {expense_performance:.1f}% of budget")
        
        if net_variance > 0:
            print(f"Budget Status: £{net_variance:.2f} over budget")
        elif net_variance < 0:
            print(f"Budget Status: £{abs(net_variance):.2f} under budget")
        else:
            print("Budget Status: On target")
        
        conn.close()
        
    except Exception as e:
        print(f"Error in budget vs actual analysis: {e}")

def manage_budget_categories():
    """Manage budget categories"""
    while True:
        print("\n" + "=" * 40)
        print("BUDGET CATEGORIES MANAGEMENT")
        print("=" * 40)
        print("1. View Categories")
        print("2. Create New Category")
        print("3. Edit Category")
        print("4. Deactivate Category")
        print("5. Return to Budget Menu")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            view_budget_categories()
        elif choice == '2':
            create_budget_category()
        elif choice == '3':
            edit_budget_category()
        elif choice == '4':
            deactivate_budget_category()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

def view_budget_categories():
    """View all budget categories"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT bc.category_id, bc.category_name, bc.category_type, 
               pc.category_name as parent_name, bc.is_active
        FROM budget_categories bc
        LEFT JOIN budget_categories pc ON bc.parent_category_id = pc.category_id
        ORDER BY bc.category_type, bc.category_name
        ''')
        
        categories = cursor.fetchall()
        
        if not categories:
            print("No budget categories found.")
            return
        
        print(f"\nBudget Categories:")
        print("=" * 80)
        print(f"{'ID':<5} {'Name':<30} {'Type':<10} {'Parent':<20} {'Active':<8}")
        print("-" * 80)
        
        for category in categories:
            cat_id, name, cat_type, parent_name, active = category
            parent_str = parent_name if parent_name else "None"
            active_str = "Yes" if active else "No"
            
            print(f"{cat_id:<5} {name:<30} {cat_type:<10} {parent_str:<20} {active_str:<8}")
        
        print("=" * 80)
        conn.close()
        
    except Exception as e:
        print(f"Error viewing budget categories: {e}")

def create_budget_category():
    """Create a new budget category - COMPLETE IMPLEMENTATION"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCreating New Budget Category:")
        
        category_name = input("Enter category name: ").strip()
        if not category_name:
            print("Category name is required.")
            conn.close()
            return
        
        # Select category type
        types = ['revenue', 'expense']
        print("\nCategory types:")
        for i, cat_type in enumerate(types, 1):
            print(f"{i}. {cat_type.title()}")
        
        type_choice = input("Select type (1-2): ").strip()
        try:
            type_index = int(type_choice) - 1
            if 0 <= type_index < len(types):
                category_type = types[type_index]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
        
        # Optional parent category
        cursor.execute('''
        SELECT category_id, category_name 
        FROM budget_categories 
        WHERE category_type = ? AND is_active = 1
        ''', (category_type,))
        
        potential_parents = cursor.fetchall()
        
        parent_category_id = None
        if potential_parents:
            print("\nParent categories (optional):")
            print("0. None (top-level category)")
            for i, (pid, pname) in enumerate(potential_parents, 1):
                print(f"{i}. {pname}")
            
            parent_choice = input("Select parent category (0 for none): ").strip()
            try:
                parent_index = int(parent_choice)
                if parent_index > 0 and parent_index <= len(potential_parents):
                    parent_category_id = potential_parents[parent_index - 1][0]
                elif parent_index == 0:
                    parent_category_id = None
                else:
                    print("Invalid selection, creating as top-level category.")
            except ValueError:
                print("Invalid input, creating as top-level category.")
        
        # Get optional description
        description = input("Enter category description (optional): ").strip()
        
        # CREATE THE CATEGORY IN DATABASE
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO budget_categories 
        (category_name, category_type, parent_category_id, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (category_name, category_type, parent_category_id, 1, now, now))
        
        category_id = cursor.lastrowid
        
        conn.commit()
        
        print(f"\n✅ Budget category created successfully!")
        print(f"Category ID: {category_id}")
        print(f"Name: {category_name}")
        print(f"Type: {category_type.title()}")
        if parent_category_id:
            parent_name = next((name for pid, name in potential_parents if pid == parent_category_id), "Unknown")
            print(f"Parent Category: {parent_name}")
        else:
            print("Parent Category: None (top-level)")
        print(f"Created: {now}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error creating budget category: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"❌ Error creating budget category: {e}")
        if 'conn' in locals():
            conn.close()

def edit_budget_category():
    """Edit an existing budget category"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        category_id = input("Enter category ID to edit: ").strip()
        
        cursor.execute('''
        SELECT category_name, category_type, is_active
        FROM budget_categories
        WHERE category_id = ?
        ''', (category_id,))
        
        category = cursor.fetchone()
        
        if not category:
            print("Category not found.")
            return
        
        current_name, cat_type, is_active = category
        
        print(f"\nEditing Category {category_id}:")
        print(f"Current name: {current_name}")
        
        new_name = input(f"Enter new name (or press Enter to keep '{current_name}'): ").strip()
        if not new_name:
            new_name = current_name
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE budget_categories 
        SET category_name = ?, updated_at = ?
        WHERE category_id = ?
        ''', (new_name, now, category_id))
        
        conn.commit()
        
        print(f"Category {category_id} updated successfully!")
        
        conn.close()
        
    except Exception as e:
        print(f"Error editing budget category: {e}")

def deactivate_budget_category():
    """Deactivate a budget category"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        category_id = input("Enter category ID to deactivate: ").strip()
        
        cursor.execute('''
        SELECT category_name FROM budget_categories
        WHERE category_id = ? AND is_active = 1
        ''', (category_id,))
        
        category = cursor.fetchone()
        
        if not category:
            print("Category not found or already inactive.")
            return
        
        confirm = input(f"Deactivate category '{category[0]}'? (y/n): ").strip().lower()
        if confirm != 'y':
            return
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE budget_categories 
        SET is_active = 0, updated_at = ?
        WHERE category_id = ?
        ''', (now, category_id))
        
        conn.commit()
        
        print(f"Category '{category[0]}' deactivated successfully!")
        
        conn.close()
        
    except Exception as e:
        print(f"Error deactivating budget category: {e}")

def budget_performance_trends():
    """Generate budget performance trends report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT bp.academic_year, 
               SUM(bp.total_revenue_budget) as total_revenue_budget,
               SUM(bp.total_expense_budget) as total_expense_budget,
               COUNT(*) as budget_count
        FROM budget_plans bp
        WHERE bp.status IN ('active', 'closed')
        GROUP BY bp.academic_year
        ORDER BY bp.academic_year
        ''')
        
        trends = cursor.fetchall()
        
        if not trends:
            print("No budget trend data found.")
            return
        
        print(f"\nBudget Performance Trends:")
        print("=" * 80)
        print(f"{'Academic Year':<15} {'Revenue Budget':<15} {'Expense Budget':<15} {'Net Budget':<15} {'Plans':<6}")
        print("-" * 80)
        
        for trend in trends:
            academic_year, revenue, expenses, count = trend
            net = revenue - expenses
            
            print(f"{academic_year:<15} £{revenue:<14,.0f} £{expenses:<14,.0f} £{net:<14,.0f} {count:<6}")
        
        print("=" * 80)
        
        # Calculate year-over-year growth
        if len(trends) > 1:
            print("\nYear-over-Year Growth:")
            for i in range(1, len(trends)):
                prev_year, prev_revenue, prev_expenses, _ = trends[i-1]
                curr_year, curr_revenue, curr_expenses, _ = trends[i]
                
                revenue_growth = ((curr_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
                expense_growth = ((curr_expenses - prev_expenses) / prev_expenses * 100) if prev_expenses > 0 else 0
                
                print(f"{curr_year}: Revenue {revenue_growth:+.1f}%, Expenses {expense_growth:+.1f}%")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating budget performance trends: {e}")
