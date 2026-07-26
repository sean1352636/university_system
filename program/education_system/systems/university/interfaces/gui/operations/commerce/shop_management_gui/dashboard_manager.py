import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
import time
import os
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
from threading import Thread
import webbrowser
from tkinter import font

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from education_system.systems.university.domain.operations.commerce.services.shop_management import (
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
from education_system.systems.university.infrastructure.auth import UserAuth, get_global_auth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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


def show_analytics_dashboard(self):
    """Display analytics dashboard"""
    self.clear_content()
    self.update_status(_t("shop_management.status.loading_analytics"))

    # Check permissions
    if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
        ttk.Label(self.content_frame, text=_t("common.access_denied"), style='Error.TLabel').grid(row=0, column=0)
        return

    # Title
    ttk.Label(self.content_frame, text=_t("shop_management.titles.analytics_dashboard"), style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 20))

    # Create main dashboard frame
    dash_frame = ttk.Frame(self.content_frame)
    dash_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
    dash_frame.columnconfigure((0, 1), weight=1)

    # Sales analytics
    sales_frame = ttk.LabelFrame(dash_frame, text=_t("shop_management.labels.sales_analytics"), padding="10")
    sales_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 10))

    try:
        analytics = get_customer_analytics()
        if analytics and analytics['overview']:
            overview = analytics['overview']
            ttk.Label(sales_frame, text=f"{_t('shop_management.labels.revenue_30_days')}: £{overview.get('total_revenue', 0):.2f}").grid(row=0, column=0, sticky=tk.W, pady=2)
            ttk.Label(sales_frame, text=f"{_t('shop_management.labels.total_customers')}: {overview.get('total_customers', 0)}").grid(row=1, column=0, sticky=tk.W, pady=2)
            ttk.Label(sales_frame, text=f"{_t('shop_management.labels.avg_order_value')}: £{overview.get('avg_order_value', 0):.2f}").grid(row=2, column=0, sticky=tk.W, pady=2)
    except Exception:
        ttk.Label(sales_frame, text=_t("shop_management.messages.analytics_unavailable")).grid(row=0, column=0, sticky=tk.W, pady=2)

    # Inventory analytics
    inventory_frame = ttk.LabelFrame(dash_frame, text=_t("shop_management.labels.inventory_analytics"), padding="10")
    inventory_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(10, 0))

    try:
        valuation = get_inventory_valuation()
        ttk.Label(inventory_frame, text=f"{_t('shop_management.labels.total_inventory_value')}: £{valuation['total_value']:.2f}").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(inventory_frame, text=f"{_t('shop_management.labels.total_products')}: {valuation['product_count']}").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Label(inventory_frame, text=f"{_t('shop_management.labels.total_items')}: {valuation['total_quantity']}").grid(row=2, column=0, sticky=tk.W, pady=2)

        # Low stock alert
        low_stock_count = len(self.get_low_stock_items())
        if low_stock_count > 0:
            ttk.Label(inventory_frame, text=f"⚠️ {_t('shop_management.labels.low_stock_items')}: {low_stock_count}",
                     style='Warning.TLabel').grid(row=3, column=0, sticky=tk.W, pady=2)
    except Exception:
        ttk.Label(inventory_frame, text=_t("shop_management.messages.inventory_unavailable")).grid(row=0, column=0, sticky=tk.W, pady=2)

    # Action buttons
    action_frame = ttk.Frame(dash_frame)
    action_frame.grid(row=1, column=0, columnspan=2, pady=20)

    ttk.Button(action_frame, text=_t("shop_management.buttons.view_customer_analytics"),
              command=self.show_customer_analytics).grid(row=0, column=0, padx=5)
    ttk.Button(action_frame, text=_t("shop_management.buttons.generate_reports"),
              command=self.show_reports).grid(row=0, column=1, padx=5)
    ttk.Button(action_frame, text=_t("shop_management.buttons.bulk_operations"),
              command=self.show_bulk_operations).grid(row=0, column=2, padx=5)

    self.update_status(_t("shop_management.status.analytics_loaded"))


