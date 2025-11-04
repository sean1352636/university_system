from university_system.infrastructure.auth.user_authentication import UserAuth, display_auth_menu
from university_system.infrastructure.database.data_backup import display_backup_menu, backup_before_operation
from university_system.modules.core.services.restaurant_menu_management import display_customer_menu
from university_system.modules.core.services.restaurant_tables_reservations_qr import display_table_management
from university_system.modules.core.services.restaurant_staff_management import display_staff_management
from university_system.modules.core.services.restaurant_inventory_supply import display_inventory_management
from university_system.modules.core.services.restaurant_finance_reports import display_financial_reports
from university_system.modules.core.services.restaurant_misc import display_system_settings
from university_system.infrastructure.database.data_backup import display_backup_menu
from university_system.infrastructure.email import send_confirmation_email
from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import random
import re
import os
import csv
import pandas as pd
import json
import hashlib
import logging
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import qrcode
from PIL import Image
import matplotlib.pyplot as plt
from decimal import Decimal, ROUND_HALF_UP
import threading
import time
from collections import defaultdict
import warnings
from university_system.utils.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
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
from university_system.modules.core.services.restaurant_menu_management import display_orders_menu
from university_system.modules.core.services.restaurant_menu_management  import display_menu_items_menu, view_all_menu_items, create_menu_item, update_menu_item, delete_menu_item, menu_analytics 
from university_system.modules.core.services.restaurant_orders_payments  import view_orders, view_order_details, add_tip, refund_order, update_order_status, process_payments, process_cash_payment, process_card_payment, process_meal_plan_payment, apply_discount, manage_purchase_orders, view_purchase_orders, create_purchase_order, update_purchase_order, receive_purchase_order, purchase_order_reports
from university_system.modules.core.services.restaurant_customers_loyalty_feedback  import create_customer, view_customers, view_customer_details, update_customer, manage_customer_feedback, view_recent_feedback, respond_to_feedback, export_feedback_report, manage_loyalty_program, view_loyalty_tiers, update_loyalty_points, promote_customer_tier, award_bonus_points, export_feedback_report_pdf
from university_system.modules.core.services.restaurant_tables_reservations_qr  import display_table_management, view_all_tables, add_new_table, update_table, delete_table, view_table_reservations, create_reservation, cancel_reservation, generate_qr_codes, create_qr_code_image, create_enhanced_qr_image, update_qr_database_record, print_qr_codes, scan_qr_code_usage, optimize_table_structure
from university_system.modules.core.services.restaurant_staff_management  import display_staff_management, view_all_staff, add_new_staff, update_staff_info, delete_staff, manage_staff_schedules, view_staff_schedules, supplier_performance, create_staff_schedule, update_staff_schedule, delete_staff_schedule, view_schedule_conflicts, staff_performance, view_performance_rankings, update_performance_scores, export_performance_report, analyze_query_performance
from university_system.modules.core.services.restaurant_inventory_supply  import manage_suppliers, view_all_suppliers, add_new_supplier, update_supplier, waste_tracking, record_waste, view_waste_reports, inventory_reports, inventory_valuation_report, stock_movement_report, low_stock_report, expiry_report, abc_analysis, display_inventory_management, view_inventory, add_inventory_item, update_stock_levels, low_stock_alerts, inventory_transactions
from university_system.modules.core.services.restaurant_finance_reports  import display_financial_reports, daily_sales_report, export_payroll_report, monthly_financial_summary, export_expense_report, tax_reports, generate_vat_report, generate_sales_tax_summary, financial_forecasting, export_financial_data, export_complete_financial_data, export_sales_data
from university_system.modules.core.services.restaurant_misc  import log_audit_action, main, payroll_calculations, calculate_weekly_payroll, calculate_monthly_payroll, calculate_individual_payroll, profit_loss_statement, expense_tracking, add_expense, user_management, view_user_activity_logs, system_maintenance, database_cleanup, clear_old_logs, reset_system_counters, rebuild_indexes, system_health_check, clear_cache, view_audit_logs, manage_notifications, view_notifications, create_notification, mark_notification_read, clear_old_notifications, system_backup, backup_database, backup_full_system, database_optimization, update_statistics, defragment_database, view_expenses, budget_management, view_budgets, create_budget, update_budget, budget_vs_actual, generate_employee_tax_summary, generate_annual_tax_summary, export_tax_data, revenue_forecast, expense_forecast, cash_flow_projection, seasonal_analysis, growth_projections, export_expense_data, export_profit_loss_data, display_system_settings, view_system_settings, update_system_settings
from university_system.modules.core.services.restaurant_misc import get_db_connection


