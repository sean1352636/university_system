"""Payment analytics and email reminder functionality"""

from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, simpledialog, _, datetime, get_connection, get_auth,
)
from tkinter.scrolledtext import ScrolledText


class AnalyticsEmailMixin:
    """Mixin for payment analytics and email reminders"""

    def show_payment_analytics(self):
        """Show payment analytics"""
        try:
            # Call the original function
            self.analyze_payment_patterns()
            self.update_status(_("finance_gui.transaction_manager.payment_analytics_generated"))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_payment_analytics", error=str(e)))


    def send_payment_email_reminders(self):
        """Send email reminders for payments and financial matters"""
        if not hasattr(self.root, 'tk'):
            messagebox.showinfo(_("finance_gui.messages.success"), "Payment reminder workflow initialized.")
            return

        # Create email reminder dialog
        email_window = tk.Toplevel(self.root)
        email_window.title(_("finance_gui.transaction_manager.email_reminders_title"))
        email_window.geometry("750x680")
        email_window.transient(self.root)
        email_window.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(email_window)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Email type selection frame
        type_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.email_type_frame"), padding=10)
        type_frame.pack(fill='x', padx=10, pady=10)

        email_type_var = tk.StringVar(value="overdue_payment")
        email_types = [
            ("overdue_payment", _("finance_gui.transaction_manager.email_type_overdue")),
            ("upcoming_payment", _("finance_gui.transaction_manager.email_type_upcoming")),
            ("payment_confirmation", _("finance_gui.transaction_manager.email_type_confirmation")),
            ("fee_notification", _("finance_gui.transaction_manager.email_type_fee_notification")),
            ("scholarship_update", _("finance_gui.transaction_manager.email_type_scholarship")),
            ("financial_hold", _("finance_gui.transaction_manager.email_type_financial_hold")),
            ("custom", _("finance_gui.transaction_manager.email_type_custom"))
        ]

        for i, (value, text) in enumerate(email_types):
            ttk.Radiobutton(type_frame, text=text, variable=email_type_var,
                           value=value).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=2)

        # Recipient selection frame
        recipient_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.recipients_frame"), padding=10)
        recipient_frame.pack(fill='x', padx=10, pady=10)

        recipient_var = tk.StringVar(value="overdue_students")
        recipient_options = [
            ("overdue_students", _("finance_gui.transaction_manager.recipient_overdue")),
            ("upcoming_due", _("finance_gui.transaction_manager.recipient_upcoming")),
            ("all_students", _("finance_gui.transaction_manager.recipient_all")),
            ("financial_aid", _("finance_gui.transaction_manager.recipient_financial_aid")),
            ("scholarship_recipients", _("finance_gui.transaction_manager.recipient_scholarship")),
            ("custom", _("finance_gui.transaction_manager.recipient_custom"))
        ]

        for i, (value, text) in enumerate(recipient_options):
            ttk.Radiobutton(recipient_frame, text=text, variable=recipient_var,
                           value=value).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=2)

        # Message composition frame
        message_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.message_frame"), padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Subject line
        ttk.Label(message_frame, text=_("finance_gui.transaction_manager.subject_label")).pack(anchor='w')
        subject_var = tk.StringVar(value=_("finance_gui.transaction_manager.subject_default"))
        subject_entry = ttk.Entry(message_frame, textvariable=subject_var, width=80)
        subject_entry.pack(fill='x', pady=(0, 10))

        # Message body
        ttk.Label(message_frame, text=_("finance_gui.transaction_manager.message_label")).pack(anchor='w')
        message_text = ScrolledText(message_frame, height=12, width=80)
        message_text.pack(fill='both', expand=True)

        # Default message templates
        def update_default_message(*args):
            email_type = email_type_var.get()
            template_map = {
                "overdue_payment": "overdue_payment_notice",
                "upcoming_payment": "upcoming_payment_reminder",
                "payment_confirmation": "payment_confirmation_notice",
                "fee_notification": "fee_notification",
                "scholarship_update": "scholarship_update_notification",
                "financial_hold": "financial_hold_notice"
            }

            if email_type in template_map:
                try:
                    from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
                    _, default_message = render_template(template_map[email_type], {})
                except Exception:
                    default_message = ""
            else:
                default_message = _("finance_gui.transaction_manager.default_custom_message")

            message_text.delete('1.0', tk.END)
            message_text.insert('1.0', default_message)

        email_type_var.trace('w', update_default_message)
        update_default_message()  # Set initial message

        # Buttons frame
        buttons_frame = ttk.Frame(scrollable_frame)
        buttons_frame.pack(fill='x', padx=10, pady=10)

        def preview_recipients():
            """Preview the list of recipients"""
            try:
                recipient_type = recipient_var.get()
                recipients = self._get_finance_email_recipients(recipient_type)

                preview_window = tk.Toplevel(email_window)
                preview_window.title(_("finance_gui.transaction_manager.recipients_preview_title"))
                preview_window.geometry("500x400")
                preview_window.transient(email_window)

                ttk.Label(preview_window, text=_("finance_gui.transaction_manager.recipients_count", count=len(recipients))).pack(anchor='w', padx=10, pady=10)

                recipients_list = tk.Listbox(preview_window, height=20)
                recipients_list.pack(fill='both', expand=True, padx=10, pady=(0, 10))

                for recipient in recipients:
                    display_text = f"{recipient['name']} ({recipient['email']})"
                    if 'balance' in recipient:
                        display_text += f" - Balance: £{recipient['balance']:.2f}"
                    recipients_list.insert(tk.END, display_text)

                ttk.Button(preview_window, text=_("finance_gui.transaction_manager.btn_close"),
                          command=preview_window.destroy).pack(pady=10)

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_preview_recipients", error=str(e)))

        def send_emails():
            """Send the email reminders"""
            try:
                email_type = email_type_var.get()
                recipient_type = recipient_var.get()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()

                if not subject or not message:
                    messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.enter_subject_message"))
                    return

                # Get recipient list
                recipients = self._get_finance_email_recipients(recipient_type)

                if not recipients:
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.no_recipients_found"))
                    return

                # Try to send emails via email GUI
                success = self._send_finance_emails_via_gui(recipients, subject, message, email_type)

                if success:
                    email_window.destroy()
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.emails_sent_success", count=len(recipients)))
                else:
                    # Fallback: show email details for manual sending
                    self._show_finance_email_fallback_dialog(recipients, subject, message)

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_send_emails", error=str(e)))

        ttk.Button(buttons_frame, text=_("finance_gui.transaction_manager.preview_recipients"),
                  command=preview_recipients).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_("finance_gui.transaction_manager.send_emails"),
                  command=send_emails).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_("finance_gui.transaction_manager.btn_cancel"),
                  command=email_window.destroy).pack(side='right')


    def _get_finance_email_recipients(self, recipient_type):
        """Get email recipients based on financial criteria"""
        recipients = []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if recipient_type == "overdue_students":
                # Students with overdue payments (more than 30 days past due)
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.due_date < date('now', '-30 days') AND f.status != 'paid'
                  AND s.email_address IS NOT NULL AND s.email_address != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')

            elif recipient_type == "upcoming_due":
                # Students with payments due in the next 7 days
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.due_date BETWEEN date('now') AND date('now', '+7 days')
                  AND f.status != 'paid' AND s.email_address IS NOT NULL AND s.email_address != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')

            elif recipient_type == "all_students":
                # All students with outstanding balances
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address,
                       COALESCE(SUM(f.amount), 0) as balance
                FROM students s
                LEFT JOIN student_fees f ON s.student_id = f.student_id
                WHERE f.status != 'paid' AND s.email_address IS NOT NULL AND s.email_address != ''
                GROUP BY s.student_id
                HAVING balance > 0
                ''')

            elif recipient_type == "financial_aid":
                # Financial aid recipients
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address
                FROM students s
                JOIN financial_aid fa ON s.student_id = fa.student_id
                WHERE fa.status = 'Approved' AND s.email_address IS NOT NULL AND s.email_address != ''
                ''')

            elif recipient_type == "scholarship_recipients":
                # Scholarship recipients
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address
                FROM students s
                JOIN scholarships sch ON s.student_id = sch.student_id
                WHERE sch.status = 'Active' AND s.email_address IS NOT NULL AND s.email_address != ''
                ''')

            for row in cursor.fetchall():
                recipient_data = {
                    'student_id': row[0],
                    'name': f"{row[1]} {row[2]}",
                    'email': row[3]
                }
                if len(row) > 4:  # Balance information available
                    recipient_data['balance'] = row[4]
                recipients.append(recipient_data)

            conn.close()

        except Exception as e:
            print(f"Error getting finance email recipients: {e}")

        return recipients


    def _send_finance_emails_via_gui(self, recipients, subject, message, email_type):
        """Try to send emails via email service"""
        try:
            # Try to import and use email service directly
            from education_system.post_18.university_system.infrastructure.email.email_service import send_email

            # Send emails through email service
            for recipient in recipients:
                personalized_message = message.replace("[Student Name]", recipient['name'])
                if 'balance' in recipient:
                    personalized_message = personalized_message.replace("[Balance]", f"£{recipient['balance']:.2f}")

                send_email(
                    recipient_email=recipient['email'],
                    subject=subject,
                    body=personalized_message
                )

            return True

        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending finance emails: {e}")
            return False


    def _show_finance_email_fallback_dialog(self, recipients, subject, message):
        """Show fallback dialog with email details for manual sending"""
        fallback_window = tk.Toplevel(self.root)
        fallback_window.title(_("finance_gui.transaction_manager.email_fallback_title"))
        fallback_window.geometry("700x500")
        fallback_window.transient(self.root)

        ttk.Label(fallback_window, text=_("finance_gui.transaction_manager.email_gui_unavailable"),
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

        # Email details
        details_frame = ttk.LabelFrame(fallback_window, text=_("finance_gui.transaction_manager.email_details_frame"), padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        details_text = ScrolledText(details_frame, height=20, width=80)
        details_text.pack(fill='both', expand=True)

        email_details = f"Subject: {subject}\n\n"
        email_details += f"Recipients ({len(recipients)}):\n"
        for recipient in recipients:
            email_details += f"  - {recipient['name']} ({recipient['email']})"
            if 'balance' in recipient:
                email_details += f" - Balance: £{recipient['balance']:.2f}"
            email_details += "\n"
        email_details += f"\nMessage:\n{message}"

        details_text.insert('1.0', email_details)
        details_text.config(state='disabled')

        ttk.Button(fallback_window, text=_("finance_gui.transaction_manager.btn_close"),
                  command=fallback_window.destroy).pack(pady=10)


    def analyze_payment_patterns(self):
        """Analyze payment patterns and display insights"""
        try:
            # Create analysis dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_("finance_gui.transaction_manager.payment_analysis_title"))
            dialog.geometry("700x600")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_("finance_gui.transaction_manager.payment_analysis_title"),
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Create text widget for results
            results_text = ScrolledText(main_frame, width=80, height=30,
                                       font=('Courier', 10), wrap=tk.WORD)
            results_text.pack(fill=tk.BOTH, expand=True)

            # Analyze payment data
            conn = self._get_connection()
            cursor = conn.cursor()

            # CTE to combine all transaction sources
            all_transactions_cte = '''
                WITH all_transactions AS (
                    SELECT payment_method, amount, payment_date as trans_date, 'Central' as source
                    FROM payments WHERE status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Gym' as source
                    FROM transactions WHERE source_type = 'gym'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Dentist' as source
                    FROM transactions WHERE source_type = 'dentist'
                    UNION ALL
                    SELECT payment_method, total_amount as amount, created_at as trans_date, 'Grocery' as source
                    FROM transactions WHERE source_type = 'grocery'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Betting' as source
                    FROM transactions WHERE source_type = 'betting' AND status = 'completed'
                    UNION ALL
                    SELECT payment_method, total_amount as amount, created_at as trans_date, 'Shop' as source
                    FROM transactions WHERE source_type = 'shop' AND status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Butcher' as source
                    FROM transactions WHERE source_type = 'butcher' AND status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'Barber' as source
                    FROM transactions WHERE source_type = 'barber' AND status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'NailBar' as source
                    FROM transactions WHERE source_type = 'nail_bar' AND status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'CarRental' as source
                    FROM transactions WHERE source_type = 'car_rental' AND status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'PhoneShop' as source
                    FROM transactions WHERE source_type = 'phone_shop' AND status = 'completed'
                    UNION ALL
                    SELECT payment_method, amount, created_at as trans_date, 'MusicShop' as source
                    FROM transactions WHERE source_type = 'music_shop' AND status = 'completed'
                )
            '''

            analysis = "PAYMENT PATTERN ANALYSIS REPORT\n"
            analysis += "=" * 70 + "\n\n"

            # 1. Payment Method Distribution
            analysis += "1. PAYMENT METHOD DISTRIBUTION\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT payment_method, COUNT(*) as count, SUM(amount) as total
                FROM all_transactions
                GROUP BY payment_method
                ORDER BY total DESC
            ''')
            methods = cursor.fetchall()
            if methods:
                for method in methods:
                    analysis += f"   {method[0]}: {method[1]} payments, \u00a3{method[2]:,.2f} total\n"
            else:
                analysis += "   No payment data available\n"
            analysis += "\n"

            # 2. Payment Timing Trends (by day of week)
            analysis += "2. PAYMENT TIMING (BY DAY OF WEEK)\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT CASE CAST(strftime('%w', trans_date) AS INTEGER)
                    WHEN 0 THEN 'Sunday'
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    WHEN 6 THEN 'Saturday'
                END as day_name,
                COUNT(*) as count,
                AVG(amount) as avg_amount
                FROM all_transactions
                WHERE trans_date IS NOT NULL
                GROUP BY strftime('%w', trans_date)
                ORDER BY count DESC
            ''')
            days = cursor.fetchall()
            if days:
                for day in days:
                    analysis += f"   {day[0]}: {day[1]} payments, \u00a3{day[2]:.2f} avg\n"
            else:
                analysis += "   No payment timing data available\n"
            analysis += "\n"

            # 3. Monthly Payment Trends
            analysis += "3. MONTHLY PAYMENT TRENDS\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT strftime('%Y-%m', trans_date) as month,
                       COUNT(*) as count,
                       SUM(amount) as total
                FROM all_transactions
                WHERE trans_date IS NOT NULL
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            ''')
            months = cursor.fetchall()
            if months:
                for month in months:
                    analysis += f"   {month[0]}: {month[1]} payments, \u00a3{month[2]:,.2f}\n"
            else:
                analysis += "   No monthly data available\n"
            analysis += "\n"

            # 4. Average Payment Amount by Status
            analysis += "4. PAYMENT STATISTICS\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT
                    COUNT(*) as total_payments,
                    SUM(amount) as total_amount,
                    AVG(amount) as avg_amount,
                    MIN(amount) as min_amount,
                    MAX(amount) as max_amount
                FROM all_transactions
            ''')
            stats = cursor.fetchone()
            if stats and stats[0] > 0:
                analysis += f"   Total Payments: {stats[0]}\n"
                analysis += f"   Total Amount: \u00a3{stats[1]:,.2f}\n"
                analysis += f"   Average Payment: \u00a3{stats[2]:.2f}\n"
                analysis += f"   Smallest Payment: \u00a3{stats[3]:.2f}\n"
                analysis += f"   Largest Payment: \u00a3{stats[4]:.2f}\n"
            else:
                analysis += "   No payment statistics available\n"
            analysis += "\n"

            # 5. Recent Payment Activity (last 30 days)
            analysis += "5. RECENT ACTIVITY (LAST 30 DAYS)\n" + "-" * 70 + "\n"
            cursor.execute(all_transactions_cte + '''
                SELECT COUNT(*) as count, SUM(amount) as total
                FROM all_transactions
                WHERE trans_date >= date('now', '-30 days')
            ''')
            recent = cursor.fetchone()
            if recent and recent[0] > 0:
                analysis += f"   Payments: {recent[0]}\n"
                analysis += f"   Total Amount: \u00a3{recent[1]:,.2f}\n"
            else:
                analysis += "   No recent payment activity\n"

            conn.close()

            # Display results
            results_text.insert('1.0', analysis)
            results_text.config(state='disabled')

            # Store analysis for email
            self.current_analytics_report = analysis

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(10, 0))

            def send_to_admin():
                """Send analytics report to admin via email"""
                try:
                    # Get admin email from database
                    admin_conn = self._get_connection()
                    admin_cursor = admin_conn.cursor()

                    # Try to find admin user email from users table
                    admin_cursor.execute('''
                        SELECT email FROM users
                        WHERE role = 'admin'
                        LIMIT 1
                    ''')
                    admin_result = admin_cursor.fetchone()

                    if not admin_result:
                        # Fallback: look for admin in students table
                        admin_cursor.execute('''
                            SELECT email_address FROM students
                            WHERE LOWER(student_id) LIKE '%admin%'
                            OR LOWER(email_address) LIKE '%admin%'
                            LIMIT 1
                        ''')
                        admin_result = admin_cursor.fetchone()

                    admin_conn.close()

                    if not admin_result or not admin_result[0]:
                        # Ask user for admin email
                        admin_email = simpledialog.askstring(
                            _("finance_gui.transaction_manager.admin_email_title"),
                            _("finance_gui.transaction_manager.admin_email_prompt"),
                            parent=dialog
                        )
                        if not admin_email:
                            return
                    else:
                        admin_email = admin_result[0]

                    # Validate email format
                    if '@' not in admin_email or '.' not in admin_email:
                        messagebox.showerror(_("finance_gui.transaction_manager.invalid_email_title"),
                                           _("finance_gui.transaction_manager.invalid_email_message", email=admin_email),
                                           parent=dialog)
                        return

                    # Send email using email service with template
                    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
                    from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

                    report_date = datetime.now().strftime('%Y-%m-%d')
                    generated_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Render email from template
                    subject, message = render_template('reports/payment_analytics_report', {
                        'report_date': report_date,
                        'generated_timestamp': generated_timestamp,
                        'report_content': analysis
                    })

                    # Fallback if template not found
                    if not subject or not message:
                        subject = f"Payment Analytics Report - {report_date}"
                        message = f"Payment Pattern Analysis Report\nGenerated: {generated_timestamp}\n\n{analysis}"

                    # Send email
                    success = send_email(
                        admin_email,
                        subject,
                        message
                    )

                    if success:
                        messagebox.showinfo(
                            _("finance_gui.transaction_manager.email_sent_title"),
                            _("finance_gui.transaction_manager.email_sent_message", email=admin_email),
                            parent=dialog
                        )
                        print(f"Analytics report emailed to {admin_email}")
                    else:
                        messagebox.showwarning(
                            _("finance_gui.transaction_manager.email_failed_title"),
                            _("finance_gui.transaction_manager.email_failed_message", email=admin_email),
                            parent=dialog
                        )

                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_send_email", error=str(e)), parent=dialog)
                    import traceback
                    traceback.print_exc()

            ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_send_to_admin"), command=send_to_admin).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_close"), command=dialog.destroy).pack(side='left', padx=5)

            print("\u2705 Payment pattern analysis completed")

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_analyze_patterns", error=str(e)))
            print(f"Error in analyze_payment_patterns: {e}")

    def get_payment_statistics(self):
        """Return basic payment statistics."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT COUNT(*) as total_count,
                       COALESCE(SUM(amount), 0) as total_amount,
                       COALESCE(AVG(amount), 0) as average_amount
                FROM payments
                WHERE status = 'completed'
                '''
            )
            row = cursor.fetchone()
            if isinstance(row, tuple):
                return {'count': row[0], 'total': row[1], 'average': row[2]}
            if row:
                return {
                    'count': row.get('total_count', 0),
                    'total': row.get('total_amount', 0.0),
                    'average': row.get('average_amount', 0.0),
                }
        except Exception as e:
            self.update_status(f"Failed to load payment statistics: {e}")
        return {'count': 0, 'total': 0.0, 'average': 0.0}

    def get_payment_trends(self):
        """Return monthly payment trend rows."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT strftime('%Y-%m', payment_date) as month,
                       COUNT(*) as payment_count,
                       COALESCE(SUM(amount), 0) as total_amount
                FROM payments
                WHERE status = 'completed'
                GROUP BY strftime('%Y-%m', payment_date)
                ORDER BY month
                '''
            )
            return cursor.fetchall()
        except Exception as e:
            self.update_status(f"Failed to load payment trends: {e}")
            return []