def show_customer_analytics(self):
    """Display customer analytics"""
    try:
        # Get customer analytics data
        analytics = get_customer_analytics()

        if not analytics:
            messagebox.showinfo(_t("shop_management.titles.customer_analytics"),
                              _t("shop_management.messages.no_analytics_data"))
            return

        # Create analytics window
        analytics_window = tk.Toplevel(self.root)
        analytics_window.title(_t("shop_management.titles.customer_analytics"))
        analytics_window.geometry("800x600")
        analytics_window.transient(self.root)

        main_frame = ttk.Frame(analytics_window, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t("shop_management.titles.customer_analytics"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Display analytics data
        from tkinter.scrolledtext import ScrolledText
        text_widget = ScrolledText(main_frame, height=25, width=90, font=('Courier', 9))
        text_widget.pack(fill='both', expand=True, pady=10)

        # Format analytics as text
        analytics_text = _t("shop_management.reports.customer_analytics_header") + "\n"
        analytics_text += "=" * 80 + "\n\n"

        if isinstance(analytics, dict):
            for key, value in analytics.items():
                analytics_text += f"{key}: {value}\n"
        else:
            analytics_text += str(analytics)

        text_widget.insert('1.0', analytics_text)
        text_widget.config(state='disabled')

        ttk.Button(main_frame, text=_t("common.close"),
                  command=analytics_window.destroy).pack(pady=10)

        analytics_window.update_idletasks()
        analytics_window.grab_set()

    except Exception as e:
        messagebox.showerror(_t("common.error"), f"{_t('shop_management.messages.analytics_load_failed')}:\n{str(e)}")


def show_dashboard(self):
    """Display dashboard with key metrics"""
    self.clear_content()
    self.update_status(_t("shop_management.status.loading_dashboard"))

    # Title
    ttk.Label(self.content_frame, text=_t("shop_management.titles.dashboard"), style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 20))

    # Create main dashboard frame
    dash_frame = ttk.Frame(self.content_frame)
    dash_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
    dash_frame.columnconfigure(1, weight=1)

    # Quick stats cards
    stats_frame = ttk.LabelFrame(dash_frame, text=_t("shop_management.labels.quick_stats"), padding="10")
    stats_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    try:
        # Get stats from backend if available
        stats = self.get_dashboard_stats()

        # Display stats in a grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.grid(row=0, column=0, sticky=(tk.W, tk.E))
        stats_grid.columnconfigure((0, 1, 2, 3), weight=1)

        # Total Products
        self.create_stat_card(stats_grid, _t("shop_management.labels.total_products"), stats.get('total_products', 'N/A'), 0, 0)

        # Low Stock Items
        low_stock = stats.get('low_stock', 0)
        self.create_stat_card(stats_grid, _t("shop_management.labels.low_stock_items"), low_stock, 0, 1,
                            'Warning' if low_stock > 0 else 'Success')

        # Recent Sales
        self.create_stat_card(stats_grid, _t("shop_management.labels.sales_30_days"), stats.get('recent_sales', 'N/A'), 0, 2)

        # Cart Items
        cart_count = len(self.cart_items)
        self.create_stat_card(stats_grid, _t("shop_management.labels.cart_items"), cart_count, 0, 3,
                            'Success' if cart_count > 0 else None)

    except Exception as e:
        ttk.Label(stats_frame, text=f"{_t('shop_management.messages.stats_error')}: {e}", style='Error.TLabel').grid(row=0, column=0)

    # Recent activity / Quick actions
    actions_frame = ttk.LabelFrame(dash_frame, text=_t("shop_management.labels.quick_actions"), padding="10")
    actions_frame.grid(row=1, column=0, sticky=(tk.W, tk.N), padx=(0, 10))

    ttk.Button(actions_frame, text=_t("shop_management.buttons.browse_products"), command=self.show_browse_products,
              style='Primary.TButton', width=20).grid(row=0, column=0, pady=5)
    ttk.Button(actions_frame, text=_t("shop_management.buttons.view_cart"), command=self.show_shopping_cart, width=20).grid(row=1, column=0, pady=5)
    ttk.Button(actions_frame, text=_t("shop_management.buttons.order_history"), command=self.show_order_history, width=20).grid(row=2, column=0, pady=5)

    # Admin quick actions
    if self.current_user.get('role') in ['admin', 'staff', 'shop_manager']:
        ttk.Separator(actions_frame, orient='horizontal').grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        ttk.Button(actions_frame, text=_t("shop_management.buttons.add_product"), command=self.show_add_product_dialog,
                  style='Success.TButton', width=20).grid(row=4, column=0, pady=5)
        ttk.Button(actions_frame, text=_t("shop_management.buttons.view_reports"), command=self.show_reports, width=20).grid(row=5, column=0, pady=5)

    # News/Alerts
    alerts_frame = ttk.LabelFrame(dash_frame, text=_t("shop_management.labels.alerts_news"), padding="10")
    alerts_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
    alerts_frame.columnconfigure(0, weight=1)
    alerts_frame.rowconfigure(0, weight=1)

    # Scrollable text widget for alerts
    alerts_text = tk.Text(alerts_frame, height=10, wrap=tk.WORD, state='disabled')
    alerts_scrollbar = ttk.Scrollbar(alerts_frame, orient='vertical', command=alerts_text.yview)
    alerts_text.configure(yscrollcommand=alerts_scrollbar.set)

    alerts_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    alerts_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    # Add sample alerts
    alerts_text.configure(state='normal')
    alerts_text.insert(tk.END, "📢 " + _t("shop_management.alerts.welcome") + "\n\n")

    if stats.get('low_stock', 0) > 0:
        alerts_text.insert(tk.END, f"⚠️ {stats['low_stock']} {_t('shop_management.alerts.low_stock_warning')}\n\n")

    alerts_text.insert(tk.END, "🎉 " + _t("shop_management.alerts.check_latest") + "\n\n")
    alerts_text.insert(tk.END, "💡 " + _t("shop_management.alerts.search_tip") + "\n\n")
    alerts_text.configure(state='disabled')

    self.update_status(_t("shop_management.status.dashboard_loaded"))


def create_stat_card(self, parent, title, value, row, col, style=None):
    """Create a statistics card widget"""
    card_frame = ttk.Frame(parent, relief='ridge', borderwidth=1, padding="10")
    card_frame.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E))

    ttk.Label(card_frame, text=title, font=('Arial', 10)).grid(row=0, column=0)

    value_style = f'{style}.TLabel' if style else 'TLabel'
    ttk.Label(card_frame, text=str(value), font=('Arial', 14, 'bold'),
             style=value_style).grid(row=1, column=0)