def set_auth(auth_instance):
    global auth
    auth = auth_instance

def get_db_connection():
    """Get database connection using the consolidated database file"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        print(f"Database connection error: {e}")
        return None

def safe_db_operation(operation_func, *args, **kwargs):
    """Wrapper for safe database operations with error handling"""
    try:
        return operation_func(*args, **kwargs)
    except sqlite3.Error as e:
        logging.error(f"Database error in {operation_func.__name__}: {e}")
        print(f"Database error: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in {operation_func.__name__}: {e}")
        print(f"An unexpected error occurred: {e}")
        return None

def init_db():
    """Initialize the enhanced restaurant database restaurant_tables in the consolidated database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Enable foreign key constraints
        cursor.execute('PRAGMA foreign_keys = ON')

        # Original restaurant_tables (enhanced)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu_items (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            allergens TEXT,
            vegetarian INTEGER DEFAULT 0,
            vegan INTEGER DEFAULT 0,
            available INTEGER DEFAULT 1,
            creation_date TEXT,
            calories INTEGER,
            protein REAL,
            carbs REAL,
            fat REAL,
            prep_time INTEGER,
            cost_price REAL,
            image_path TEXT,
            popularity_score INTEGER DEFAULT 0
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            table_id TEXT,
            order_time TEXT NOT NULL,
            total_price REAL NOT NULL,
            status TEXT NOT NULL,
            payment_method TEXT,
            order_type TEXT DEFAULT 'dine_in',
            estimated_time INTEGER,
            actual_time INTEGER,
            rating INTEGER,
            feedback TEXT,
            discount_applied REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            tip_amount REAL DEFAULT 0,
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers (customer_id),
            FOREIGN KEY (table_id) REFERENCES restaurant_tables (table_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            special_instructions TEXT,
            FOREIGN KEY (order_id) REFERENCES restaurant_orders (order_id),
            FOREIGN KEY (item_id) REFERENCES menu_items (item_id)
        )
        ''')

        # Customer Management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            dietary_restrictions TEXT,
            loyalty_points INTEGER DEFAULT 0,
            loyalty_tier TEXT DEFAULT 'Bronze',
            birthday TEXT,
            registration_date TEXT,
            last_visit TEXT,
            total_spent REAL DEFAULT 0,
            visit_count INTEGER DEFAULT 0,
            preferences TEXT,
            address TEXT,
            emergency_contact TEXT,
            notes TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_customer_favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            last_ordered TEXT,
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers (customer_id),
            FOREIGN KEY (item_id) REFERENCES menu_items (item_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_customer_feedback (
            feedback_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            order_id TEXT,
            item_id TEXT,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            feedback_text TEXT,
            feedback_date TEXT,
            response_text TEXT,
            response_date TEXT,
            category TEXT,
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers (customer_id),
            FOREIGN KEY (order_id) REFERENCES restaurant_orders (order_id),
            FOREIGN KEY (item_id) REFERENCES menu_items (item_id)
        )
        ''')

        # Table Management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_tables (
            table_id TEXT PRIMARY KEY,
            capacity INTEGER NOT NULL,
            status TEXT DEFAULT 'Available',
            current_order_id TEXT,
            location TEXT,
            table_type TEXT,
            last_cleaned TEXT,
            FOREIGN KEY (current_order_id) REFERENCES restaurant_orders (order_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_reservations (
            reservation_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            table_id TEXT NOT NULL,
            reservation_date TEXT NOT NULL,
            reservation_time TEXT NOT NULL,
            party_size INTEGER NOT NULL,
            status TEXT DEFAULT 'Active',
            special_requests TEXT,
            created_date TEXT,
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers (customer_id),
            FOREIGN KEY (table_id) REFERENCES restaurant_tables (table_id)
        )
        ''')

        # Staff Management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_staff (
            staff_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            hourly_rate REAL,
            email TEXT,
            phone TEXT,
            hire_date TEXT,
            status TEXT DEFAULT 'Active',
            emergency_contact TEXT,
            address TEXT,
            performance_score REAL DEFAULT 0
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_staff_schedules (
            schedule_id TEXT PRIMARY KEY,
            staff_id TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            break_duration INTEGER DEFAULT 30,
            status TEXT DEFAULT 'Scheduled',
            actual_start TEXT,
            actual_end TEXT,
            FOREIGN KEY (staff_id) REFERENCES restaurant_staff (staff_id)
        )
        ''')

        # Supplier Management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            rating REAL DEFAULT 0,
            payment_terms TEXT,
            delivery_schedule TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Active'
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_purchase_orders (
            po_id TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            order_date TEXT NOT NULL,
            expected_delivery TEXT,
            actual_delivery TEXT,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'Pending',
            notes TEXT,
            created_by TEXT,
            FOREIGN KEY (supplier_id) REFERENCES restaurant_suppliers (supplier_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            unit_cost REAL NOT NULL,
            total_cost REAL NOT NULL,
            received_quantity REAL DEFAULT 0,
            FOREIGN KEY (po_id) REFERENCES restaurant_purchase_orders (po_id)
        )
        ''')

        # Enhanced Inventory
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_inventory (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            cost_per_unit REAL DEFAULT 0,
            reorder_level REAL DEFAULT 0,
            max_level REAL DEFAULT 0,
            supplier_id TEXT,
            category TEXT,
            expiry_date TEXT,
            batch_number TEXT,
            last_updated TEXT,
            location TEXT,
            temperature_req TEXT,
            FOREIGN KEY (supplier_id) REFERENCES restaurant_suppliers (supplier_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_inventory_transactions (
            transaction_id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_cost REAL,
            reference_id TEXT,
            transaction_date TEXT,
            notes TEXT,
            performed_by TEXT,
            FOREIGN KEY (item_id) REFERENCES restaurant_inventory (item_id)
        )
        ''')

        # Financial Management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_expenses (
            expense_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date TEXT NOT NULL,
            payment_method TEXT,
            vendor TEXT,
            receipt_path TEXT,
            created_by TEXT,
            status TEXT DEFAULT 'Pending',
            approval_date TEXT,
            approved_by TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_budgets (
            budget_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            allocated_amount REAL NOT NULL,
            spent_amount REAL DEFAULT 0,
            created_date TEXT,
            created_by TEXT,
            notes TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_daily_sales (
            date TEXT PRIMARY KEY,
            total_revenue REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            avg_order_value REAL DEFAULT 0,
            cash_sales REAL DEFAULT 0,
            card_sales REAL DEFAULT 0,
            meal_plan_sales REAL DEFAULT 0,
            total_costs REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            customer_count INTEGER DEFAULT 0
        )
        ''')

        # Enhanced Special Offers
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_special_offers (
            offer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            discount_type TEXT DEFAULT 'percentage',
            discount_value REAL NOT NULL,
            min_order_amount REAL DEFAULT 0,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            applicable_items TEXT,
            max_uses INTEGER DEFAULT -1,
            uses_count INTEGER DEFAULT 0,
            applicable_days TEXT,
            applicable_times TEXT,
            customer_type TEXT DEFAULT 'all',
            status TEXT DEFAULT 'Active'
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_offer_usage (
            usage_id TEXT PRIMARY KEY,
            offer_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            usage_date TEXT,
            discount_amount REAL,
            FOREIGN KEY (offer_id) REFERENCES restaurant_special_offers (offer_id),
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers (customer_id),
            FOREIGN KEY (order_id) REFERENCES restaurant_orders (order_id)
        )
        ''')

        # Enhanced Meal Plans
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_meal_plans (
            plan_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            plan_type TEXT NOT NULL,
            balance REAL NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            auto_reload INTEGER DEFAULT 0,
            reload_amount REAL DEFAULT 0,
            reload_threshold REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_date TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_meal_plan_transactions (
            transaction_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            balance_before REAL,
            balance_after REAL,
            reference_id TEXT,
            transaction_date TEXT,
            description TEXT,
            FOREIGN KEY (plan_id) REFERENCES restaurant_meal_plans (plan_id)
        )
        ''')

        # Marketing & Promotions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_marketing_campaigns (
            campaign_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            target_audience TEXT,
            start_date TEXT,
            end_date TEXT,
            budget REAL DEFAULT 0,
            spent_amount REAL DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Draft',
            created_by TEXT,
            created_date TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_customer_segments (
            segment_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            criteria TEXT NOT NULL,
            customer_count INTEGER DEFAULT 0,
            created_date TEXT,
            last_updated TEXT
        )
        ''')

        # Quality & Compliance
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_temperature_logs (
            log_id TEXT PRIMARY KEY,
            equipment_id TEXT NOT NULL,
            temperature REAL NOT NULL,
            recorded_date TEXT NOT NULL,
            recorded_by TEXT,
            location TEXT,
            notes TEXT,
            alert_triggered INTEGER DEFAULT 0
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_food_safety_checks (
            check_id TEXT PRIMARY KEY,
            check_type TEXT NOT NULL,
            check_date TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            results TEXT NOT NULL,
            notes TEXT,
            corrective_actions TEXT,
            follow_up_date TEXT,
            status TEXT DEFAULT 'Completed'
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_waste_tracking (
            waste_id TEXT PRIMARY KEY,
            item_id TEXT,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            waste_reason TEXT NOT NULL,
            cost_impact REAL DEFAULT 0,
            recorded_date TEXT NOT NULL,
            recorded_by TEXT,
            location TEXT,
            FOREIGN KEY (item_id) REFERENCES menu_items (item_id)
        )
        ''')

        # System Administration
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_audit_logs (
            log_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            table_name TEXT,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            timestamp TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_system_settings (
            setting_name TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            description TEXT,
            category TEXT,
            last_updated TEXT,
            updated_by TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_notifications (
            notification_id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_date TEXT NOT NULL,
            read_date TEXT,
            priority TEXT DEFAULT 'Normal',
            category TEXT,
            action_required INTEGER DEFAULT 0
        )
        ''')

        # Technology Integration
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_qr_codes (
            qr_id TEXT PRIMARY KEY,
            table_id TEXT,
            qr_data TEXT NOT NULL,
            created_date TEXT,
            last_used TEXT,
            usage_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (table_id) REFERENCES restaurant_tables (table_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_mobile_orders (
            mobile_order_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            app_type TEXT NOT NULL,
            device_info TEXT,
            location_info TEXT,
            pickup_time TEXT,
            notification_sent INTEGER DEFAULT 0,
            FOREIGN KEY (order_id) REFERENCES restaurant_orders (order_id)
        )
        ''')

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_restaurant_orders_date ON restaurant_orders(order_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_restaurant_orders_customer ON restaurant_orders(customer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_restaurant_orders_status ON restaurant_orders(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_restaurant_customer_email ON restaurant_customers(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_restaurant_inventory_reorder ON restaurant_inventory(reorder_level)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_restaurant_staff_schedules_date ON restaurant_staff_schedules(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_restaurant_audit_logs_timestamp ON restaurant_audit_logs(timestamp)')

        # Insert default data if restaurant_tables are empty
        initialize_default_data(cursor)

        conn.commit()
        conn.close()

        logging.info("Restaurant database initialized successfully")
        print("Enhanced restaurant database initialized successfully!")
        return True

    except sqlite3.Error as e:
        logging.error(f"Database initialization error: {e}")
        print(f"Database initialization error: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error during database initialization: {e}")
        print(f"Unexpected error: {e}")
        return False

def initialize_default_data(cursor):
    """Initialize default data for the restaurant system"""
    try:
        # Check if menu items exist
        cursor.execute('SELECT COUNT(*) FROM menu_items')
        if cursor.fetchone()[0] == 0:
            default_items = [
                ('M001', 'University Burger', 'Beef patty with lettuce, tomato, cheese, and special sauce', 5.99, 'Main', 'Dairy, Gluten', 0, 0, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 580, 25, 45, 30, 15, 3.50, None, 85),
                ('M002', 'Veggie Wrap', 'Fresh vegetables with hummus in a wrap', 4.50, 'Main', 'Gluten', 1, 1, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 420, 15, 55, 12, 10, 2.75, None, 72),
                ('M003', 'Chicken Caesar Salad', 'Grilled chicken, romaine lettuce, croutons, and Caesar dressing', 6.50, 'Main', 'Dairy, Gluten', 0, 0, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 390, 35, 15, 22, 12, 4.25, None, 68),
                ('S001', 'French Fries', 'Crispy golden fries', 2.50, 'Side', 'None', 1, 1, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 320, 4, 45, 15, 8, 1.20, None, 92),
                ('S002', 'Onion Rings', 'Battered and fried onion rings', 3.00, 'Side', 'Gluten', 1, 1, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 280, 5, 35, 18, 10, 1.50, None, 65),
                ('D001', 'Chocolate Brownie', 'Rich chocolate brownie', 2.75, 'Dessert', 'Dairy, Gluten, Eggs', 1, 0, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 450, 6, 58, 20, 5, 1.25, None, 78),
                ('D002', 'Fruit Salad', 'Fresh seasonal fruits', 3.25, 'Dessert', 'None', 1, 1, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 120, 2, 30, 0, 3, 2.00, None, 55),
                ('B001', 'Soda', 'Choice of cola, lemon-lime, or orange', 1.50, 'Beverage', 'None', 1, 1, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 150, 0, 39, 0, 1, 0.25, None, 88),
                ('B002', 'Coffee', 'Freshly brewed coffee', 2.00, 'Beverage', 'None', 1, 1, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 5, 0, 0, 0, 2, 0.50, None, 95)
            ]

            cursor.executemany('''
                INSERT INTO menu_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', default_items)

        # Initialize default restaurant_tables
        cursor.execute('SELECT COUNT(*) FROM restaurant_tables')
        if cursor.fetchone()[0] == 0:
            default_tables = [
                ('T001', 2, 'Available', None, 'Main Dining', 'Standard', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ('T002', 4, 'Available', None, 'Main Dining', 'Standard', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ('T003', 6, 'Available', None, 'Main Dining', 'Large', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ('T004', 8, 'Available', None, 'Private Room', 'VIP', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ('T005', 2, 'Available', None, 'Patio', 'Outdoor', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            ]

            cursor.executemany('INSERT INTO restaurant_tables VALUES (?, ?, ?, ?, ?, ?, ?)', default_tables)

        # Initialize system settings
        cursor.execute('SELECT COUNT(*) FROM restaurant_system_settings')
        if cursor.fetchone()[0] == 0:
            default_settings = [
                ('tax_rate', '0.08', 'Sales tax rate percentage', 'Financial', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system'),
                ('service_charge', '0.10', 'Service charge percentage for large groups', 'Financial', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system'),
                ('loyalty_points_rate', '0.05', 'Points earned per dollar spent', 'Customer', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system'),
                ('reservation_window', '30', 'Days in advance for reservations', 'Operations', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system'),
                ('low_stock_threshold', '10', 'Default low stock alert threshold', 'Inventory', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system'),
                ('kitchen_prep_time', '15', 'Average kitchen preparation time in minutes', 'Operations', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system')
            ]

            cursor.executemany('INSERT INTO restaurant_system_settings VALUES (?, ?, ?, ?, ?, ?)', default_settings)

        logging.info("Restaurant default data initialized successfully")

    except sqlite3.Error as e:
        logging.error(f"Error initializing restaurant default data: {e}")
        raise

def display_main_menu():
    """Display main menu for the restaurant management system"""
    global auth

    while True:
        print("\n" + "="*60)
        print("UNIVERSITY RESTAURANT MANAGEMENT SYSTEM")
        print("="*60)
        print(f"Welcome, {auth.current_user['username']}!")
        print(f"Role: {auth.current_user['role']}")

        print("\nMain Menu:")
        print("1. Menu Items Management")
        print("2. Orders Management")
        print("3. Customer Management")
        print("4. Table Management")
        print("5. Staff Management")
        print("6. Inventory Management")
        print("7. Financial Reports")
        print("8. System Settings")
        print("9. Data Backup & Recovery")
        print("10. Logout")
        print("11. Exit")

        choice = input("Choose an option (1-11): ")

        if choice == '1':
            display_menu_items_menu()
        elif choice == '2':
            display_orders_menu()
        elif choice == '3':
            display_customer_menu()
        elif choice == '4':
            display_table_management()
        elif choice == '5':
            display_staff_management()
        elif choice == '6':
            display_inventory_management()
        elif choice == '7':
            display_financial_reports()
        elif choice == '8':
            display_system_settings()
        elif choice == '9':
            display_backup_menu()
        elif choice == '10':
            auth.logout()
            print("Logged out successfully.")
            break
        elif choice == '11':
            print("Thank you for using the Restaurant Management System!")
            return
        else:
            print("Invalid choice. Please try again.")
