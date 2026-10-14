"""Methods _process_library_refund through load_book_costs."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LibraryFinanceManager:
    def _process_library_refund(self, student_id, loan_id, refund_amount, refund_method, refund_reason, book_title):
        """Process a library fine refund with finance integration"""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_date = datetime.now().strftime('%Y-%m-%d')

            # Handle finance account refund
            if refund_method == "Student Finance Account":
                try:
                    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
                        ensure_student_finance_account_exists,
                        top_up_student_finance_account,
                        get_student_finance_account_balance
                    )

                    ensure_student_finance_account_exists(student_id)

                    result = top_up_student_finance_account(
                        student_id=student_id,
                        amount=refund_amount,
                        description=f"Library fine refund (Loan {loan_id})",
                        payment_method="Refund Credit",
                        processed_by=get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
                    )

                    if not result or not result.get('success'):
                        conn.close()
                        return False

                except ImportError:
                    messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.not_available', default="Not Available"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.finance_account_integration_not_available', default="Finance account integration not available"))
                    conn.close()
                    return False

            # Record refund in finance system
            try:
                from education_system.systems.university.domains.finance.infrastructure.finance_integration import record_refund_to_finance

                refund_id = record_refund_to_finance(
                    student_id=student_id,
                    refund_amount=refund_amount,
                    original_payment_id=None,
                    refund_reason=refund_reason,
                    refund_type="library_fine",
                    transaction_source="Library",
                    transaction_ref=f"FINE_REFUND_{loan_id}",
                    refund_method=refund_method.lower().replace(' ', '_'),
                    currency="GBP",
                    requested_by="Library Manager",
                    notes=f"Book: {book_title}"
                )
            except ImportError:
                refund_id = None

            # Update loan notes
            cursor.execute('SELECT notes FROM book_loans WHERE loan_id = ?', (loan_id,))
            result = cursor.fetchone()
            current_notes = result[0] if result else ""

            refund_note = f"Refund of £{refund_amount:.2f} processed on {current_date} via {refund_method}. Reason: {refund_reason}"
            updated_notes = f"{current_notes}; {refund_note}" if current_notes else refund_note

            cursor.execute('UPDATE book_loans SET notes = ? WHERE loan_id = ?', (updated_notes, loan_id))

            conn.commit()
            conn.close()

            # Send refund receipt email
            user_info = self.get_user_email(student_id)
            if user_info:
                self._send_library_refund_email(user_info, refund_amount, refund_method, book_title, refund_reason, loan_id)

            return True

        except Exception as e:
            print(f"Error processing library refund: {e}")
            import traceback
            traceback.print_exc()
            if 'conn' in locals():
                conn.close()
            return False

    def _send_library_refund_email(self, user_info, refund_amount, refund_method, book_title, refund_reason, loan_id):
        """Send refund receipt email"""
        try:
            if not user_info or not user_info.get('email'):
                return False

            # Render email from template
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            receipt_number = f"LIB-REFUND-{loan_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            refund_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            refund_message = f"Your student finance account has been credited with £{refund_amount:.2f}." if refund_method == "Student Finance Account" else f"Your refund has been processed using {refund_method}."

            subject, body = render_template('library/refund_receipt', {
                'student_name': user_info['full_name'],
                'receipt_number': receipt_number,
                'refund_date': refund_date,
                'refund_amount': f'{refund_amount:.2f}',
                'refund_method': refund_method,
                'book_title': book_title,
                'refund_reason': refund_reason,
                'refund_message': refund_message
            })

            # Fallback if template not found
            if not subject or not body:
                subject = "Library Fine Refund Receipt"
                body = f"""Dear {user_info['full_name']},

This email confirms your library fine refund has been processed.

REFUND DETAILS
Receipt Number:  {receipt_number}
Refund Date:     {refund_date}
Refund Amount:   £{refund_amount:.2f}
Refund Method:   {refund_method}

BOOK DETAILS:
Book Title:      {book_title}

REASON:
{refund_reason}

{refund_message}

If you have any questions about this refund, please contact the library.

