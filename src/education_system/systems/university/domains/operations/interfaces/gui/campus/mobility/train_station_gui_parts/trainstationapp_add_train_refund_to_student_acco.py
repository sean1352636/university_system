"""Methods add_train_refund_to_student_account through view_train_ticket_details."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import train_station_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TrainStationApp:
    def add_train_refund_to_student_account(self, ticket_number, amount, student_id):
        """Add refund amount to student finance account"""
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.finance_unavailable", default="Finance system not available."))
            return

        if not student_id:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("train.refunds.no_student_id", default="Could not determine student ID."))
            return

        try:
            from education_system.systems.university.domains.finance.infrastructure.finance_integration import ensure_student_finance_account_exists
            from education_system.systems.university.infrastructure.database.db import get_db_connection as get_central_db, transaction as central_transaction

            # Ensure student account exists
            ensure_student_finance_account_exists(student_id)

            # Generate refund reference
            refund_ref = f"TRAIN-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Update ticket in local database
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Add status column if it doesn't exist (optional - status is now derived from unified_refunds)
            try:
                cursor.execute("ALTER TABLE train_station_tickets ADD COLUMN status TEXT DEFAULT 'active'")
            except Exception:
                pass

            # Update status if column exists (optional - status is now derived from unified_refunds)
            try:
                cursor.execute("""
                    UPDATE train_station_tickets
                    SET status = 'refunded'
                    WHERE ticket_number = ?
                """, (ticket_number,))
            except Exception:
                pass  # Column doesn't exist, status will be derived from unified_refunds table

            # Get processed_by info
            processed_by = None
            if self.current_user:
                processed_by = self.current_user.get('username') or self.current_user.get('id', '')

            # Insert refund record into unified_refunds in local database
            cursor.execute("""
                INSERT INTO unified_refunds
                (source_type, reference_id, reference_type, student_id, amount, refund_method, refund_reference, refund_date, processed_by)
                VALUES ('train', ?, 'ticket', ?, ?, 'student_account', ?, CURRENT_TIMESTAMP, ?)
            """, (ticket_number, student_id, amount, refund_ref, processed_by))

            conn.commit()
            conn.close()

            # Process in central database
            central_refund_id = None
            with central_transaction() as conn:
                cursor = conn.cursor()

                # Create refund record in central database
                cursor.execute("""
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, student_id, amount, refund_method, refund_reference, refund_date, processed_by, status)
                    VALUES ('train', ?, 'ticket', ?, ?, 'student_account', ?, CURRENT_TIMESTAMP, ?, 'processed')
                """, (ticket_number, student_id, amount, refund_ref, processed_by))
                central_refund_id = cursor.lastrowid

                # Add to student finance account
                cursor.execute("""
                    UPDATE student_finance_accounts
                    SET balance = balance + ?
                    WHERE student_id = ?
                """, (amount, student_id))

                # Get new balance and account_id after update
                cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?", (student_id,))
                result = cursor.fetchone()
                if result:
                    account_id, new_balance = result
                else:
                    account_id, new_balance = None, amount

                # Log transaction in transactions table
                cursor.execute("""
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_after, description,
                     reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                """, (account_id, student_id, amount, new_balance, f'Train ticket refund - {refund_ref}',
                      refund_ref, processed_by, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # Auto-post to GL using the central DB's refund_id (cash has moved). Never raises.
            if central_refund_id is not None:
                try:
                    from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
                    notify_ledger('refund', central_refund_id, posted_by=processed_by or 'train_station')
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "ledger hook failed for train refund %s", central_refund_id,
                    )

            # Send receipt
            self.send_train_refund_receipt(student_id, amount, 'student_account', refund_ref, ticket_number, new_balance)

            # Notify finance GUI
            self.notify_train_finance_gui(ticket_number, amount, 'student_account', refund_ref)

            # Refresh list if refunds view is active
            if hasattr(self, 'refunds_tree'):
                try:
                    self.refresh_refunds_list()
                except Exception:
                    pass  # Refunds view not currently active

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund added to student account!\n"
                              f"Reference: {refund_ref}\n"
                              f"New Balance: £{new_balance:.2f}")

        except Exception as e:
            logger.error(f"Error adding train refund to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to add refund to account: {str(e)}")

    def send_train_refund_receipt(self, student_id, amount, refund_method, refund_ref, ticket_number, new_balance=None):
        """Send refund receipt email to customer"""
        if not EMAIL_AVAILABLE:
            logger.info("Email service not available, skipping receipt")
            return

        try:
            # Get customer email
            customer_email = None
            customer_name = None

            if self.current_user and self.current_user.get('student_id') == student_id:
                customer_email = self.current_user.get('email')
                customer_name = self.current_user.get('full_name')
            elif student_id:
                customer_email = get_student_email(student_id)
                # Get name from students table
                from education_system.systems.university.infrastructure.database.db import get_db_connection as get_central_db
                with get_central_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
                    result = cursor.fetchone()
                    if result:
                        first_name, last_name = result
                        customer_name = f"{first_name} {last_name}".strip() if first_name or last_name else None

            if not customer_email:
                logger.warning(f"No email found for student {student_id}")
                return

            if not customer_name:
                customer_name = student_id

            # Format refund method for display
            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_account': 'Student Finance Account'
            }.get(refund_method, refund_method)

            # Build email body
            try:
                if TEMPLATE_AVAILABLE:
                    subject, email_body = render_template('train_refund_receipt', {
                        'customer_name': customer_name,
                        'booking_id': ticket_number,
                        'refund_amount': f"{amount:.2f}",
                        'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'payment_method': method_display,
                        'refund_id': refund_ref
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logger.warning(f"Failed to render template: {template_error}. Using fallback email.")
                # Fallback email
                subject = f"Train Ticket Refund Receipt - {refund_ref}"
                email_body = f"""
