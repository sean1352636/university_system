"""
Cafe System - Reports tab mixin
Handles report generation, export, and emailing
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.interfaces.gui.operations.commerce.cafe_common import get_db_connection, EMAIL_SERVICE_AVAILABLE


class CafeReportsMixin:
    """Mixin for reports tab functionality"""

    def create_reports_tab(self):
        """Create reports tab"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text=_t("cafe.tab_reports"))

        # Reports selection
        controls_frame = ttk.Frame(reports_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(controls_frame, text=_t("cafe.reports.select_report")).pack(side=tk.LEFT, padx=5)

        self.report_type = ttk.Combobox(
            controls_frame,
            values=[_t("cafe.reports.daily_sales"), _t("cafe.reports.weekly_sales"), _t("cafe.reports.monthly_sales"), _t("cafe.reports.total_revenue"), _t("cafe.reports.popular_items"), _t("cafe.reports.low_stock_alert")],
            state='readonly'
        )
        self.report_type.set(_t("cafe.reports.daily_sales"))
        self.report_type.pack(side=tk.LEFT, padx=5)

        ttk.Button(controls_frame, text=_t("cafe.reports.generate_report"), command=self.generate_report).pack(side=tk.LEFT, padx=5)

        # Report action buttons
        actions_frame = ttk.Frame(reports_frame)
        actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            actions_frame,
            text=_t("cafe.reports.save_as_txt"),
            command=self.save_report_as_txt
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            actions_frame,
            text=_t("cafe.reports.open_in_window"),
            command=self.open_report_in_window
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            actions_frame,
            text=_t("cafe.reports.email_to_admin"),
            command=self.email_report_to_admin
        ).pack(side=tk.LEFT, padx=5)

        # Report display
        report_display_frame = ttk.Frame(reports_frame)
        report_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        report_scroll = ttk.Scrollbar(report_display_frame)
        report_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.report_text = ScrolledText(
            report_display_frame,
            wrap=tk.WORD,
            yscrollcommand=report_scroll.set,
            font=('Courier', 10)
        )
        report_scroll.config(command=self.report_text.yview)
        self.report_text.pack(fill=tk.BOTH, expand=True)

    def generate_report(self):
        """Generate selected report"""
        report_type = self.report_type.get()
        self.report_text.delete('1.0', tk.END)

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            report_content = ""

            if report_type == 'Daily Sales':
                report_content = "=== DAILY SALES REPORT ===\n\n"
                report_content += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"

                cursor.execute('''
                    SELECT COUNT(*), SUM(total_amount)
                    FROM orders
                    WHERE source_type = 'cafe' AND DATE(order_date) = DATE('now')
                ''')
                result = cursor.fetchone()
                order_count = result[0] or 0
                total_sales = result[1] or 0.0

                report_content += f"Total Orders: {order_count}\n"
                report_content += f"Total Sales: £{total_sales:.2f}\n\n"

                cursor.execute('''
                    SELECT payment_method, COUNT(*), SUM(total_amount)
                    FROM orders
                    WHERE source_type = 'cafe' AND DATE(order_date) = DATE('now')
                    GROUP BY payment_method
                ''')

                report_content += "Sales by Payment Method:\n"
                for row in cursor.fetchall():
                    method, count, amount = row
                    report_content += f"  {method}: {count} orders, £{amount:.2f}\n"

                # Show finance system synced revenue
                report_content += "\n--- Finance System Revenue (Synced) ---\n"
                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(amount), 0)
                    FROM payments
                    WHERE notes LIKE '[Cafe]%' AND DATE(payment_date) = DATE('now')
                ''')
                finance_result = cursor.fetchone()
                finance_count = finance_result[0] or 0
                finance_total = finance_result[1] or 0.0
                report_content += f"Finance Transactions: {finance_count}\n"
                report_content += f"Finance Total Revenue: £{finance_total:.2f}\n"

            elif report_type == 'Weekly Sales':
                report_content = "=== WEEKLY SALES REPORT ===\n\n"
                report_content += f"Week ending: {datetime.now().strftime('%Y-%m-%d')}\n\n"

                cursor.execute('''
                    SELECT COUNT(*), SUM(total_amount)
                    FROM orders
                    WHERE source_type = 'cafe' AND DATE(order_date) >= DATE('now', '-7 days')
                ''')
                result = cursor.fetchone()
                order_count = result[0] or 0
                total_sales = result[1] or 0.0

                report_content += f"Total Orders: {order_count}\n"
                report_content += f"Total Sales: £{total_sales:.2f}\n"
                report_content += f"Average per day: £{total_sales/7:.2f}\n\n"

                # Show finance system synced revenue
                report_content += "--- Finance System Revenue (Synced) ---\n"
                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(amount), 0)
                    FROM payments
                    WHERE notes LIKE '[Cafe]%' AND DATE(payment_date) >= DATE('now', '-7 days')
                ''')
                finance_result = cursor.fetchone()
                finance_count = finance_result[0] or 0
                finance_total = finance_result[1] or 0.0
                report_content += f"Finance Transactions: {finance_count}\n"
                report_content += f"Finance Total Revenue: £{finance_total:.2f}\n"

            elif report_type == 'Monthly Sales':
                report_content = "=== MONTHLY SALES REPORT ===\n\n"
                report_content += f"Month: {datetime.now().strftime('%B %Y')}\n\n"

                cursor.execute('''
                    SELECT COUNT(*), SUM(total_amount)
                    FROM orders
                    WHERE source_type = 'cafe' AND DATE(order_date) >= DATE('now', 'start of month')
                ''')
                result = cursor.fetchone()
                order_count = result[0] or 0
                total_sales = result[1] or 0.0

                report_content += f"Total Orders: {order_count}\n"
                report_content += f"Total Sales: £{total_sales:.2f}\n\n"

                # Show finance system synced revenue
                report_content += "--- Finance System Revenue (Synced) ---\n"
                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(amount), 0)
                    FROM payments
                    WHERE notes LIKE '[Cafe]%' AND DATE(payment_date) >= DATE('now', 'start of month')
                ''')
                finance_result = cursor.fetchone()
                finance_count = finance_result[0] or 0
                finance_total = finance_result[1] or 0.0
                report_content += f"Finance Transactions: {finance_count}\n"
                report_content += f"Finance Total Revenue: £{finance_total:.2f}\n"

            elif report_type == 'Total Revenue':
                report_content = "=== TOTAL REVENUE REPORT ===\n\n"
                report_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

                # Cafe orders total
                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(total_amount), 0)
                    FROM orders
                    WHERE source_type = 'cafe' AND order_status = 'completed'
                ''')
                result = cursor.fetchone()
                total_orders = result[0] or 0
                cafe_total = result[1] or 0.0

                report_content += "═══════════════════════════════════════════════════════\n"
                report_content += "                    CAFE SALES SUMMARY\n"
                report_content += "═══════════════════════════════════════════════════════\n\n"
                report_content += f"Total Completed Orders:    {total_orders}\n"
                report_content += f"Total Cafe Revenue:        £{cafe_total:.2f}\n\n"

                # Revenue by payment method
                report_content += "Revenue by Payment Method:\n"
                report_content += "───────────────────────────────────────────────────────\n"
                cursor.execute('''
                    SELECT payment_method, COUNT(*), SUM(total_amount)
                    FROM orders
                    WHERE source_type = 'cafe' AND order_status = 'completed'
                    GROUP BY payment_method
                    ORDER BY SUM(total_amount) DESC
                ''')
                for row in cursor.fetchall():
                    method, count, amount = row
                    report_content += f"  {method or 'Unknown':<20} {count:>5} orders  £{amount or 0:.2f}\n"

                # Finance system synced total
                report_content += "\n═══════════════════════════════════════════════════════\n"
                report_content += "              FINANCE SYSTEM (SYNCED)\n"
                report_content += "═══════════════════════════════════════════════════════\n\n"

                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(amount), 0)
                    FROM payments
                    WHERE notes LIKE '[Cafe]%'
                ''')
                finance_result = cursor.fetchone()
                finance_count = finance_result[0] or 0
                finance_total = finance_result[1] or 0.0

                report_content += f"Finance Transactions:      {finance_count}\n"
                report_content += f"Finance Total Revenue:     £{finance_total:.2f}\n\n"

                report_content += "This revenue is reflected in the main Finance GUI\n"
                report_content += "dashboard under 'Total Revenue' and can be viewed\n"
                report_content += "in the Revenue by Source report as 'Cafe'.\n"

            elif report_type == 'Popular Items':
                report_content = "=== POPULAR ITEMS REPORT ===\n\n"

                cursor.execute('''
                    SELECT item_name, SUM(quantity) as total_qty, SUM(subtotal) as total_sales
                    FROM order_items
                    WHERE source_type = 'cafe'
                    GROUP BY item_name
                    ORDER BY total_qty DESC
                    LIMIT 20
                ''')

                report_content += "Top 20 Most Popular Items:\n\n"
                rank = 1
                for row in cursor.fetchall():
                    item, qty, sales = row
                    report_content += f"{rank}. {item}: {qty} units sold, £{sales:.2f} revenue\n"
                    rank += 1

            elif report_type == 'Low Stock Alert':
                report_content = "=== LOW STOCK ALERT ===\n\n"

                cursor.execute('''
                    SELECT name, category, stock_quantity
                    FROM products
                    WHERE source_type = 'cafe' AND stock_quantity < 20
                    ORDER BY stock_quantity ASC
                ''')

                items = cursor.fetchall()
                if items:
                    report_content += "Items requiring attention:\n\n"
                    for item, category, stock in items:
                        status = "OUT OF STOCK" if stock == 0 else "LOW STOCK"
                        report_content += f"  [{status}] {item} ({category}): {stock} units\n"
                else:
                    report_content += "All items have adequate stock levels.\n"

            conn.close()

            self.report_text.insert('1.0', report_content)

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.generate_report", error=str(e)))

    def save_report_as_txt(self):
        """Save the current report as a TXT file"""
        # Get report content
        report_content = self.report_text.get('1.0', tk.END).strip()

        if not report_content:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.no_report"))
            return

        # Generate default filename based on report type and date
        report_type = self.report_type.get().replace(' ', '_').lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"cafe_{report_type}_{timestamp}.txt"

        # Ask user for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_filename,
            title=_t("cafe.reports.save_title")
        )

        if not file_path:
            return  # User cancelled

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            messagebox.showinfo(_t("common.success"), _t("cafe.messages.report_saved", path=file_path))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("cafe.errors.save_report", error=str(e)))

    def open_report_in_window(self):
        """Open the current report in a separate window"""
        # Get report content
        report_content = self.report_text.get('1.0', tk.END).strip()

        if not report_content:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.no_report_display"))
            return

        # Create new window
        report_window = tk.Toplevel(self.cafe_window)
        report_window.title(f"Cafe Report - {self.report_type.get()}")
        report_window.geometry("700x600")

        # Add header
        header_frame = ttk.Frame(report_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text=f"Cafe Report: {self.report_type.get()}",
            font=('Helvetica', 14, 'bold')
        ).pack(side=tk.LEFT)

        ttk.Label(
            header_frame,
            text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            font=('Helvetica', 10)
        ).pack(side=tk.RIGHT)

        # Add report text
        text_frame = ttk.Frame(report_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        report_text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=report_text_widget.yview)
        report_text_widget.pack(fill=tk.BOTH, expand=True)

        # Insert content
        report_text_widget.insert('1.0', report_content)
        report_text_widget.config(state=tk.DISABLED)  # Make read-only

        # Add buttons at bottom
        button_frame = ttk.Frame(report_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(
            button_frame,
            text=_t("cafe.reports.save_as_txt"),
            command=self.save_report_as_txt
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t("cafe.reports.email_to_admin"),
            command=self.email_report_to_admin
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t("cafe.dialogs.close"),
            command=report_window.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def email_report_to_admin(self):
        """Email the current report to admin"""
        if not EMAIL_SERVICE_AVAILABLE:
            messagebox.showerror(_t("common.error"), _t("cafe.messages.email_not_available"))
            return

        from education_system.systems.university.infrastructure.email.email_service import send_email

        # Get report content
        report_content = self.report_text.get('1.0', tk.END).strip()

        if not report_content:
            messagebox.showwarning(_t("common.warning"), _t("cafe.messages.no_report_email"))
            return

        # Get admin email from database
        admin_email = self._get_admin_email()
        if not admin_email:
            messagebox.showerror(_t("common.error"), _t("cafe.messages.admin_email_not_found"))
            return

        # Confirm before sending
        if not messagebox.askyesno(
            _t("common.confirm"),
            _t("cafe.messages.confirm_email", type=self.report_type.get(), email=admin_email)
        ):
            return

        # Prepare email
        report_type = self.report_type.get()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Prepare template variables
        from education_system.systems.university.infrastructure.email.template_utils import render_template

        template_vars = {
            'report_type': report_type,
            'timestamp': timestamp,
            'generated_by': self.current_user.get('username', 'Unknown') if self.current_user else 'System',
            'report_content': report_content
        }

        subject, body = render_template('commerce/cafe_report', template_vars)
        if not subject or not body:
            messagebox.showerror(_t("common.error"), "Failed to render email template")
            return

        try:
            result = send_email(admin_email, subject, body)
            if result:
                messagebox.showinfo(_t("common.success"), _t("cafe.messages.email_sent", email=admin_email))
            else:
                messagebox.showerror(_t("common.error"), _t("cafe.messages.email_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to send email: {e}")

    def _get_admin_email(self):
        """Get admin email address from database"""
        try:
            conn = get_db_connection()
            if not conn:
                return None

            cursor = conn.cursor()
            cursor.execute('''
                SELECT email FROM users
                WHERE role = 'admin' AND username = 'admin'
                LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()

            if result:
                return result[0]
            return None
        except Exception as e:
            print(f"Error getting admin email: {e}")
            return None