Best regards,
University Library System
"""

            send_email_as_system(
                recipient_email=user_info['email'],
                subject=subject,
                body=body,
                system_name="Library System"
            )
            return True

        except Exception as e:
            print(f"Error sending refund email: {e}")
            return False

    def _render_revenue_report(self, report_text, payment_count, total_revenue,
                               avg_payment, monthly_data, start_date, end_date):
        """Draw the revenue report as headline cards plus a monthly table."""
        host = getattr(self, "revenue_stats_host", None)
        if host is None:
            return
        for child in host.winfo_children():
            child.destroy()

        tk.Label(host, text=f"Period: {start_date} to {end_date}",
                 bg='white', fg='#6b7280', font=('Arial', 9)).pack(anchor='w')

        cards = tk.Frame(host, bg='white')
        cards.pack(fill='x', pady=(6, 10))
        figures = [
            (f"{payment_count:,}", "Payments Received", self.colors['info']),
            (f"£{total_revenue:,.2f}", "Total Revenue", self.colors['success']),
            (f"£{avg_payment:,.2f}", "Average Payment", self.colors['secondary']),
        ]
        for col, (value, label, colour) in enumerate(figures):
            cards.columnconfigure(col, weight=1, uniform='rev')
            cell = tk.Frame(cards, bg='white', highlightbackground='#e5e7eb',
                            highlightthickness=1)
            cell.grid(row=0, column=col, sticky='ew', padx=4)
            tk.Label(cell, text=value, bg='white', fg=colour,
                     font=('Arial', 17, 'bold')).pack(pady=(10, 0))
            tk.Label(cell, text=label, bg='white', fg='#6b7280',
                     font=('Arial', 9)).pack(pady=(0, 10))

        if not monthly_data:
            tk.Label(host, text="No payments in this period.", bg='white',
                     fg='#6b7280', font=('Arial', 10, 'italic')).pack(anchor='w')
            return

        table = tk.Frame(host, bg='white')
        table.pack(fill='both', expand=True)
        columns = ('Month', 'Payments', 'Revenue')
        tree = ttk.Treeview(table, columns=columns, show='headings', height=8)
        for col, width, anchor in (('Month', 140, 'w'), ('Payments', 110, 'e'),
                                   ('Revenue', 140, 'e')):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor=anchor)
        tree.tag_configure('odd', background='#f7f9fb')
        for i, (month, payments, revenue) in enumerate(monthly_data):
            tree.insert('', 'end', tags=('odd',) if i % 2 else (),
                        values=(month, f"{payments:,}", f"£{revenue:,.2f}"))
        scroll = ttk.Scrollbar(table, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

    def generate_revenue_report(self):
        """Generate revenue report for specified date range"""
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.please_enter_both_start_and_end_dates', default="Please enter both start and end dates."))
            return

        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Query from payments table for library source
            cursor.execute('''
                SELECT COUNT(*) as payment_count,
                       SUM(amount) as total_revenue, AVG(amount) as avg_payment
                FROM payments
                WHERE source_type = 'library'
                AND DATE(payment_date) BETWEEN DATE(?) AND DATE(?)
            ''', (start_date, end_date))

            stats = cursor.fetchone()
            payment_count = stats[0] or 0
            total_revenue = stats[1] or 0.0
            avg_payment = stats[2] or 0.0

            cursor.execute('''
                SELECT strftime('%Y-%m', payment_date) as month,
                       COUNT(*) as payments, SUM(amount) as revenue
                FROM payments
                WHERE source_type = 'library'
                AND DATE(payment_date) BETWEEN DATE(?) AND DATE(?)
                GROUP BY month ORDER BY month DESC
            ''', (start_date, end_date))

            monthly_data = cursor.fetchall()
            conn.close()

            report = f"""
LIBRARY FINE REVENUE REPORT
Period: {start_date} to {end_date}
{'='*60}

SUMMARY STATISTICS:
  Total Payments Received:    {payment_count:,}
  Total Revenue:              £{total_revenue:,.2f}
  Average Payment:            £{avg_payment:,.2f}

