import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
import time
import os
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
import pandas as pd
from threading import Thread
import webbrowser
from tkinter import font

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from education_system.university_system.modules.domain.commerce.services.shop_management import (
        auth, add_to_shopping_cart, browse_products, checkout_process,
        display_product_management_menu, display_shop_menu,
        get_customer_analytics, get_inventory_valuation, init_shop_db,
        print_product_labels, search_products, set_auth,
        toggle_discount_status, toggle_product_status, view_purchase_history
    )
except Exception:
    try:
        from shop_management import (
            auth, add_to_shopping_cart, browse_products, checkout_process,
            display_product_management_menu, display_shop_menu,
            get_customer_analytics, get_inventory_valuation, init_shop_db,
            print_product_labels, search_products, set_auth,
            toggle_discount_status, toggle_product_status, view_purchase_history
        )
    except Exception:
        # If running standalone, we'll define the essential fallback functions
        def get_customer_analytics():
            return None

        def get_inventory_valuation():
            return {'total_value': 0, 'product_count': 0, 'total_quantity': 0}

        def print_product_labels(product_ids=None):
            print("Label printing functionality not available")

        # Note: get_low_stock_items is implemented as a class method in UniversityShopGUI

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Initialize logger
logger = logging.getLogger(__name__)


def show_monthly_report(self):
    """Show monthly sales report"""
    # Clear report display
    for widget in self.report_display_frame.winfo_children():
        widget.destroy()

    # Report title and month selection
    title_frame = ttk.Frame(self.report_display_frame)
    title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(title_frame, text="Monthly Sales Report", style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W)

    # Month/Year selection
    today = datetime.now()
    month_frame = ttk.Frame(title_frame)
    month_frame.grid(row=0, column=1, sticky=tk.E)

    ttk.Label(month_frame, text="Year:").grid(row=0, column=0, padx=(0, 5))
    year_var = tk.StringVar(value=str(today.year))
    year_combo = ttk.Combobox(month_frame, textvariable=year_var, width=6,
                             values=[str(y) for y in range(2020, today.year + 2)])
    year_combo.grid(row=0, column=1, padx=5)

    ttk.Label(month_frame, text="Month:").grid(row=0, column=2, padx=(10, 5))
    month_var = tk.StringVar(value=str(today.month))
    month_combo = ttk.Combobox(month_frame, textvariable=month_var, width=6,
                              values=[str(m) for m in range(1, 13)])
    month_combo.grid(row=0, column=3, padx=5)

    def generate_monthly_report():
        try:
            year = int(year_var.get())
            month = int(month_var.get())

            # Generate monthly stats using existing backend function
            stats = self.get_monthly_stats(year, month)

            # Clear previous results
            for widget in self.report_display_frame.winfo_children()[1:]:
                widget.destroy()

            # Display monthly stats
            stats_frame = ttk.Frame(self.report_display_frame)
            stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
            stats_frame.columnconfigure((0, 1, 2, 3), weight=1)

            month_name = datetime(year, month, 1).strftime('%B %Y')
            ttk.Label(stats_frame, text=f"Report for {month_name}",
                     style='Heading.TLabel').grid(row=0, column=0, columnspan=4, pady=(0, 10))

            self.create_stat_card(stats_frame, "Total Sales", f"£{stats.get('total_sales', 0):.2f}", 1, 0)
            self.create_stat_card(stats_frame, "Transactions", stats.get('transaction_count', 0), 1, 1)
            self.create_stat_card(stats_frame, "Avg Order", f"£{stats.get('avg_order', 0):.2f}", 1, 2)
            self.create_stat_card(stats_frame, "Items Sold", stats.get('items_sold', 0), 1, 3)

            # Weekly breakdown
            if stats.get('weekly_breakdown'):
                weekly_frame = ttk.LabelFrame(self.report_display_frame, text="Weekly Breakdown", padding="10")
                weekly_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)

                for i, week_data in enumerate(stats['weekly_breakdown']):
                    week_label = f"Week {i+1}"
                    ttk.Label(weekly_frame, text=f"{week_label}: £{week_data['amount']:.2f} ({week_data['count']} orders)").grid(
                        row=i, column=0, sticky=tk.W, pady=2)

        except ValueError:
            messagebox.showerror("Error", "Please enter valid year and month")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate monthly report: {e}")

    ttk.Button(month_frame, text="Generate", command=generate_monthly_report).grid(row=0, column=4, padx=10)


