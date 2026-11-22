"""Methods complete_purchase through request_ticket_refund."""

from .. import train_station_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TrainStationApp:
    def complete_purchase(self):
        """Process the ticket purchase"""
        name = self.name_entry.get().strip()

        if not name:
            messagebox.showerror(_t("common.error"), _t("train.error.enter_passenger_name"))
            return

        if self.service_combo.current() < 0:
            messagebox.showerror(_t("common.error"), _t("train.error.select_service"))
            return

        service_idx = self.service_combo.current()
        service = self.services[service_idx]

        if service[7] <= 0:
            messagebox.showerror(_t("common.error"), _t("train.error.no_seats"))
            return

        # Calculate price
        base_price = service[6]
        payment_method = self.payment_var.get()
        if payment_method == "Student Account":
            final_price = base_price * 0.7
        else:
            final_price = base_price

        # Process student account payment if selected
        if payment_method == "Student Account" and FINANCE_AVAILABLE:
            student_id = self._get_current_user_student_id()
            if not student_id:
                messagebox.showerror(_t("train.error.payment_error"), _t("train.error.no_student_account"))
                return

            # Check balance and process payment
            balance = get_student_finance_account_balance(student_id)
            if balance is None:
                messagebox.showerror(_t("train.error.payment_error"), _t("train.error.account_not_found"))
                return

            if balance < final_price:
                messagebox.showerror(
                    _t("train.error.payment_error"),
                    _t("train.error.insufficient_balance", balance=balance, required=final_price)
                )
                return

        # Confirm purchase
        confirm = messagebox.askyesno(_t("train.purchase.confirm_title"),
            f"{_t('train.purchase.confirm_message')}\n\n"
            f"{_t('train.purchase.passenger_name')}: {name}\n"
            f"{_t('train.services.service_no')}: {service[1]}\n"
            f"{_t('train.purchase.route')}: {service[2]} → {service[3]}\n"
            f"{_t('train.services.departure')}: {service[4]}\n"
            f"{_t('train.purchase.payment_method')}: {payment_method}\n"
            f"{_t('train.purchase.total_price')}: £{final_price:.2f}")

        if confirm:
            # The domain service takes the payment (student account draw-down
            # or cash/card posting) and writes the ticket.
            try:
                ticket_num, receipt_num = self.db.purchase_ticket(
                    service[0], name, payment_method, final_price,
                    student_id=self._get_current_user_student_id(),
                    processed_by=self.current_user.get('username', 'System') if self.current_user else 'System',
                )
            except Exception as exc:
                messagebox.showerror(_t("train.error.payment_error"),
                                     _t("train.error.payment_failed", default=str(exc)))
                return

            # Send confirmation email
            ticket_data = {
                'ticket_number': ticket_num,
                'receipt_number': receipt_num,
                'passenger_name': name,
                'service_number': service[1],
                'departure_station': service[2],
                'arrival_station': service[3],
                'departure_time': service[4],
                'arrival_time': service[5],
                'payment_method': payment_method,
                'price_paid': final_price,
                'purchase_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            email_sent = self._send_booking_confirmation_email(ticket_data)

            self.show_receipt(ticket_num, email_sent=email_sent)

    def show_receipt(self, ticket_number, email_sent=False):
        """Display payment receipt"""
        receipt_data = self.db.get_receipt(ticket_number)

        if not receipt_data:
            messagebox.showerror(_t("common.error"), _t("train.error.receipt_not_found"))
            return

        # Create receipt window
        receipt_window = tk.Toplevel(self.root)
        receipt_window.title(_t("train.receipt.title"))
        receipt_window.geometry("450x600")
        receipt_window.configure(bg="white")
        receipt_window.resizable(False, False)

        # Receipt content
        receipt_frame = tk.Frame(receipt_window, bg="white", padx=30, pady=20)
        receipt_frame.pack(fill="both", expand=True)

        # Header
        tk.Label(receipt_frame, text=f"🚂 {_t('train.app_name').upper()}",
                font=("Helvetica", 18, "bold"),
                bg="white", fg="#1a365d").pack()
        tk.Label(receipt_frame, text=_t("train.receipt.payment_receipt"),
                font=("Helvetica", 14),
                bg="white", fg="#4a5568").pack()

        # Divider
        tk.Frame(receipt_frame, height=2, bg="#e2e8f0").pack(fill="x", pady=15)

        # Receipt details
        details = [
            (f"{_t('train.receipt.receipt_no')}:", receipt_data[0]),
            (f"{_t('train.receipt.date')}:", receipt_data[3]),
            ("", ""),
            (f"{_t('train.receipt.ticket_no')}:", receipt_data[4]),
            (f"{_t('train.receipt.passenger')}:", receipt_data[5]),
            (f"{_t('train.receipt.service')}:", receipt_data[6]),
            ("", ""),
            (f"{_t('train.receipt.from')}:", receipt_data[7]),
            (f"{_t('train.receipt.to')}:", receipt_data[8]),
            (f"{_t('train.receipt.departure')}:", receipt_data[9]),
            (f"{_t('train.receipt.arrival')}:", receipt_data[10]),
            ("", ""),
            (f"{_t('train.receipt.payment_method')}:", receipt_data[2]),
        ]

        for label, value in details:
            if label == "":
                tk.Frame(receipt_frame, height=5, bg="white").pack()
                continue
            row = tk.Frame(receipt_frame, bg="white")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=("Helvetica", 11),
                    bg="white", fg="#4a5568", width=15, anchor="e").pack(side="left")
            tk.Label(row, text=value, font=("Helvetica", 11, "bold"),
                    bg="white", fg="#1a365d").pack(side="left", padx=10)

        # Total
        tk.Frame(receipt_frame, height=2, bg="#e2e8f0").pack(fill="x", pady=15)
        total_row = tk.Frame(receipt_frame, bg="white")
        total_row.pack(fill="x")
        tk.Label(total_row, text=f"{_t('train.receipt.total_paid')}:",
                font=("Helvetica", 14, "bold"),
                bg="white", fg="#1a365d").pack(side="left")
        tk.Label(total_row, text=f"£{receipt_data[1]:.2f}",
                font=("Helvetica", 18, "bold"),
                bg="white", fg="#2f855a").pack(side="right")

        # Email confirmation status
        if email_sent:
            tk.Label(receipt_frame, text=f"📧 {_t('train.receipt.email_sent')}",
                    font=("Helvetica", 10), bg="white", fg="#2f855a").pack(pady=5)

        # Footer
        tk.Frame(receipt_frame, height=2, bg="#e2e8f0").pack(fill="x", pady=15)
        tk.Label(receipt_frame, text=_t("train.receipt.thank_you"),
                font=("Helvetica", 11, "italic"),
                bg="white", fg="#718096").pack()

        # Close button
        close_btn = tk.Button(receipt_frame, text=_t("common.close"),
                             font=("Helvetica", 11),
                             bg="#4a5568", fg="white",
                             relief="flat", padx=30, pady=8,
                             cursor="hand2",
                             command=receipt_window.destroy)
        close_btn.pack(pady=20)

        # Refresh services to update seat count
        self.services = self.db.get_all_services()
        messagebox.showinfo(_t("common.success"), _t("train.purchase.success", ticket_number=ticket_number))

    def show_tickets(self):
        """Display all purchased tickets"""
        self.clear_content()

        # Title
        title = tk.Label(self.content_frame,
                        text=_t("train.tickets.title"),
                        font=("Helvetica", 18, "bold"),
                        bg="#f0f4f8", fg="#1a365d")
        title.pack(pady=(0, 15))

        # Create treeview with scrollbar
        tree_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        tree_frame.pack(fill="both", expand=False, pady=(0, 10))

        columns = ("Ticket", "Passenger", "Service", "From", "To", "Time", "Payment", "Price", "Date", "Status")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

        # Configure columns
        tree.heading("Ticket", text=_t("train.tickets.ticket_no"))
        tree.heading("Passenger", text=_t("train.tickets.passenger"))
        tree.heading("Service", text=_t("train.tickets.service"))
        tree.heading("From", text=_t("train.tickets.from"))
        tree.heading("To", text=_t("train.tickets.to"))
        tree.heading("Time", text=_t("train.tickets.departure"))
        tree.heading("Payment", text=_t("train.tickets.payment"))
        tree.heading("Price", text=_t("train.tickets.price"))
        tree.heading("Date", text=_t("train.tickets.purchase_date"))
        tree.heading("Status", text=_t("train.tickets.status", default="Status"))

        tree.column("Ticket", width=100, anchor="center")
        tree.column("Passenger", width=120)
        tree.column("Service", width=80, anchor="center")
        tree.column("From", width=130)
        tree.column("To", width=130)
        tree.column("Time", width=70, anchor="center")
        tree.column("Payment", width=100, anchor="center")
        tree.column("Price", width=70, anchor="center")
        tree.column("Date", width=110, anchor="center")
        tree.column("Status", width=80, anchor="center")

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        # Populate data with refund status
        tickets = self.db.get_all_tickets()

        # Get refund status for all tickets
        refunded_tickets = set()
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT reference_id FROM unified_refunds WHERE source_type = 'train' AND reference_type = 'ticket'")
            refunded_tickets = set(row[0] for row in cursor.fetchall())
            conn.close()
        except Exception as e:
            logger.warning(f"Could not load refund status: {e}")
            # Continue without refund status

        for ticket in tickets:
            ticket_number = ticket[0]
            status = "Refunded" if ticket_number in refunded_tickets else "Active"
            tag = "refunded" if ticket_number in refunded_tickets else "active"

            tree.insert("", "end", values=(
                ticket_number,  # ticket_number
                ticket[1],  # passenger_name
                ticket[2],  # service_number
                ticket[3],  # departure_station
                ticket[4],  # arrival_station
                ticket[5],  # departure_time
                ticket[6],  # payment_method
                f"£{ticket[7]:.2f}",  # price_paid
                ticket[8],   # purchase_date
                status
            ), tags=(tag,))

        # Store tree reference for receipt viewing
        self.tickets_tree = tree

        # Buttons frame - make it more prominent
        btn_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        btn_frame.pack(pady=20, fill=tk.X)

        # Create inner frame to center buttons
        inner_btn_frame = tk.Frame(btn_frame, bg="#f0f4f8")
        inner_btn_frame.pack()

        view_receipt_btn = tk.Button(inner_btn_frame, text=f"📄 {_t('train.tickets.view_receipt')}",
                                    font=("Helvetica", 12, "bold"),
                                    bg="#3182ce", fg="white",
                                    activebackground="#2b6cb0",
                                    relief="flat", padx=25, pady=12,
                                    cursor="hand2",
                                    command=self.view_selected_receipt)
        view_receipt_btn.pack(side=tk.LEFT, padx=10)

        refund_btn = tk.Button(inner_btn_frame, text=f"💸 {_t('train.tickets.request_refund', default='Request Refund')}",
                              font=("Helvetica", 12, "bold"),
                              bg="#e53e3e", fg="white",
                              activebackground="#c53030",
                              relief="flat", padx=25, pady=12,
                              cursor="hand2",
                              command=self.request_ticket_refund)
        refund_btn.pack(side=tk.LEFT, padx=10)

        # Configure row colors based on status
        tree.tag_configure("refunded", background="#ffcccc", foreground="#7f0000")
        tree.tag_configure("active", background="#ccffcc", foreground="#005500")

        # Show count
        count_label = tk.Label(self.content_frame,
                              text=_t("train.tickets.total_count", count=len(tickets)),
                              font=("Helvetica", 10),
                              bg="#f0f4f8", fg="#718096")
        count_label.pack()

    def view_selected_receipt(self):
        """View receipt for selected ticket"""
        selection = self.tickets_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("train.tickets.select_ticket"))
            return

        item = self.tickets_tree.item(selection[0])
        ticket_number = item["values"][0]
        self.show_receipt(ticket_number)

    def request_ticket_refund(self):
        """Request refund for selected ticket"""
        selection = self.tickets_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                  _t("train.tickets.select_ticket", default="Please select a ticket."))
            return

        item = self.tickets_tree.item(selection[0])
        ticket_number = item["values"][0]
        passenger_name = item["values"][1]
        price_str = item["values"][7]  # Format: £XX.XX
        amount = float(price_str.replace('£', ''))

        # Check if already refunded
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT refund_id FROM unified_refunds WHERE source_type = 'train' AND reference_type = 'ticket' AND reference_id = ?
            """, (ticket_number,))
            existing_refund = cursor.fetchone()
            conn.close()

            if existing_refund:
                messagebox.showwarning(_t("train.refunds.already_refunded", default="Already Refunded"),
                                      _t("train.refunds.already_refunded_msg", default="This ticket has already been refunded."))
                return

        except Exception as e:
            logger.error(f"Error checking refund status: {e}")

        # Confirm refund
        if not messagebox.askyesno(_t("train.refunds.confirm", default="Confirm Refund"),
                                  f"Process refund for ticket {ticket_number}?\n\nPassenger: {passenger_name}\nAmount: £{amount:.2f}"):
            return

        # Get student ID
        student_id = None
        if self.current_user:
            student_id = self.current_user.get('student_id') or self.current_user.get('id', '')

        # Show refund method dialog
        self.show_train_refund_method_dialog(ticket_number, amount, passenger_name)