def show_club_merchandise_selection(self):
    """Display page to select which club to buy merchandise for"""
    self.clear_content()
    self.update_status("Loading club merchandise selection...")

    # Title
    title_frame = ttk.Frame(self.content_frame)
    title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 20))

    ttk.Label(title_frame, text="Club Merchandise", style='Title.TLabel').pack(side='left')
    ttk.Label(title_frame, text="Select a club to browse merchandise",
             font=('Arial', 10), foreground='gray').pack(side='left', padx=20)

    # Main content frame
    main_frame = ttk.Frame(self.content_frame)
    main_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
    main_frame.columnconfigure(0, weight=1)

    # Instructions
    instructions_frame = ttk.LabelFrame(main_frame, text="Instructions", padding="15")
    instructions_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))

    ttk.Label(instructions_frame, text="Select a student club below to view and purchase their official merchandise.",
             wraplength=600).pack()

    # Club selection frame
    clubs_frame = ttk.LabelFrame(main_frame, text="Available Clubs", padding="15")
    clubs_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    clubs_frame.columnconfigure(0, weight=1)
    clubs_frame.rowconfigure(1, weight=1)

    # Search frame
    search_frame = ttk.Frame(clubs_frame)
    search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side='left', padx=5)

    # Clubs list
    list_frame = ttk.Frame(clubs_frame)
    list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    list_frame.columnconfigure(0, weight=1)
    list_frame.rowconfigure(0, weight=1)

    # Create treeview for clubs
    columns = ('club_id', 'club_name', 'category', 'members')
    clubs_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

    clubs_tree.heading('club_id', text='ID')
    clubs_tree.heading('club_name', text='Club Name')
    clubs_tree.heading('category', text='Category')
    clubs_tree.heading('members', text='Members')

    clubs_tree.column('club_id', width=60)
    clubs_tree.column('club_name', width=250)
    clubs_tree.column('category', width=150)
    clubs_tree.column('members', width=100)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=clubs_tree.yview)
    h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=clubs_tree.xview)
    clubs_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    clubs_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

    # Load clubs from database
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT club_id, club_name, category, member_count
            FROM student_clubs
            WHERE status = 'active'
            ORDER BY club_name
        ''')
        clubs = cursor.fetchall()

        for club in clubs:
            clubs_tree.insert('', tk.END, values=club)

        conn.close()

        # Update instructions with club count
        ttk.Label(instructions_frame,
                 text=f"({len(clubs)} active clubs available)",
                 font=('Arial', 9), foreground='gray').pack()

    except Exception as e:
        ttk.Label(list_frame, text=f"Error loading clubs: {e}",
                 foreground='red').grid(row=0, column=0, pady=20)

    # Action buttons
    button_frame = ttk.Frame(clubs_frame)
    button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(15, 0))

    def view_club_merchandise():
        selection = clubs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a club to view merchandise.")
            return

        item = clubs_tree.item(selection[0])
        club_id = item['values'][0]
        club_name = item['values'][1]

        # Filter products by club category or tag
        self.show_browse_products()  # Show regular browse with filter option
        self.update_status(f"Showing merchandise for: {club_name}")
        messagebox.showinfo("Club Merchandise",
                           f"Browsing merchandise for {club_name}\n\n"
                           f"Tip: Products tagged with '{club_name}' will appear in the list.")

    ttk.Button(button_frame, text="View Merchandise", command=view_club_merchandise,
              style='Primary.TButton').pack(side='left', padx=5)
    ttk.Button(button_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='left', padx=5)

    # Search functionality
    def search_clubs(*args):
        search_term = search_var.get().lower()
        clubs_tree.delete(*clubs_tree.get_children())

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT club_id, club_name, category, member_count
                FROM student_clubs
                WHERE status = 'active'
                AND (LOWER(club_name) LIKE ? OR LOWER(category) LIKE ?)
                ORDER BY club_name
            ''', (f'%{search_term}%', f'%{search_term}%'))
            clubs = cursor.fetchall()

            for club in clubs:
                clubs_tree.insert('', tk.END, values=club)

            conn.close()
        except Exception as e:
            print(f"Error searching clubs: {e}")

    search_var.trace('w', search_clubs)

    # Double-click to view merchandise
    clubs_tree.bind('<Double-1>', lambda e: view_club_merchandise())

    self.update_status("Club merchandise selection loaded")