def show_weekly_report(self):
    """Show weekly sales report"""
    # Clear report display
    for widget in self.report_display_frame.winfo_children():
        widget.destroy()

    # Report title
    ttk.Label(self.report_display_frame, text="Weekly Sales Report",
             style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

    try:
        # Get weekly stats
        stats = self.get_weekly_stats()

        # Stats display
        stats_frame = ttk.Frame(self.report_display_frame)
        stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        stats_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.create_stat_card(stats_frame, "Total Sales", f"£{stats.get('total_sales', 0):.2f}", 0, 0)
        self.create_stat_card(stats_frame, "Transactions", stats.get('transaction_count', 0), 0, 1)
        self.create_stat_card(stats_frame, "Avg Order", f"£{stats.get('avg_order', 0):.2f}", 0, 2)
        self.create_stat_card(stats_frame, "Items Sold", stats.get('items_sold', 0), 0, 3)

        # Daily breakdown
        if stats.get('daily_breakdown'):
            daily_frame = ttk.LabelFrame(self.report_display_frame, text="Daily Breakdown", padding="10")
            daily_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)

            for day, data in stats['daily_breakdown'].items():
                day_name = datetime.strptime(day, '%Y-%m-%d').strftime('%A, %b %d')
                ttk.Label(daily_frame, text=f"{day_name}: £{data['amount']:.2f} ({data['count']} orders)").grid(
                    row=len(daily_frame.winfo_children()), column=0, sticky=tk.W, pady=2)

    except Exception as e:
        ttk.Label(self.report_display_frame, text=f"Error loading weekly report: {e}",
                 style='Error.TLabel').grid(row=1, column=0)


