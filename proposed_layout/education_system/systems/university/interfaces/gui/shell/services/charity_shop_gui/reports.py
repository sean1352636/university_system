"""Charity Shop - Reports mixin for CharityShopApp."""

from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui._imports import (
    tk, ttk, messagebox, filedialog,
    datetime, sqlite3,
    DEFAULT_DB_PATH,
    EMAIL_SERVICE_AVAILABLE, send_email,
    logger,
)


class ReportsMixin:
    """Report operations for CharityShopApp."""

    def show_charts(self):
        """Show the charts and analytics window."""
        from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui.charts import ChartsWindow
        ChartsWindow(self.root, self.db)

    def show_report_with_type(self, report_type):
        """Show the reports window with a specific report type pre-selected"""
        self.show_reports_window()
        # Set the report type and generate
        if hasattr(self, 'report_type_var'):
            self.report_type_var.set(report_type)
            self.generate_report(report_type)

    def show_reports_window(self):
        """Show the reports window with all report options"""
        report_window = tk.Toplevel(self.root)
        report_window.title("Charity Shop Reports")
        report_window.geometry("800x650")
        report_window.minsize(700, 550)

        # Store reference for other methods
        self.report_window = report_window
        self.report_content = ""

        # Header
        header_frame = ttk.Frame(report_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="Charity Shop Reports",
            font=('Helvetica', 16, 'bold')
        ).pack(side=tk.LEFT)

        # Report selection
        controls_frame = ttk.Frame(report_window)
        controls_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(controls_frame, text="Select Report:").pack(side=tk.LEFT, padx=5)

        self.report_type_var = tk.StringVar(value='daily')
        report_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.report_type_var,
            values=['daily', 'weekly', 'monthly', 'total', 'stock', 'category'],
            state='readonly',
            width=20
        )
        report_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            controls_frame,
            text="Generate Report",
            command=lambda: self.generate_report(self.report_type_var.get())
        ).pack(side=tk.LEFT, padx=5)

        # Action buttons
        actions_frame = ttk.Frame(report_window)
        actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            actions_frame,
            text="Save as TXT",
            command=self.save_report_as_txt
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            actions_frame,
            text="Open in New Window",
            command=self.open_report_in_window
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            actions_frame,
            text="Email to Admin",
            command=self.email_report_to_admin
        ).pack(side=tk.LEFT, padx=5)

        # Report display
        display_frame = ttk.Frame(report_window)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = ttk.Scrollbar(display_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.report_text_widget = tk.Text(
            display_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.report_text_widget.yview)
        self.report_text_widget.pack(fill=tk.BOTH, expand=True)

        # Generate initial report
        self.generate_report('daily')

    def generate_report(self, report_type):
        """Generate a report of the specified type"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            report_content = ""
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if report_type == 'daily':
                report_content = "\u2550" * 60 + "\n"
                report_content += "           CHARITY SHOP - DAILY SALES REPORT\n"
                report_content += "\u2550" * 60 + "\n\n"
                report_content += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
                report_content += f"Generated: {timestamp}\n\n"

                # Today's sales
                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(price * quantity), 0)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) = DATE('now')
                ''')
                result = cursor.fetchone()
                items_sold = result[0] or 0
                daily_revenue = result[1] or 0.0

                report_content += f"Items Sold Today: {items_sold}\n"
                report_content += f"Daily Revenue: \u00a3{daily_revenue:.2f}\n\n"

                # Today's sales by category
                report_content += "\u2500" * 40 + "\n"
                report_content += "Sales by Category:\n"
                report_content += "\u2500" * 40 + "\n"
                cursor.execute('''
                    SELECT category, COUNT(*), SUM(price * quantity)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) = DATE('now')
                    GROUP BY category
                    ORDER BY SUM(price * quantity) DESC
                ''')
                for row in cursor.fetchall():
                    cat, count, amount = row
                    report_content += f"  {cat or 'Uncategorized':<20} {count:>3} items  \u00a3{amount or 0:.2f}\n"

            elif report_type == 'weekly':
                report_content = "\u2550" * 60 + "\n"
                report_content += "          CHARITY SHOP - WEEKLY SALES REPORT\n"
                report_content += "\u2550" * 60 + "\n\n"
                report_content += f"Week Ending: {datetime.now().strftime('%Y-%m-%d')}\n"
                report_content += f"Generated: {timestamp}\n\n"

                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(price * quantity), 0)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) >= DATE('now', '-7 days')
                ''')
                result = cursor.fetchone()
                items_sold = result[0] or 0
                weekly_revenue = result[1] or 0.0

                report_content += f"Items Sold This Week: {items_sold}\n"
                report_content += f"Weekly Revenue: \u00a3{weekly_revenue:.2f}\n"
                report_content += f"Average Per Day: \u00a3{weekly_revenue/7:.2f}\n\n"

                # Daily breakdown
                report_content += "\u2500" * 40 + "\n"
                report_content += "Daily Breakdown:\n"
                report_content += "\u2500" * 40 + "\n"
                cursor.execute('''
                    SELECT DATE(date_added), COUNT(*), SUM(price * quantity)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) >= DATE('now', '-7 days')
                    GROUP BY DATE(date_added)
                    ORDER BY DATE(date_added) DESC
                ''')
                for row in cursor.fetchall():
                    date, count, amount = row
                    report_content += f"  {date}  {count:>3} items  \u00a3{amount or 0:.2f}\n"

            elif report_type == 'monthly':
                report_content = "\u2550" * 60 + "\n"
                report_content += "         CHARITY SHOP - MONTHLY SALES REPORT\n"
                report_content += "\u2550" * 60 + "\n\n"
                report_content += f"Month: {datetime.now().strftime('%B %Y')}\n"
                report_content += f"Generated: {timestamp}\n\n"

                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(price * quantity), 0)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) >= DATE('now', 'start of month')
                ''')
                result = cursor.fetchone()
                items_sold = result[0] or 0
                monthly_revenue = result[1] or 0.0

                report_content += f"Items Sold This Month: {items_sold}\n"
                report_content += f"Monthly Revenue: \u00a3{monthly_revenue:.2f}\n\n"

                # Weekly breakdown
                report_content += "\u2500" * 40 + "\n"
                report_content += "Category Breakdown:\n"
                report_content += "\u2500" * 40 + "\n"
                cursor.execute('''
                    SELECT category, COUNT(*), SUM(price * quantity)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) >= DATE('now', 'start of month')
                    GROUP BY category
                    ORDER BY SUM(price * quantity) DESC
                ''')
                for row in cursor.fetchall():
                    cat, count, amount = row
                    report_content += f"  {cat or 'Uncategorized':<20} {count:>3} items  \u00a3{amount or 0:.2f}\n"

            elif report_type == 'total':
                report_content = "\u2550" * 60 + "\n"
                report_content += "        CHARITY SHOP - TOTAL REVENUE REPORT\n"
                report_content += "\u2550" * 60 + "\n\n"
                report_content += f"Generated: {timestamp}\n\n"

                # Total stats
                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(price * quantity), 0)
                    FROM charity_shop_stock WHERE sold = 1
                ''')
                result = cursor.fetchone()
                total_sold = result[0] or 0
                total_revenue = result[1] or 0.0

                cursor.execute('SELECT COUNT(*) FROM charity_shop_stock WHERE sold = 0')
                available = cursor.fetchone()[0] or 0

                cursor.execute('SELECT COALESCE(SUM(price * quantity), 0) FROM charity_shop_stock WHERE sold = 0')
                available_value = cursor.fetchone()[0] or 0.0

                report_content += "\u2500" * 40 + "\n"
                report_content += "SUMMARY\n"
                report_content += "\u2500" * 40 + "\n"
                report_content += f"Total Items Sold:      {total_sold}\n"
                report_content += f"Total Revenue:         \u00a3{total_revenue:.2f}\n"
                report_content += f"Items Still Available: {available}\n"
                report_content += f"Available Stock Value: \u00a3{available_value:.2f}\n\n"

                # Revenue by category
                report_content += "\u2500" * 40 + "\n"
                report_content += "Revenue by Category:\n"
                report_content += "\u2500" * 40 + "\n"
                cursor.execute('''
                    SELECT category, COUNT(*), SUM(price * quantity)
                    FROM charity_shop_stock WHERE sold = 1
                    GROUP BY category ORDER BY SUM(price * quantity) DESC
                ''')
                for row in cursor.fetchall():
                    cat, count, amount = row
                    report_content += f"  {cat or 'Uncategorized':<20} {count:>4} items  \u00a3{amount or 0:.2f}\n"

            elif report_type == 'stock':
                report_content = "\u2550" * 60 + "\n"
                report_content += "        CHARITY SHOP - STOCK STATUS REPORT\n"
                report_content += "\u2550" * 60 + "\n\n"
                report_content += f"Generated: {timestamp}\n\n"

                # Available stock by category
                cursor.execute('''
                    SELECT category, COUNT(*), SUM(quantity), SUM(price * quantity)
                    FROM charity_shop_stock WHERE sold = 0
                    GROUP BY category ORDER BY category
                ''')

                report_content += "\u2500" * 50 + "\n"
                report_content += "Available Stock by Category:\n"
                report_content += "\u2500" * 50 + "\n"
                report_content += f"{'Category':<20} {'Items':>6} {'Qty':>6} {'Value':>12}\n"
                report_content += "\u2500" * 50 + "\n"

                total_items = 0
                total_qty = 0
                total_value = 0.0
                for row in cursor.fetchall():
                    cat, items, qty, value = row
                    total_items += items or 0
                    total_qty += qty or 0
                    total_value += value or 0.0
                    report_content += f"{cat or 'Uncategorized':<20} {items or 0:>6} {qty or 0:>6} \u00a3{value or 0:>10.2f}\n"

                report_content += "\u2500" * 50 + "\n"
                report_content += f"{'TOTAL':<20} {total_items:>6} {total_qty:>6} \u00a3{total_value:>10.2f}\n"

            elif report_type == 'category':
                report_content = "\u2550" * 60 + "\n"
                report_content += "       CHARITY SHOP - CATEGORY ANALYSIS REPORT\n"
                report_content += "\u2550" * 60 + "\n\n"
                report_content += f"Generated: {timestamp}\n\n"

                # Get all categories with stats
                cursor.execute('''
                    SELECT
                        category,
                        COUNT(*) as total_items,
                        SUM(CASE WHEN sold = 1 THEN 1 ELSE 0 END) as sold_items,
                        SUM(CASE WHEN sold = 0 THEN 1 ELSE 0 END) as available_items,
                        SUM(CASE WHEN sold = 1 THEN price * quantity ELSE 0 END) as revenue,
                        SUM(CASE WHEN sold = 0 THEN price * quantity ELSE 0 END) as stock_value
                    FROM charity_shop_stock
                    GROUP BY category
                    ORDER BY revenue DESC
                ''')

                report_content += "\u2500" * 60 + "\n"
                report_content += f"{'Category':<15} {'Total':>6} {'Sold':>6} {'Avail':>6} {'Revenue':>12} {'Stock Val':>12}\n"
                report_content += "\u2500" * 60 + "\n"

                for row in cursor.fetchall():
                    cat, total, sold, avail, rev, stock_val = row
                    report_content += f"{(cat or 'Uncategorized'):<15} {total or 0:>6} {sold or 0:>6} {avail or 0:>6} \u00a3{rev or 0:>10.2f} \u00a3{stock_val or 0:>10.2f}\n"

            conn.close()

            # Store report content
            self.report_content = report_content

            # Display in report window if it exists
            if hasattr(self, 'report_text_widget') and self.report_text_widget.winfo_exists():
                self.report_text_widget.delete('1.0', tk.END)
                self.report_text_widget.insert('1.0', report_content)

            return report_content

        except Exception as e:
            error_msg = f"Error generating report: {e}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
            return ""

    def save_report_as_txt(self):
        """Save the current report as a TXT file"""
        if not hasattr(self, 'report_content') or not self.report_content:
            messagebox.showwarning("Warning", "No report to save. Please generate a report first.")
            return

        # Generate default filename
        report_type = self.report_type_var.get() if hasattr(self, 'report_type_var') else 'report'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"charity_shop_{report_type}_{timestamp}.txt"

        # Ask user for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_filename,
            title="Save Report As"
        )

        if not file_path:
            return  # User cancelled

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.report_content)
            messagebox.showinfo("Success", f"Report saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {e}")

    def open_report_in_window(self):
        """Open the current report in a separate window"""
        if not hasattr(self, 'report_content') or not self.report_content:
            messagebox.showwarning("Warning", "No report to display. Please generate a report first.")
            return

        # Create new window
        new_window = tk.Toplevel(self.root)
        report_type = self.report_type_var.get() if hasattr(self, 'report_type_var') else 'Report'
        new_window.title(f"Charity Shop Report - {report_type.title()}")
        new_window.geometry("700x600")

        # Header
        header_frame = ttk.Frame(new_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text=f"Charity Shop: {report_type.title()} Report",
            font=('Helvetica', 14, 'bold')
        ).pack(side=tk.LEFT)

        ttk.Label(
            header_frame,
            text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            font=('Helvetica', 10)
        ).pack(side=tk.RIGHT)

        # Report text
        text_frame = ttk.Frame(new_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=text_widget.yview)
        text_widget.pack(fill=tk.BOTH, expand=True)

        text_widget.insert('1.0', self.report_content)
        text_widget.config(state=tk.DISABLED)

        # Buttons
        button_frame = ttk.Frame(new_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(
            button_frame,
            text="Save as TXT",
            command=self.save_report_as_txt
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Email to Admin",
            command=self.email_report_to_admin
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Close",
            command=new_window.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def email_report_to_admin(self):
        """Email the current report to admin"""
        if not EMAIL_SERVICE_AVAILABLE:
            messagebox.showerror("Error", "Email service is not available.")
            return

        if not hasattr(self, 'report_content') or not self.report_content:
            messagebox.showwarning("Warning", "No report to email. Please generate a report first.")
            return

        # Get admin email from database
        admin_email = self._get_admin_email()
        if not admin_email:
            messagebox.showerror("Error", "Could not find admin email address in database.")
            return

        report_type = self.report_type_var.get() if hasattr(self, 'report_type_var') else 'Report'

        # Confirm before sending
        if not messagebox.askyesno(
            "Confirm Email",
            f"Send '{report_type.title()}' report to:\n{admin_email}?"
        ):
            return

        # Prepare email
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = f"Charity Shop Report: {report_type.title()} - {timestamp}"

        generated_by = 'System'
        if self.current_user:
            generated_by = self.current_user.get('username', 'System')

        body = f"""Charity Shop Report

Report Type: {report_type.title()}
Generated: {timestamp}
Generated By: {generated_by}

{'=' * 60}

{self.report_content}

{'=' * 60}

This report was automatically generated by the University Charity Shop System.
"""

        try:
            result = send_email(admin_email, subject, body)
            if result:
                messagebox.showinfo("Success", f"Report sent to {admin_email}")
            else:
                messagebox.showerror("Error", "Failed to send email. Please try again.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send email: {e}")

    def _get_admin_email(self):
        """Get admin email address from database"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
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
            logger.error(f"Error getting admin email: {e}")
            return None