def get_dashboard_stats(self):
    """Get dashboard statistics from backend"""
    try:
        # Use original functions if available
        stats = {}

        if 'get_connection' in globals():
            conn = get_connection()
            cursor = conn.cursor()

            # Total products
            cursor.execute("SELECT COUNT(*) FROM products WHERE source_type = 'shop' AND is_active = 1")
            stats['total_products'] = cursor.fetchone()[0]

            # Low stock items
            cursor.execute("""
                SELECT COUNT(*) FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop' AND p.is_active = 1 AND i.quantity <= i.restock_threshold
            """)
            stats['low_stock'] = cursor.fetchone()[0]

            # Recent sales (30 days)
            cursor.execute("""
                SELECT COUNT(*) FROM transactions
                WHERE source_type = 'shop' AND created_at >= date('now', '-30 days')
            """)
            stats['recent_sales'] = cursor.fetchone()[0]

            conn.close()
        else:
            # Fallback stats
            stats = {
                'total_products': 10,
                'low_stock': 2,
                'recent_sales': 15
            }

        return stats

    except Exception as e:
        return {'error': str(e)}


def toggle_discount_status(self):
    """Toggle the status of the selected discount"""
    selection = self.discounts_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a discount to toggle status.")
        return

    discount_id = self.discounts_tree.item(selection[0])['text']
    current_status = self.discounts_tree.item(selection[0])['values'][2]

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        new_status = 0 if current_status == "Active" else 1
        cursor.execute('''
            UPDATE shop_discounts
            SET is_active = ?
            WHERE discount_id = ?
        ''', (new_status, discount_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        messagebox.showinfo("Success", f"Discount {discount_id} has been {status_text}.")
        self.load_discounts()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to update discount status: {str(e)}")


def get_monthly_stats(self, year, month):
    """Get monthly sales statistics"""
    try:
        if 'get_connection' not in globals():
            return {'total_sales': 0, 'transaction_count': 0, 'avg_order': 0, 'items_sold': 0}

        # Calculate month boundaries
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)

        start_str = first_day.strftime('%Y-%m-%d 00:00:00')
        end_str = last_day.strftime('%Y-%m-%d 23:59:59')

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Basic stats
        cursor.execute("""
            SELECT COUNT(*) as transaction_count,
                   SUM(total_amount) as total_sales,
                   AVG(total_amount) as avg_order
            FROM transactions
            WHERE source_type = 'shop' AND created_at BETWEEN ? AND ?
        """, [start_str, end_str])

        basic_stats = cursor.fetchone()

        # Items sold
        cursor.execute("""
            SELECT SUM(ti.quantity) as items_sold
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            WHERE t.created_at BETWEEN ? AND ?
        """, [start_str, end_str])

        items_result = cursor.fetchone()

        # Weekly breakdown
        weekly_breakdown = []
        current_week = first_day
        week_num = 1

        while current_week <= last_day:
            week_end = min(current_week + timedelta(days=6), last_day)

            cursor.execute("""
                SELECT COUNT(*) as count, SUM(total_amount) as amount
                FROM transactions
                WHERE source_type = 'shop' AND created_at BETWEEN ? AND ?
            """, [current_week.strftime('%Y-%m-%d 00:00:00'),
                  week_end.strftime('%Y-%m-%d 23:59:59')])

            week_data = cursor.fetchone()
            weekly_breakdown.append({
                'week': week_num,
                'count': week_data['count'] or 0,
                'amount': week_data['amount'] or 0
            })

            current_week = week_end + timedelta(days=1)
            week_num += 1

        conn.close()

        return {
            'total_sales': basic_stats['total_sales'] or 0,
            'transaction_count': basic_stats['transaction_count'] or 0,
            'avg_order': basic_stats['avg_order'] or 0,
            'items_sold': items_result['items_sold'] or 0,
            'weekly_breakdown': weekly_breakdown
        }

    except Exception as e:
        return {'error': str(e)}


def get_weekly_stats(self):
    """Get current week's sales statistics"""
    try:
        if 'get_connection' not in globals():
            return {'total_sales': 0, 'transaction_count': 0, 'avg_order': 0, 'items_sold': 0}

        # Calculate week boundaries (Monday to Sunday)
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        start_str = start_of_week.strftime('%Y-%m-%d 00:00:00')
        end_str = end_of_week.strftime('%Y-%m-%d 23:59:59')

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Basic stats
        cursor.execute("""
            SELECT COUNT(*) as transaction_count,
                   SUM(total_amount) as total_sales,
                   AVG(total_amount) as avg_order
            FROM transactions
            WHERE source_type = 'shop' AND created_at BETWEEN ? AND ?
        """, [start_str, end_str])

        basic_stats = cursor.fetchone()

        # Items sold
        cursor.execute("""
            SELECT SUM(ti.quantity) as items_sold
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            WHERE t.created_at BETWEEN ? AND ?
        """, [start_str, end_str])

        items_result = cursor.fetchone()

        # Daily breakdown
        daily_breakdown = {}
        current_day = start_of_week

        while current_day <= end_of_week:
            day_str = current_day.strftime('%Y-%m-%d')

            cursor.execute("""
                SELECT COUNT(*) as count, SUM(total_amount) as amount
                FROM transactions
                WHERE source_type = 'shop' AND DATE(created_at) = ?
            """, [day_str])

            day_data = cursor.fetchone()
            daily_breakdown[day_str] = {
                'count': day_data['count'] or 0,
                'amount': day_data['amount'] or 0
            }

            current_day += timedelta(days=1)

        conn.close()

        return {
            'total_sales': basic_stats['total_sales'] or 0,
            'transaction_count': basic_stats['transaction_count'] or 0,
            'avg_order': basic_stats['avg_order'] or 0,
            'items_sold': items_result['items_sold'] or 0,
            'daily_breakdown': daily_breakdown
        }

    except Exception as e:
        return {'error': str(e)}


def show_sales_summary_report(self, start_date, end_date):
    """Show sales summary report for date range"""
    # Clear report display
    for widget in self.report_display_frame.winfo_children():
        widget.destroy()

    try:
        # Get sales data
        sales_data = self.get_sales_summary_data(start_date, end_date)

        # Report title
        ttk.Label(self.report_display_frame, text=f"Sales Summary: {start_date} to {end_date}",
                 style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Summary stats
        stats_frame = ttk.Frame(self.report_display_frame)
        stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        stats_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.create_stat_card(stats_frame, "Total Revenue", f"£{sales_data.get('total_revenue', 0):.2f}", 0, 0)
        self.create_stat_card(stats_frame, "Transactions", sales_data.get('transaction_count', 0), 0, 1)
        self.create_stat_card(stats_frame, "Avg Order", f"£{sales_data.get('avg_order_value', 0):.2f}", 0, 2)
        self.create_stat_card(stats_frame, "Items Sold", sales_data.get('total_items', 0), 0, 3)

        # Daily trend if available
        if sales_data.get('daily_trend'):
            trend_frame = ttk.LabelFrame(self.report_display_frame, text="Daily Sales Trend", padding="10")
            trend_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)

            for date, amount in sales_data['daily_trend'].items():
                ttk.Label(trend_frame, text=f"{date}: £{amount:.2f}").grid(
                    row=len(trend_frame.winfo_children()), column=0, sticky=tk.W, pady=1)

    except Exception as e:
        ttk.Label(self.report_display_frame, text=f"Error loading sales summary: {e}",
                 style='Error.TLabel').grid(row=1, column=0)


def get_sales_summary_data(self, start_date, end_date):
    """Get sales summary data for the inclusive date range [start_date, end_date]."""
    conn = None
    try:
        # Get a DB connection
        if hasattr(self, "get_connection") and callable(getattr(self, "get_connection")):
            conn = self.get_connection()
        elif "get_connection" in globals() and callable(globals()["get_connection"]):
            conn = globals()["get_connection"]()
        else:
            return {"error": "get_connection() not available"}

        if conn is None:
            return {"error": "get_connection() returned None"}

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Basic summary
        cursor.execute(
            """
            SELECT
                COUNT(*) AS transaction_count,
                COALESCE(SUM(total_amount), 0) AS total_revenue,
                COALESCE(AVG(total_amount), 0) AS avg_order_value
            FROM transactions
            WHERE source_type = 'shop' AND DATE(created_at) BETWEEN ? AND ?
            """,
            (start_date, end_date),
        )
        summary_row = cursor.fetchone()
        summary = dict(summary_row) if summary_row else {}

        # Total items sold
        cursor.execute(
            """
            SELECT COALESCE(SUM(ti.quantity), 0) AS total_items
            FROM shop_transaction_items ti
            JOIN transactions t
              ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            WHERE DATE(t.created_at) BETWEEN ? AND ?
            """,
            (start_date, end_date),
        )
        items_row = cursor.fetchone()
        items_result = dict(items_row) if items_row else {}

        # Daily trend
        cursor.execute(
            """
            SELECT
                DATE(created_at) AS d,
                COALESCE(SUM(total_amount), 0) AS daily_total
            FROM transactions
            WHERE source_type = 'shop' AND DATE(created_at) BETWEEN ? AND ?
            GROUP BY DATE(created_at)
            ORDER BY d
            """,
            (start_date, end_date),
        )
        daily_trend = {row["d"]: row["daily_total"] for row in cursor.fetchall()}

        return {
            "transaction_count": summary.get("transaction_count", 0),
            "total_revenue": summary.get("total_revenue", 0),
            "avg_order_value": summary.get("avg_order_value", 0),
            "total_items": items_result.get("total_items", 0),
            "daily_trend": daily_trend,
        }

    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


def toggle_product_status(self):
    """Toggle active status of selected product"""
    if not hasattr(self, 'mgmt_products_tree'):
        return

    selection = self.mgmt_products_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product")
        return

    item = self.mgmt_products_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    current_status = values[5]

    new_status = "Inactive" if current_status == "Active" else "Active"

    if messagebox.askyesno("Confirm", f"Change product status to {new_status}?"):
        try:
            self.update_product_status(product_id, new_status == "Active")
            self.load_products_for_management()
            self.update_status(f"Product {product_id} status changed to {new_status}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update status: {e}")


def update_product_status(self, product_id, is_active):
    """Update product active status"""
    try:
        if 'get_connection' in globals():
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE products
                SET is_active = ?, updated_at = ?
                WHERE source_type = 'shop' AND source_product_id = ?
            """, [is_active, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id])

            conn.commit()
            conn.close()

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise Exception(f"Database error: {e}")


def get_daily_stats(self, date):
    """Get daily sales statistics"""
    try:

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Basic stats
        cursor.execute("""
            SELECT COUNT(*) as transaction_count,
                   SUM(total_amount) as total_sales,
                   AVG(total_amount) as avg_order
            FROM transactions
            WHERE source_type = 'shop' AND DATE(created_at) = ?
        """, [date])

        basic_stats = cursor.fetchone()

        # Items sold
        cursor.execute("""
            SELECT SUM(ti.quantity) as items_sold
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            WHERE DATE(t.created_at) = ?
        """, [date])

        items_result = cursor.fetchone()

        # Top products
        cursor.execute("""
            SELECT p.name, SUM(ti.quantity) as quantity
            FROM shop_transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.source_transaction_id AND t.source_type = 'shop'
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE DATE(t.created_at) = ?
            GROUP BY p.source_product_id
            ORDER BY quantity DESC
            LIMIT 5
        """, [date])

        top_products = cursor.fetchall()

        conn.close()

        return {
            'total_sales': basic_stats['total_sales'] or 0,
            'transaction_count': basic_stats['transaction_count'] or 0,
            'avg_order': basic_stats['avg_order'] or 0,
            'items_sold': items_result['items_sold'] or 0,
            'top_products': [dict(product) for product in top_products]
        }

    except Exception as e:
        return {'error': str(e)}


def show_low_stock_report(self):
    """Show low stock report"""
    try:
        # Get low stock items
        low_stock_items = self.get_low_stock_items()

        if not low_stock_items:
            messagebox.showinfo("Low Stock Report",
                              "✅ All products are adequately stocked!")
            return

        # Generate report content as text
        report = "LOW STOCK REPORT\n"
        report += "=" * 80 + "\n\n"

        critical_count = len([item for item in low_stock_items if item['quantity'] == 0])
        urgent_count = len([item for item in low_stock_items if 0 < item['quantity'] <= item['restock_threshold']])

        report += f"⚠️ {len(low_stock_items)} products need attention\n"
        if critical_count > 0:
            report += f"🔴 {critical_count} products are OUT OF STOCK\n"
        if urgent_count > 0:
            report += f"🟡 {urgent_count} products need immediate restocking\n"
        report += "\n"

        report += f"{'Product ID':<15} {'Name':<30} {'Category':<15} {'Stock':<8} {'Threshold':<10} {'Action':<15}\n"
        report += "-" * 80 + "\n"

        for item in low_stock_items:
            if item['quantity'] == 0:
                action = "OUT OF STOCK"
            elif item['quantity'] <= item['restock_threshold']:
                action = "RESTOCK NOW"
            else:
                action = "Monitor"

            report += f"{item['product_id']:<15} {item['name']:<30} {item['category']:<15} {item['quantity']:<8} {item['restock_threshold']:<10} {action:<15}\n"

        report += "\n" + "=" * 80 + "\n"

        # Show in new window with export/email buttons
        self.show_report_window("Low Stock Report", report)

    except Exception as e:
        messagebox.showerror("Report Error", f"Error loading low stock report:\n{str(e)}")


def get_low_stock_items(self):
    """Get list of low stock items"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.source_product_id as product_id, p.name, p.category, i.quantity, i.restock_threshold
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.is_active = 1 AND i.quantity <= i.restock_threshold * 1.2
            ORDER BY (i.quantity * 1.0 / i.restock_threshold), p.name
        """)

        items = cursor.fetchall()
        conn.close()

        return [dict(item) for item in items]

    except Exception:
        return []


def update_status(self, message):
    """Update the status bar"""
    if self.status_label:
        self.status_label.config(text=message)
        self.root.update_idletasks()