def show_top_products_report(self):
    """Show top products report"""
    # Clear report display
    for widget in self.report_display_frame.winfo_children():
        widget.destroy()

    # Report title
    ttk.Label(self.report_display_frame, text="Top Products Report",
             style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

    try:
        # Get top products
        top_products = self.get_top_products_data()

        if not top_products:
            ttk.Label(self.report_display_frame, text="No product sales data available",
                     style='Warning.TLabel').grid(row=1, column=0, pady=20)
            return

        # Top products table
        products_frame = ttk.Frame(self.report_display_frame)
        products_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        products_frame.columnconfigure(0, weight=1)
        products_frame.rowconfigure(0, weight=1)

        # Create treeview
        columns = ('Rank', 'Product ID', 'Name', 'Category', 'Quantity Sold', 'Revenue', 'Avg Price')
        products_tree = ttk.Treeview(products_frame, columns=columns, show='headings', height=15)

        for col in columns:
            products_tree.heading(col, text=col)

        products_tree.column('Rank', width=50)
        products_tree.column('Product ID', width=100)
        products_tree.column('Name', width=200)
        products_tree.column('Category', width=120)
        products_tree.column('Quantity Sold', width=100)
        products_tree.column('Revenue', width=100)
        products_tree.column('Avg Price', width=100)

        # Scrollbar
        products_scrollbar = ttk.Scrollbar(products_frame, orient='vertical', command=products_tree.yview)
        products_tree.configure(yscrollcommand=products_scrollbar.set)

        products_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        products_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Populate data
        for i, product in enumerate(top_products, 1):
            avg_price = product['total_revenue'] / product['total_quantity'] if product['total_quantity'] > 0 else 0
            products_tree.insert('', 'end', values=(
                i,
                product['product_id'],
                product['name'],
                product['category'],
                product['total_quantity'],
                f"£{product['total_revenue']:.2f}",
                f"£{avg_price:.2f}"
            ))

    except Exception as e:
        ttk.Label(self.report_display_frame, text=f"Error loading top products: {e}",
                 style='Error.TLabel').grid(row=1, column=0)


def get_top_products_data(self, limit=20, days=30):
    """Get top products data"""
    try:
        if 'get_connection' not in globals():
            return []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.source_product_id as product_id, p.name, p.category,
                   SUM(ti.quantity) as total_quantity,
                   SUM(ti.subtotal) as total_revenue,
                   COUNT(DISTINCT ti.transaction_id) as transaction_count
            FROM shop_transaction_items ti
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            WHERE t.created_at >= ?
            GROUP BY p.source_product_id
            ORDER BY total_revenue DESC
            LIMIT ?
        """, [start_date.strftime('%Y-%m-%d %H:%M:%S'), limit])

        products = cursor.fetchall()
        conn.close()

        return [dict(product) for product in products]

    except Exception as e:
        return []


def generate_custom_report(self):
    """Generate custom report based on user selection"""
    report_type = self.report_type_var.get()
    start_date = self.report_start_date.get()
    end_date = self.report_end_date.get()

    try:
        # Validate dates
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')

        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()

        # Show loading
        ttk.Label(self.report_display_frame, text="Generating custom report...",
                 style='Heading.TLabel').grid(row=0, column=0, pady=20)
        self.root.update()

        if report_type == "sales_summary":
            self.show_sales_summary_report(start_date, end_date)
        elif report_type == "product_performance":
            self.show_product_performance_report(start_date, end_date)
        elif report_type == "category_analysis":
            self.show_category_analysis_report(start_date, end_date)
        elif report_type == "customer_analysis":
            self.show_customer_analysis_report(start_date, end_date)
        elif report_type == "payment_methods":
            self.show_payment_methods_report(start_date, end_date)

    except ValueError:
        messagebox.showerror("Error", "Please enter valid dates in YYYY-MM-DD format")
    except Exception as e:
        # Clear and show error
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        ttk.Label(self.report_display_frame, text=f"Error generating report: {e}",
                 style='Error.TLabel').grid(row=0, column=0, pady=20)


def show_product_performance_report(self, start_date, end_date):
    """Show product performance report"""
    # Clear report display
    for widget in self.report_display_frame.winfo_children():
        widget.destroy()

    try:
        # Get product performance data
        performance_data = self.get_product_performance_data(start_date, end_date)

        # Report title
        ttk.Label(self.report_display_frame, text=f"Product Performance: {start_date} to {end_date}",
                 style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Performance table
        performance_frame = ttk.Frame(self.report_display_frame)
        performance_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        performance_frame.columnconfigure(0, weight=1)
        performance_frame.rowconfigure(0, weight=1)

        columns = ('Product ID', 'Name', 'Category', 'Units Sold', 'Revenue', 'Avg Price', 'Performance')
        perf_tree = ttk.Treeview(performance_frame, columns=columns, show='headings', height=15)

        for col in columns:
            perf_tree.heading(col, text=col)

        perf_scrollbar = ttk.Scrollbar(performance_frame, orient='vertical', command=perf_tree.yview)
        perf_tree.configure(yscrollcommand=perf_scrollbar.set)

        perf_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        perf_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Populate performance data
        for product in performance_data:
            avg_price = product['revenue'] / product['units_sold'] if product['units_sold'] > 0 else 0
            performance_rating = "High" if product['revenue'] > 100 else "Medium" if product['revenue'] > 50 else "Low"

            perf_tree.insert('', 'end', values=(
                product['product_id'],
                product['name'],
                product['category'],
                product['units_sold'],
                f"£{product['revenue']:.2f}",
                f"£{avg_price:.2f}",
                performance_rating
            ))

    except Exception as e:
        ttk.Label(self.report_display_frame, text=f"Error loading product performance: {e}",
                 style='Error.TLabel').grid(row=1, column=0)


def get_product_performance_data(self, start_date, end_date):
    """Get product performance data"""
    try:
        if 'get_connection' not in globals():
            return []

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.source_product_id as product_id, p.name, p.category,
                   SUM(ti.quantity) as units_sold,
                   SUM(ti.subtotal) as revenue
            FROM shop_transaction_items ti
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            WHERE DATE(t.created_at) BETWEEN ? AND ?
            GROUP BY p.source_product_id
            ORDER BY revenue DESC
        """, [start_date, end_date])

        products = cursor.fetchall()
        conn.close()

        return [dict(product) for product in products]

    except Exception as e:
        return []