MONTHLY BREAKDOWN:
{'='*60}
Month          Payments      Revenue
{'-'*60}
"""
            for month, payments, revenue in monthly_data:
                report += f"{month}         {payments:>8}      £{revenue:>10,.2f}\n"
            report += f"{'='*60}\n"
            # The text form is still what Email Report and Export CSV send,
            # so it is built either way; only the on-screen view changes.
            self._last_revenue_report = report
            self._render_revenue_report(
                report, payment_count, total_revenue, avg_payment, monthly_data,
                start_date, end_date)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate revenue report:\n{str(e)}")

    def email_revenue_report_to_admin(self):
        """Email the revenue report to admin users"""
        if not hasattr(self, '_last_revenue_report') or not self._last_revenue_report:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.no_report', default="No Report"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.please_generate_a_report_first', default="Please generate a report first."))
            return

        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email
            from education_system.systems.university.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' AND email IS NOT NULL AND email != ''")
            admins = cursor.fetchall()
            conn.close()

            if not admins:
                messagebox.showinfo(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.no_admins', default="No Admins"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.no_admin_email_addresses_found', default="No admin email addresses found."))
                return

            sent = 0
            for (email,) in admins:
                try:
                    send_email(
                        recipient_email=email,
                        subject="Library Fine Revenue Report",
                        body=self._last_revenue_report
                    )
                    sent += 1
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            if sent > 0:
                messagebox.showinfo(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.email_sent', default="Email Sent"), f"Report emailed to {sent} admin(s).")
            else:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.email_failed', default="Email Failed"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.could_not_send_email_to_any_admin', default="Could not send email to any admin."))

        except Exception as e:
            messagebox.showerror(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.error', default="Error"), f"Failed to email report: {e}")

    def show_revenue_charts(self):
        """Display revenue charts"""
        # Read through _shared, not as a bare global: finance_shared resolves
        # matplotlib on first access, so these names are absent from the
        # globals() splice at the top of this module.
        if not _shared.MATPLOTLIB_AVAILABLE:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.not_available', default="Not Available"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.matplotlib_is_not_available_for_charts', default="Matplotlib is not available for charts."))
            return

        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.please_enter_date_range_first', default="Please enter date range first."))
            return

        try:
            for widget in self.revenue_chart_frame.winfo_children():
                widget.destroy()

            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT strftime('%Y-%m', payment_date) as month, SUM(amount) as revenue
                FROM payments
                WHERE source_type = 'library'
                AND payment_date BETWEEN ? AND ?
                GROUP BY month ORDER BY month ASC
            ''', (start_date, end_date))

            monthly_data = cursor.fetchall()
            conn.close()

            if not monthly_data:
                messagebox.showinfo(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.no_data', default="No Data"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.no_revenue_data_found_for_the_specified_period', default="No revenue data found for the specified period."))
                return

            fig = _shared.Figure(figsize=(10, 6), dpi=100)
            ax1 = fig.add_subplot(1, 2, 1)
            months = [item[0] for item in monthly_data]
            revenues = [item[1] for item in monthly_data]

            ax1.bar(range(len(months)), revenues, color=self.colors['library'])
            ax1.set_xticks(range(len(months)))
            ax1.set_xticklabels(months, rotation=45, ha='right')
            ax1.set_ylabel('Revenue (£)', fontweight='bold')
            ax1.set_title('Monthly Library Fine Revenue', fontsize=12, fontweight='bold')

            ax2 = fig.add_subplot(1, 2, 2)
            ax2.plot(range(len(months)), revenues, marker='o', linewidth=2, color=self.colors['library'])
            ax2.set_xticks(range(len(months)))
            ax2.set_xticklabels(months, rotation=45, ha='right')
            ax2.set_ylabel('Revenue (£)', fontweight='bold')
            ax2.set_title('Revenue Trend', fontsize=12, fontweight='bold')

            fig.tight_layout()
            canvas = _shared.FigureCanvasTkAgg(fig, master=self.revenue_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to create charts:\n{str(e)}")

    def export_revenue_csv(self):
        """Export revenue data to CSV"""
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_library_refund.dialogs.please_enter_date_range_first', default="Please enter date range first."))
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"library_revenue_{datetime.now().strftime('%Y%m%d')}.csv"
            )
            if not filename:
                return

            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT p.payment_date, p.student_id, pa.amount, p.payment_method, p.notes
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3 AND p.payment_date BETWEEN ? AND ?
                ORDER BY p.payment_date DESC
            ''', (start_date, end_date))

            data = cursor.fetchall()
            conn.close()

            import csv
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Date', 'Student ID', 'Amount', 'Payment Method', 'Notes'])
                for row in data:
                    writer.writerow(row)

            messagebox.showinfo(_("common.success"), f"Revenue data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to export data:\n{str(e)}")

    def load_book_costs(self):
        """Load book costs from database"""
        try:
            for item in self.costs_tree.get_children():
                self.costs_tree.delete(item)

            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(books)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'purchase_price' not in columns:
                cursor.execute('ALTER TABLE books ADD COLUMN purchase_price REAL DEFAULT 0.0')
                cursor.execute('ALTER TABLE books ADD COLUMN purchase_date TEXT')
                cursor.execute('ALTER TABLE books ADD COLUMN supplier TEXT')
                cursor.execute('ALTER TABLE books ADD COLUMN quantity INTEGER DEFAULT 1')
                conn.commit()

            cursor.execute('''
                SELECT book_id, title, author, isbn, COALESCE(purchase_price, 0.0),
                       purchase_date, supplier, COALESCE(quantity, 1)
                FROM books ORDER BY title
            ''')

            books = cursor.fetchall()
            total_cost = 0
            total_books = 0

            for book in books:
                book_id, title, author, isbn, price, date, supplier, qty = book
                total_cost += price * qty
                total_books += qty
                self.costs_tree.insert('', 'end', values=(
                    book_id, (title[:40] if title else 'N/A'), (author[:30] if author else 'N/A'),
                    isbn or 'N/A', f"£{price:.2f}", date or 'N/A', supplier or 'N/A', qty
                ))

            conn.close()
            self.costs_summary_label.config(text=f"Total Book Investment: £{total_cost:,.2f} | Total Books: {total_books}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load book costs:\n{str(e)}")