Dear {customer_name},

This is to confirm that your train ticket refund has been processed successfully.

Refund Details:
- Ticket Number: {ticket_number}
- Refund Amount: £{amount:.2f}
- Refund Method: {method_display}
- Reference Number: {refund_ref}
- Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

                if new_balance is not None:
                    email_body += f"\nYour new student account balance is: £{new_balance:.2f}\n"

                email_body += """
If you have any questions about this refund, please contact the train station.

Best regards,
University Train Station
"""

            # Send email
            send_email(
                recipient_email=customer_email,
                subject=subject,
                body=email_body
            )

            logger.info(f"Refund receipt sent to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending train refund receipt: {e}")

    def notify_train_finance_gui(self, ticket_number, amount, refund_method, refund_ref):
        """Notify finance system about the refund"""
        try:
            # Notify finance GUI via event/callback mechanism if available
            # The finance_refunds SQL insert has been removed as part of unified_refunds migration
            logger.info(f"Finance GUI notified of refund {refund_ref}")

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_train_ticket_details(self):
        """View detailed information about a ticket"""
        # Get selected ticket
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("train.refunds.select_ticket_view", default="Please select a ticket to view."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        ticket_number = values[0]

        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Get ticket details with service info
            cursor.execute("""
                SELECT
                    t.ticket_number,
                    t.passenger_name,
                    t.price_paid,
                    t.payment_method,
                    t.purchase_date,
                    CASE WHEN r.id IS NOT NULL THEN 'refunded' ELSE 'active' END as status,
                    s.service_number,
                    s.departure_station,
                    s.arrival_station,
                    s.departure_time,
                    s.arrival_time
                FROM train_station_tickets t
                JOIN train_station_services s ON t.service_id = s.id
                LEFT JOIN unified_refunds r ON t.ticket_number = r.reference_id AND r.source_type = 'train' AND r.reference_type = 'ticket'
                WHERE t.ticket_number = ?
            """, (ticket_number,))

            ticket = cursor.fetchone()
            conn.close()

            if not ticket:
                messagebox.showerror(_t("common.error", default="Error"),
                                   _t("train.refunds.ticket_not_found", default="Ticket not found."))
                return

            (ticket_num, passenger, amount, payment_method, purchase_date, status,
             service_number, dep_station, arr_station, dep_time, arr_time) = ticket

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(_t("train.refunds.ticket_details", default="Ticket Details"))
            details_window.geometry("600x650")
            details_window.transient(self.root)
            details_window.configure(bg="#f0f4f8")

            # Header
            header_frame = tk.Frame(details_window, bg="#1a365d", height=60)
            header_frame.pack(fill="x")
            header_frame.pack_propagate(False)

            tk.Label(header_frame, text=_t('gui.operations.campus.mobility.train_station_gui_parts.trainstationapp_add_train_refund_to_student_acco.labels.train_ticket_details', default="🎫 Train Ticket Details"),
                    font=("Helvetica", 16, "bold"), bg="#1a365d", fg="white").pack(pady=12)

            # Scrollable content
            canvas = tk.Canvas(details_window, bg="#f0f4f8", highlightthickness=0)
            scrollbar = tk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg="#f0f4f8")

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Build details
            details = f"""
═══════════════════════════════════════════════════════

TICKET INFORMATION
───────────────────────────────────────────────────────
  Ticket Number: {ticket_num}
  Status: {status.upper()}
  Purchase Date: {purchase_date}

PASSENGER INFORMATION
───────────────────────────────────────────────────────
  Passenger Name: {passenger}

JOURNEY DETAILS
───────────────────────────────────────────────────────
  Service Number: {service_number}
  From: {dep_station}
  To: {arr_station}
  Departure Time: {dep_time}
  Arrival Time: {arr_time}

FINANCIAL DETAILS
───────────────────────────────────────────────────────
  Amount: £{amount:.2f}
  Payment Method: {payment_method}

═══════════════════════════════════════════════════════
"""

            text_widget = tk.Text(scrollable_frame, wrap="word", width=70, height=25,
                                font=("Courier", 10), bg="#ffffff", relief="flat", padx=20, pady=20)
            text_widget.insert('1.0', details)
            text_widget.config(state='disabled')
            text_widget.pack(padx=20, pady=20)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Close button
            tk.Button(details_window, text=_t("common.close", default="Close"),
                     command=details_window.destroy,
                     font=("Helvetica", 10, "bold"),
                     bg="#e53e3e", fg="white",
                     activebackground="#c53030",
                     relief="flat", padx=20, pady=10,
                     cursor="hand2").pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing ticket details: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load details: {str(e)}")