def show_category_analysis_report(self, start_date, end_date):
    """Show category analysis report"""
    # Clear report display
    for widget in self.report_display_frame.winfo_children():
        widget.destroy()

    try:
        # Get category data
        category_data = self.get_category_analysis_data(start_date, end_date)

        # Report title
        ttk.Label(self.report_display_frame, text=f"Category Analysis: {start_date} to {end_date}",
                 style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Category table
        category_frame = ttk.Frame(self.report_display_frame)
        category_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        category_frame.columnconfigure(0, weight=1)
        category_frame.rowconfigure(0, weight=1)

        columns = ('Category', 'Products', 'Units Sold', 'Revenue', 'Avg per Product', 'Market Share %')
        cat_tree = ttk.Treeview(category_frame, columns=columns, show='headings', height=10)

        for col in columns:
            cat_tree.heading(col, text=col)

        cat_scrollbar = ttk.Scrollbar(category_frame, orient='vertical', command=cat_tree.yview)
        cat_tree.configure(yscrollcommand=cat_scrollbar.set)

        cat_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        cat_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Calculate total revenue for market share
        total_revenue = sum(cat['revenue'] for cat in category_data)

        # Populate category data
        for category in category_data:
            avg_per_product = category['revenue'] / category['product_count'] if category['product_count'] > 0 else 0
            market_share = (category['revenue'] / total_revenue * 100) if total_revenue > 0 else 0

            cat_tree.insert('', 'end', values=(
                category['category'],
                category['product_count'],
                category['units_sold'],
                f"£{category['revenue']:.2f}",
                f"£{avg_per_product:.2f}",
                f"{market_share:.1f}%"
            ))

    except Exception as e:
        ttk.Label(self.report_display_frame, text=f"Error loading category analysis: {e}",
                 style='Error.TLabel').grid(row=1, column=0)


def get_category_analysis_data(self, start_date, end_date):
    """Get category analysis data"""
    try:
        if 'get_connection' not in globals():
            return []

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.category,
                   COUNT(DISTINCT p.product_id) as product_count,
                   SUM(ti.quantity) as units_sold,
                   SUM(ti.subtotal) as revenue
            FROM shop_transaction_items ti
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            WHERE DATE(t.created_at) BETWEEN ? AND ?
            GROUP BY p.category
            ORDER BY revenue DESC
        """, [start_date, end_date])

        categories = cursor.fetchall()
        conn.close()

        return [dict(category) for category in categories]

    except Exception as e:
        return []


def show_customer_analysis_report(self, start_date, end_date):
    """Show customer analysis report"""
    # Clear report display
    for widget in self.report_display_frame.winfo_children():
        widget.destroy()

    try:
        # Get customer data
        customer_data = self.get_customer_analysis_data(start_date, end_date)

        # Report title
        ttk.Label(self.report_display_frame, text=f"Customer Analysis: {start_date} to {end_date}",
                 style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Summary stats
        stats_frame = ttk.Frame(self.report_display_frame)
        stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        stats_frame.columnconfigure((0, 1, 2), weight=1)

        self.create_stat_card(stats_frame, "Total Customers", customer_data.get('total_customers', 0), 0, 0)
        self.create_stat_card(stats_frame, "Avg Orders/Customer", f"{customer_data.get('avg_orders_per_customer', 0):.1f}", 0, 1)
        self.create_stat_card(stats_frame, "Avg Spend/Customer", f"£{customer_data.get('avg_spend_per_customer', 0):.2f}", 0, 2)

        # Top customers table
        if customer_data.get('top_customers'):
            customers_frame = ttk.LabelFrame(self.report_display_frame, text="Top Customers", padding="10")
            customers_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
            customers_frame.columnconfigure(0, weight=1)
            customers_frame.rowconfigure(0, weight=1)

            columns = ('Username', 'Student ID', 'Orders', 'Total Spent', 'Avg Order')
            cust_tree = ttk.Treeview(customers_frame, columns=columns, show='headings', height=10)

            for col in columns:
                cust_tree.heading(col, text=col)

            cust_scrollbar = ttk.Scrollbar(customers_frame, orient='vertical', command=cust_tree.yview)
            cust_tree.configure(yscrollcommand=cust_scrollbar.set)

            cust_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            cust_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

            # Populate customer data
            for customer in customer_data['top_customers']:
                avg_order = customer['total_spent'] / customer['order_count'] if customer['order_count'] > 0 else 0
                cust_tree.insert('', 'end', values=(
                    customer['username'],
                    customer['student_id'] or 'N/A',
                    customer['order_count'],
                    f"£{customer['total_spent']:.2f}",
                    f"£{avg_order:.2f}"
                ))

    except Exception as e:
        ttk.Label(self.report_display_frame, text=f"Error loading customer analysis: {e}",
                 style='Error.TLabel').grid(row=1, column=0)


def get_customer_analysis_data(self, start_date, end_date):
    """Get customer analysis data"""
    try:
        if 'get_connection' not in globals():
            return {}

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Customer summary
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as total_customers,
                   AVG(orders_per_customer) as avg_orders_per_customer,
                   AVG(spend_per_customer) as avg_spend_per_customer
            FROM (
                SELECT user_id,
                       COUNT(*) as orders_per_customer,
                       SUM(total_amount) as spend_per_customer
                FROM transactions
                WHERE source_type = 'shop' AND DATE(created_at) BETWEEN ? AND ?
                GROUP BY customer_id
            )
        """, [start_date, end_date])

        summary = cursor.fetchone()

        # Top customers
        cursor.execute("""
            SELECT u.username, u.student_id,
                   COUNT(t.transaction_id) as order_count,
                   SUM(t.total_amount) as total_spent
            FROM transactions t
            JOIN users u ON t.customer_id = u.id
            WHERE t.source_type = 'shop' AND DATE(t.created_at) BETWEEN ? AND ?
            GROUP BY u.id
            ORDER BY total_spent DESC
            LIMIT 10
        """, [start_date, end_date])

        top_customers = cursor.fetchall()
        conn.close()

        return {
            'total_customers': summary['total_customers'] or 0,
            'avg_orders_per_customer': summary['avg_orders_per_customer'] or 0,
            'avg_spend_per_customer': summary['avg_spend_per_customer'] or 0,
            'top_customers': [dict(customer) for customer in top_customers]
        }

    except Exception as e:
        return {'error': str(e)}


