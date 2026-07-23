"""Barber Shop GUI - Finance & payment feature methods."""

from education_system.post_18.university_system.modules.domain.commerce.barber.gui.common import (
    tk, ttk, messagebox, logging, json,
    datetime, timedelta,
    _t, get_db_connection, log_activity,
    FINANCE_AVAILABLE,
)

logger = logging.getLogger(__name__)


class FinanceMixin:
    """Mixin providing finance & payment methods for BarberGUI."""

    def _update_finance_summary(self):
        """Update finance summary labels."""
        try:
            from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import TransactionManager
            today = datetime.now().strftime('%Y-%m-%d')

            daily_revenue = TransactionManager.get_daily_revenue(today)
            total_sales = daily_revenue.get('total_revenue') or 0
            self.daily_sales_label.config(text=f"Today's Sales: £{total_sales:.2f}")

            cash_revenue = daily_revenue.get('service_revenue') or 0
            self.cash_drawer_label.config(text=f"Cash Revenue: £{cash_revenue:.2f}")

            self.outstanding_label.config(text="Outstanding: £0.00")

        except Exception as e:
            logger.error(f"Error updating finance summary: {e}")

    def apply_discount(self):
        """Apply discount to transaction."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        discount_window = tk.Toplevel(self.parent)
        discount_window.title("Apply Discount")
        discount_window.geometry("350x250")
        discount_window.transient(self.parent)
        discount_window.grab_set()

        ttk.Label(discount_window, text=f"Apply Discount to {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(discount_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Discount Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(frame, values=['percentage', 'fixed_amount'], width=15)
        type_combo.set('percentage')
        type_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Value (% or £):").grid(row=1, column=0, sticky=tk.W, pady=5)
        value_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=value_var, width=10).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Reason:").grid(row=2, column=0, sticky=tk.W, pady=5)
        reason_var = tk.StringVar(value="Loyalty discount")
        ttk.Entry(frame, textvariable=reason_var, width=25).grid(row=2, column=1, pady=5)

        def apply():
            try:
                from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import (
                    AppointmentManager, DiscountManager
                )
                appt = AppointmentManager.get_appointment_by_number(appt_number)
                if appt:
                    DiscountManager.apply_discount(
                        appointment_id=appt['appointment_id'],
                        discount_type=type_combo.get(),
                        value=float(value_var.get()),
                        reason=reason_var.get(),
                        applied_by=self.current_user.get('username')
                    )
                    messagebox.showinfo("Success", "Discount applied!")
                    discount_window.destroy()
                    self._load_appointments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(discount_window, text="Apply Discount", command=apply).pack(pady=10)

    def issue_refund(self):
        """Issue refund."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        refund_window = tk.Toplevel(self.parent)
        refund_window.title("Issue Refund")
        refund_window.geometry("400x300")
        refund_window.transient(self.parent)
        refund_window.grab_set()

        ttk.Label(refund_window, text=f"Issue Refund for {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(refund_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Refund Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(frame, values=['full', 'partial'], width=15)
        type_combo.set('full')
        type_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Amount (for partial):").grid(row=1, column=0, sticky=tk.W, pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(frame, textvariable=amount_var, width=15).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Reason:").grid(row=2, column=0, sticky=tk.W, pady=5)
        reason_text = tk.Text(frame, height=3, width=25)
        reason_text.grid(row=2, column=1, pady=5)

        def process_refund():
            try:
                from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import (
                    AppointmentManager, RefundManager
                )
                appt = AppointmentManager.get_appointment_by_number(appt_number)
                if appt:
                    amount = None
                    if type_combo.get() == 'partial':
                        amount = float(amount_var.get())

                    RefundManager.issue_refund(
                        appointment_id=appt['appointment_id'],
                        refund_type=type_combo.get(),
                        amount=amount,
                        reason=reason_text.get('1.0', tk.END).strip(),
                        processed_by=self.current_user.get('username')
                    )
                    messagebox.showinfo("Success", "Refund processed!")
                    refund_window.destroy()
                    self._load_appointments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(refund_window, text="Process Refund", command=process_refund).pack(pady=10)

    def view_daily_sales(self):
        """View daily sales."""
        sales_window = tk.Toplevel(self.parent)
        sales_window.title("Daily Sales Report")
        sales_window.geometry("600x450")
        sales_window.transient(self.parent)

        # Date selection
        date_frame = ttk.Frame(sales_window, padding="10")
        date_frame.pack(fill=tk.X)

        ttk.Label(date_frame, text="Date:").pack(side=tk.LEFT)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(date_frame, textvariable=date_var, width=12).pack(side=tk.LEFT, padx=5)

        # Sales display
        sales_text = tk.Text(sales_window, wrap=tk.WORD, height=20)
        scrollbar = ttk.Scrollbar(sales_window, orient=tk.VERTICAL, command=sales_text.yview)
        sales_text.configure(yscrollcommand=scrollbar.set)

        sales_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_sales():
            sales_text.delete('1.0', tk.END)
            try:
                from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import TransactionManager
                revenue_data = TransactionManager.get_daily_revenue(date_var.get())

                report = "=== Daily Sales Report ===\n"
                report += f"Date: {date_var.get()}\n\n"
                report += f"Transactions: {revenue_data['transaction_count'] or 0}\n"
                report += f"Service Revenue: £{(revenue_data['service_revenue'] or 0):.2f}\n"
                report += f"Tips: £{(revenue_data['tips'] or 0):.2f}\n"
                report += f"Total Revenue: £{(revenue_data['total_revenue'] or 0):.2f}\n"

                sales_text.insert('1.0', report)
            except Exception as e:
                sales_text.insert('1.0', f"Error: {e}")

        ttk.Button(date_frame, text="Load", command=load_sales).pack(side=tk.LEFT, padx=10)
        load_sales()

    def generate_financial_report(self):
        """Generate financial report."""
        report_window = tk.Toplevel(self.parent)
        report_window.title("Financial Report")
        report_window.geometry("700x500")
        report_window.transient(self.parent)

        # Options
        options_frame = ttk.Frame(report_window, padding="10")
        options_frame.pack(fill=tk.X)

        ttk.Label(options_frame, text="From:").pack(side=tk.LEFT)
        from_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(options_frame, text="To:").pack(side=tk.LEFT, padx=(10, 0))
        to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=to_var, width=12).pack(side=tk.LEFT, padx=5)

        # Report display
        report_text = tk.Text(report_window, wrap=tk.WORD, height=25)
        scrollbar = ttk.Scrollbar(report_window, orient=tk.VERTICAL, command=report_text.yview)
        report_text.configure(yscrollcommand=scrollbar.set)

        report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def generate():
            report_text.delete('1.0', tk.END)
            try:
                from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import ReportManager

                sales_data = ReportManager.generate_sales_report(from_var.get(), to_var.get())

                report = "=== Financial Report ===\n\n"
                report += f"Period: {sales_data['period']['start']} to {sales_data['period']['end']}\n"
                report += f"Generated: {sales_data['generated_at']}\n\n"

                summary = sales_data.get('summary', {})
                report += "SUMMARY:\n"
                report += f"  Total Appointments: {summary.get('total_appointments') or 0}\n"
                report += f"  Service Revenue: £{(summary.get('service_revenue') or 0):.2f}\n"
                report += f"  Total Tips: £{(summary.get('total_tips') or 0):.2f}\n"
                report += f"  Avg Service Value: £{(summary.get('avg_service_value') or 0):.2f}\n"
                total = (summary.get('service_revenue') or 0) + (summary.get('total_tips') or 0)
                report += f"  TOTAL REVENUE: £{total:.2f}\n\n"

                report += "REVENUE BY SERVICE:\n"
                by_service = sales_data.get('by_service', [])
                if by_service:
                    for svc in by_service:
                        service_name = svc.get('service_name', 'Unknown')
                        count = svc.get('count') or 0
                        revenue = svc.get('revenue') or 0
                        report += f"  {service_name}: {count} bookings, £{revenue:.2f}\n"
                else:
                    report += "  No service data available\n"

                report += "\nREVENUE BY STAFF:\n"
                by_staff = sales_data.get('by_staff', [])
                if by_staff:
                    for staff in by_staff:
                        staff_name = staff.get('staff_name', 'Unknown')
                        appointments = staff.get('appointments') or 0
                        revenue = staff.get('revenue') or 0
                        tips = staff.get('tips') or 0
                        report += f"  {staff_name}: {appointments} appointments, "
                        report += f"£{revenue:.2f} revenue, £{tips:.2f} tips\n"
                else:
                    report += "  No staff data available\n"

                report_text.insert('1.0', report)
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                logger.error(f"Error generating financial report: {e}\n{error_detail}")
                report_text.insert('1.0', f"Error generating report: {e}")

        ttk.Button(options_frame, text="Generate", command=generate).pack(side=tk.LEFT, padx=20)
        generate()

    def track_cash_drawer(self):
        """Track cash drawer."""
        drawer_window = tk.Toplevel(self.parent)
        drawer_window.title("Cash Drawer")
        drawer_window.geometry("500x400")
        drawer_window.transient(self.parent)
        drawer_window.grab_set()

        ttk.Label(drawer_window, text="Cash Drawer Management",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        # Current balance
        try:
            from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import CashDrawerManager
            balance = CashDrawerManager.get_balance()
        except Exception:
            balance = 0.0

        balance_label = ttk.Label(drawer_window, text=f"Current Balance: £{balance:.2f}",
                                 font=('Helvetica', 12, 'bold'))
        balance_label.pack(pady=10)

        # Actions
        frame = ttk.Frame(drawer_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Action:").grid(row=0, column=0, sticky=tk.W, pady=5)
        action_combo = ttk.Combobox(frame, values=['add', 'remove', 'count'], width=15)
        action_combo.set('add')
        action_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Amount (£):").grid(row=1, column=0, sticky=tk.W, pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(frame, textvariable=amount_var, width=15).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Note:").grid(row=2, column=0, sticky=tk.W, pady=5)
        note_var = tk.StringVar()
        ttk.Entry(frame, textvariable=note_var, width=30).grid(row=2, column=1, pady=5)

        def execute_action():
            try:
                from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import CashDrawerManager
                action = action_combo.get()
                amount = float(amount_var.get()) if amount_var.get() else 0

                if action == 'add':
                    drawer_id = CashDrawerManager.open_drawer(
                        opening_amount=amount,
                        opened_by=self.current_user.get('username', 'System')
                    )
                    messagebox.showinfo("Success", f"Drawer opened with £{amount:.2f}\nNote: {note_var.get()}")
                elif action == 'remove':
                    messagebox.showinfo("Info", "Use 'Close Drawer' function to reconcile cash at end of shift")
                elif action == 'count':
                    messagebox.showinfo("Info", "Use 'Close Drawer' function to record final count")

                balance_label.config(text=f"Current Balance: £{amount:.2f}")
                self._update_finance_summary()

            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Execute", command=execute_action).grid(row=3, column=0, columnspan=2, pady=20)

    def create_gift_card(self):
        """Create gift card."""
        gift_window = tk.Toplevel(self.parent)
        gift_window.title("Create Gift Card")
        gift_window.geometry("400x350")
        gift_window.transient(self.parent)
        gift_window.grab_set()

        ttk.Label(gift_window, text="Create Gift Card",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(gift_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Value (£):").grid(row=0, column=0, sticky=tk.W, pady=5)
        value_var = tk.StringVar(value="50")
        ttk.Entry(frame, textvariable=value_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Recipient Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=25).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Recipient Email:").grid(row=2, column=0, sticky=tk.W, pady=5)
        email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=email_var, width=25).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Message:").grid(row=3, column=0, sticky=tk.W, pady=5)
        msg_text = tk.Text(frame, height=3, width=25)
        msg_text.grid(row=3, column=1, pady=5)

        def create():
            try:
                from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import GiftCardManager
                card_code = GiftCardManager.create_card(
                    value=float(value_var.get()),
                    recipient_name=name_var.get().strip(),
                    recipient_email=email_var.get().strip(),
                    message=msg_text.get('1.0', tk.END).strip(),
                    created_by=self.current_user.get('username')
                )
                messagebox.showinfo("Success", f"Gift card created!\nCode: {card_code}")
                gift_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(gift_window, text="Create Gift Card", command=create).pack(pady=10)

    def redeem_gift_card(self):
        """Redeem gift card."""
        redeem_window = tk.Toplevel(self.parent)
        redeem_window.title("Redeem Gift Card")
        redeem_window.geometry("400x250")
        redeem_window.transient(self.parent)
        redeem_window.grab_set()

        ttk.Label(redeem_window, text="Redeem Gift Card",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(redeem_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Gift Card Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        code_var = tk.StringVar()
        ttk.Entry(frame, textvariable=code_var, width=20).grid(row=0, column=1, pady=5)

        balance_label = ttk.Label(frame, text="Balance: --")
        balance_label.grid(row=1, column=0, columnspan=2, pady=10)

        def check_balance():
            try:
                from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import GiftCardManager
                card = GiftCardManager.get_gift_card(code_var.get().strip())
                if card:
                    balance_label.config(text=f"Balance: £{card['current_balance']:.2f}")
                else:
                    balance_label.config(text="Invalid card code")
            except Exception as e:
                balance_label.config(text=f"Error: {e}")

        ttk.Button(frame, text="Check Balance", command=check_balance).grid(row=2, column=0, columnspan=2, pady=5)

        ttk.Label(frame, text="Amount to Redeem (£):").grid(row=3, column=0, sticky=tk.W, pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(frame, textvariable=amount_var, width=15).grid(row=3, column=1, pady=5)

        def redeem():
            try:
                from education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core import GiftCardManager
                success, message = GiftCardManager.redeem_gift_card(
                    code=code_var.get().strip(),
                    amount=float(amount_var.get()),
                    redeemed_by=self.current_user.get('username')
                )
                if success:
                    messagebox.showinfo("Success", message)
                    redeem_window.destroy()
                else:
                    messagebox.showerror("Error", message)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Redeem", command=redeem).grid(row=4, column=0, columnspan=2, pady=10)

    def view_outstanding_payments(self):
        """View outstanding payments."""
        outstanding_window = tk.Toplevel(self.parent)
        outstanding_window.title("Outstanding Payments")
        outstanding_window.geometry("700x400")
        outstanding_window.transient(self.parent)

        columns = ('appt', 'date', 'customer', 'service', 'amount', 'status')
        tree = ttk.Treeview(outstanding_window, columns=columns, show='headings', height=15)

        tree.heading('appt', text='Appointment')
        tree.heading('date', text='Date')
        tree.heading('customer', text='Customer')
        tree.heading('service', text='Service')
        tree.heading('amount', text='Amount')
        tree.heading('status', text='Status')

        for col in columns:
            tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(outstanding_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT appointment_id, appointment_date, customer_name, service_name, price, payment_status
                    FROM barber_appointments
                    WHERE payment_status IN ('pending', 'unpaid') AND status != 'cancelled'
                    ORDER BY appointment_date DESC
                ''')
                for row in cursor.fetchall():
                    tree.insert('', tk.END, values=(
                        row[0], row[1], row[2], row[3],
                        f"£{row[4]:.2f}", row[5]
                    ))
        except Exception as e:
            logger.error(f"Error loading outstanding: {e}")