def show_report_window(self, title, report_content):
    """
    Display a report in a new window with export and email buttons.

    Args:
        title: Window title and report name
        report_content: The text content of the report
    """
    # Create report window
    report_window = tk.Toplevel(self.root)
    report_window.title(title)
    report_window.geometry("900x700")
    report_window.transient(self.root)

    main_frame = ttk.Frame(report_window, padding=20)
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=10)

    # Report display area
    report_frame = ttk.LabelFrame(main_frame, text="Report", padding=10)
    report_frame.pack(fill='both', expand=True, pady=10)

    from tkinter.scrolledtext import ScrolledText
    report_text = ScrolledText(report_frame, height=25, width=100, font=('Courier', 9))
    report_text.pack(fill='both', expand=True)
    report_text.insert('1.0', report_content)
    report_text.config(state='disabled')  # Make read-only

    # Buttons frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)

    def export_as_txt():
        """Export report to a text file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Clean title for filename
            clean_title = title.replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{clean_title}_{timestamp}.txt"
            filepath = os.path.join(os.getcwd(), filename)

            with open(filepath, 'w') as f:
                f.write(report_content)

            messagebox.showinfo("Export Success",
                              f"Report exported successfully!\n\n"
                              f"File: {filename}\n"
                              f"Location: {filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report:\n{str(e)}")

    def email_to_admin():
        """Email report to admin"""
        try:
            # Get admin email from database
            conn = get_connection()
            if not conn:
                messagebox.showerror("Database Error", "Could not connect to database")
                return

            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1")
            result = cursor.fetchone()
            conn.close()

            if not result or not result[0]:
                messagebox.showerror("Email Error",
                                   "No admin email found in database.\n"
                                   "Please configure an admin email address first.")
                return

            admin_email = result[0]

            # Import email service
            try:
                from education_system.university_system.infrastructure.email.email_service import send_email
            except ImportError:
                messagebox.showerror("Email Error",
                                   "Email service not available.\n"
                                   "Please check your email configuration.")
                return

            # Prepare template variables
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'title': title,
                'report_content': report_content
            }

            subject, body = render_template('commerce/shop_report', template_vars)
            if not subject or not body:
                messagebox.showerror("Email Error", "Failed to render email template")
                return

            send_email(admin_email, subject, body)

            messagebox.showinfo("Email Sent",
                              f"Report has been sent to admin email:\n{admin_email}")

        except Exception as e:
            messagebox.showerror("Email Error", f"Failed to send email:\n{str(e)}")

    ttk.Button(btn_frame, text="Export as TXT", command=export_as_txt).grid(row=0, column=0, padx=5)
    ttk.Button(btn_frame, text="Email to Admin", command=email_to_admin).grid(row=0, column=1, padx=5)
    ttk.Button(btn_frame, text="Close", command=report_window.destroy).grid(row=0, column=2, padx=5)

    # Now that window is fully created, make it modal
    report_window.update_idletasks()
    report_window.grab_set()


def show_reports(self):
    """Display reports interface"""
    self.clear_content()
    self.update_status("Loading reports...")

    # Check permissions
    if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
        ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
        return

    # Title
    ttk.Label(self.content_frame, text="Sales Reports", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 20))

    # Report categories
    reports_frame = ttk.Frame(self.content_frame)
    reports_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    reports_frame.columnconfigure((0, 1), weight=1)

    # Quick Reports
    quick_frame = ttk.LabelFrame(reports_frame, text="Quick Reports", padding="15")
    quick_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 10))

    ttk.Button(quick_frame, text="📊 Daily Sales", command=lambda: self.generate_quick_report('daily'),
              width=20).grid(row=0, column=0, pady=5, sticky=tk.W)
    ttk.Button(quick_frame, text="📈 Weekly Sales", command=lambda: self.generate_quick_report('weekly'),
              width=20).grid(row=1, column=0, pady=5, sticky=tk.W)
    ttk.Button(quick_frame, text="📅 Monthly Sales", command=lambda: self.generate_quick_report('monthly'),
              width=20).grid(row=2, column=0, pady=5, sticky=tk.W)
    ttk.Button(quick_frame, text="🏆 Top Products", command=lambda: self.generate_quick_report('top_products'),
              width=20).grid(row=3, column=0, pady=5, sticky=tk.W)
    ttk.Button(quick_frame, text="📦 Low Stock", command=self.show_low_stock_report,
              width=20).grid(row=4, column=0, pady=5, sticky=tk.W)

    # Custom Reports
    custom_frame = ttk.LabelFrame(reports_frame, text="Custom Reports", padding="15")
    custom_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(10, 0))

    # Date range selector
    ttk.Label(custom_frame, text="Date Range:").grid(row=0, column=0, sticky=tk.W, pady=5)

    date_frame = ttk.Frame(custom_frame)
    date_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)

    ttk.Label(date_frame, text="From:").grid(row=0, column=0)
    self.report_start_date = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    ttk.Entry(date_frame, textvariable=self.report_start_date, width=12).grid(row=0, column=1, padx=5)

    ttk.Label(date_frame, text="To:").grid(row=0, column=2, padx=(10, 0))
    self.report_end_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
    ttk.Entry(date_frame, textvariable=self.report_end_date, width=12).grid(row=0, column=3, padx=5)

    # Report type selector
    ttk.Label(custom_frame, text="Report Type:").grid(row=2, column=0, sticky=tk.W, pady=(10, 5))
    self.report_type_var = tk.StringVar(value="sales_summary")

    report_types = [
        ("Sales Summary", "sales_summary"),
        ("Product Performance", "product_performance"),
        ("Category Analysis", "category_analysis"),
        ("Customer Analysis", "customer_analysis"),
        ("Payment Methods", "payment_methods")
    ]

    for i, (label, value) in enumerate(report_types):
        ttk.Radiobutton(custom_frame, text=label, variable=self.report_type_var,
                       value=value).grid(row=3+i, column=0, sticky=tk.W, pady=2)

    # Generate button
    ttk.Button(custom_frame, text="Generate Custom Report",
              command=self.generate_custom_report, style='Primary.TButton').grid(row=10, column=0, pady=20)

    # Report display area
    self.report_display_frame = ttk.LabelFrame(self.content_frame, text="Report Results", padding="10")
    self.report_display_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=20)
    self.report_display_frame.columnconfigure(0, weight=1)
    self.report_display_frame.rowconfigure(0, weight=1)

    # Initial message
    ttk.Label(self.report_display_frame, text="Select a report type above to generate a report",
             style='Heading.TLabel').grid(row=0, column=0, pady=50)

    self.update_status("Reports interface loaded")


def generate_quick_report(self, report_type):
    """Generate a quick report"""
    try:
        # Clear report display
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()

        # Show loading
        ttk.Label(self.report_display_frame, text="Generating report...",
                 style='Heading.TLabel').grid(row=0, column=0, pady=20)
        self.root.update()

        # Generate report based on type
        if report_type == 'daily':
            self.show_daily_report()
        elif report_type == 'weekly':
            self.show_weekly_report()
        elif report_type == 'monthly':
            self.show_monthly_report()
        elif report_type == 'top_products':
            self.show_top_products_report()

    except Exception as e:
        # Clear and show error
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
        ttk.Label(self.report_display_frame, text=f"Error generating report: {e}",
                 style='Error.TLabel').grid(row=0, column=0, pady=20)


def show_daily_report(self):
    """Show daily sales report"""
    today = datetime.now().strftime('%Y-%m-%d')

    try:
        # Get daily stats
        stats = self.get_daily_stats(today)

        # Generate report content as text
        report = f"DAILY SALES REPORT - {today}\n"
        report += "=" * 80 + "\n\n"
        report += "SUMMARY:\n"
        report += "-" * 80 + "\n"
        report += f"Total Sales:       £{stats.get('total_sales', 0):.2f}\n"
        report += f"Transactions:      {stats.get('transaction_count', 0)}\n"
        report += f"Average Order:     £{stats.get('avg_order', 0):.2f}\n"
        report += f"Items Sold:        {stats.get('items_sold', 0)}\n\n"

        # Top products today
        if stats.get('top_products'):
            report += "TOP PRODUCTS TODAY:\n"
            report += "-" * 80 + "\n"
            for i, product in enumerate(stats['top_products'][:5], 1):
                report += f"{i}. {product['name']:<40} {product['quantity']:>5} sold\n"
            report += "\n"

        report += "=" * 80 + "\n"

        # Show in new window with export/email buttons
        self.show_report_window(f"Daily Sales Report - {today}", report)

    except Exception as e:
        messagebox.showerror("Report Error", f"Error loading daily report:\n{str(e)}")


