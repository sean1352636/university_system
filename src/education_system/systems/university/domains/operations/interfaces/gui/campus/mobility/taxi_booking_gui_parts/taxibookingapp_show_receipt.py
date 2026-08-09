"""Methods show_receipt through refresh_refunds_list."""

from .. import taxi_booking_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TaxiBookingApp:
    def show_receipt(self, ticket_id, email_sent=False):
        """Show the payment receipt"""
        ticket = self.db.get_ticket_by_id(ticket_id)

        if not ticket:
            messagebox.showerror(_t("common.error"), _t("taxi.error.ticket_not_found"))
            return

        # Unpack ticket data
        (t_id, ticket_num, service_id, customer, pickup, dropoff, distance,
         total, payment, status, date, time, service_name, vehicle, desc) = ticket

        # Create receipt window
        receipt_window = tk.Toplevel(self.root)
        receipt_window.title(_t("taxi.receipt.title"))
        receipt_window.geometry("500x700")
        receipt_window.configure(bg=ModernStyle.BG_PRIMARY)
        receipt_window.resizable(False, False)

        # Receipt container
        receipt_frame = tk.Frame(receipt_window, bg="white", padx=30, pady=30)
        receipt_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        tk.Label(receipt_frame, text=f"🚕 {_t('taxi.app_name')}", font=("Segoe UI", 24, "bold"),
                bg="white", fg=ModernStyle.BG_SECONDARY).pack()
        tk.Label(receipt_frame, text=_t("taxi.receipt.payment_receipt"), font=("Segoe UI", 12),
                bg="white", fg="gray").pack()

        # Separator
        tk.Frame(receipt_frame, bg="#e0e0e0", height=2).pack(fill=tk.X, pady=15)

        # Ticket number
        tk.Label(receipt_frame, text=f"{_t('taxi.receipt.ticket')}: {ticket_num}", font=("Courier", 14, "bold"),
                bg="white", fg=ModernStyle.BG_SECONDARY).pack()

        # Date/Time
        tk.Label(receipt_frame, text=f"{date} {_t('taxi.email.at')} {time}", font=("Segoe UI", 10),
                bg="white", fg="gray").pack(pady=(0, 15))

        # Details
        details = [
            (_t("taxi.receipt.customer"), customer),
            (_t("taxi.receipt.service"), f"{service_name} ({vehicle})"),
            (_t("taxi.receipt.pickup"), pickup),
            (_t("taxi.receipt.dropoff"), dropoff),
            (_t("taxi.receipt.distance"), f"{distance:.1f} km"),
            (_t("taxi.receipt.payment"), payment),
            (_t("taxi.receipt.status"), status),
        ]

        for label, value in details:
            row = tk.Frame(receipt_frame, bg="white")
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=("Segoe UI", 10), bg="white",
                    fg="gray", width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("Segoe UI", 10, "bold"),
                    bg="white", fg="#333").pack(side=tk.LEFT)

        # Separator
        tk.Frame(receipt_frame, bg="#e0e0e0", height=2).pack(fill=tk.X, pady=15)

        # Total
        total_frame = tk.Frame(receipt_frame, bg="white")
        total_frame.pack(fill=tk.X)
        tk.Label(total_frame, text=_t("taxi.receipt.total_paid"), font=("Segoe UI", 12),
                bg="white", fg="gray").pack(side=tk.LEFT)
        tk.Label(total_frame, text=f"£{total:.2f}", font=("Segoe UI", 24, "bold"),
                bg="white", fg=ModernStyle.SUCCESS).pack(side=tk.RIGHT)

        if payment == "Student Account":
            tk.Label(receipt_frame, text=_t("taxi.booking.student_discount_applied"),
                    font=("Segoe UI", 10), bg="white", fg=ModernStyle.WARNING).pack(pady=5)

        # Email confirmation status
        if email_sent:
            tk.Label(receipt_frame, text=f"📧 {_t('taxi.receipt.email_sent')}",
                    font=("Segoe UI", 10), bg="white", fg=ModernStyle.SUCCESS).pack(pady=5)

        # Thank you message
        tk.Label(receipt_frame, text=_t("taxi.receipt.thank_you"),
                font=("Segoe UI", 11, "italic"), bg="white", fg="gray").pack(pady=20)

        # Buttons
        btn_frame = tk.Frame(receipt_frame, bg="white")
        btn_frame.pack(fill=tk.X, pady=10)

        # Save receipt button
        save_btn = tk.Button(btn_frame, text=f"💾 {_t('taxi.receipt.save_receipt')}", font=ModernStyle.FONT_BUTTON,
                            bg=ModernStyle.ACCENT, fg="white", bd=0, padx=20, pady=10,
                            cursor="hand2", command=lambda: self.save_receipt(ticket))
        save_btn.pack(side=tk.LEFT, expand=True, padx=5)

        # Close button
        close_btn = tk.Button(btn_frame, text=_t("common.close"), font=ModernStyle.FONT_BUTTON,
                             bg=ModernStyle.BG_CARD, fg="white", bd=0, padx=20, pady=10,
                             cursor="hand2", command=receipt_window.destroy)
        close_btn.pack(side=tk.RIGHT, expand=True, padx=5)

    def save_receipt(self, ticket):
        """Save receipt to a text file"""
        (t_id, ticket_num, service_id, customer, pickup, dropoff, distance,
         total, payment, status, date, time, service_name, vehicle, desc) = ticket

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[(_t("taxi.file.text_files"), "*.txt")],
            initialfile=f"TaxiGo_Receipt_{ticket_num}.txt"
        )

        if filename:
            receipt_text = f"""
╔══════════════════════════════════════════════════════════╗
║                    🚕 {_t('taxi.app_name'):<36}║
║                  {_t('taxi.receipt.payment_receipt'):<40}║
╠══════════════════════════════════════════════════════════╣
║  {_t('taxi.receipt.ticket_number')}: {ticket_num:<40} ║
║  {_t('common.date')}: {date:<49} ║
║  {_t('common.time')}: {time:<49} ║
╠══════════════════════════════════════════════════════════╣
║  {_t('taxi.receipt.trip_details'):<54} ║
║  {_t('taxi.receipt.customer')}:    {customer:<42} ║
║  {_t('taxi.receipt.service')}:     {service_name} ({vehicle}){' ' * (42 - len(service_name) - len(vehicle) - 3)}║
║  {_t('taxi.receipt.pickup')}:      {pickup:<42} ║
║  {_t('taxi.receipt.dropoff')}:     {dropoff:<42} ║
║  {_t('taxi.receipt.distance')}:    {distance:.1f} km{' ' * (39 - len(f'{distance:.1f}'))}║
╠══════════════════════════════════════════════════════════╣
║  {_t('taxi.receipt.payment_section'):<54} ║
║  {_t('taxi.receipt.method')}:      {payment:<42} ║
║  {_t('taxi.receipt.status')}:      {status:<42} ║
║                                                           ║
║  {_t('taxi.receipt.total_paid')}:  £{total:.2f}{' ' * (40 - len(f'{total:.2f}'))}║
╠══════════════════════════════════════════════════════════╣
║         {_t('taxi.receipt.thank_you'):<47} ║
║              {_t('taxi.receipt.safe_journey')} 🚕                       ║
╚══════════════════════════════════════════════════════════╝
"""
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(receipt_text)

            messagebox.showinfo(_t("common.success"), _t("taxi.receipt.saved_to", filename=filename))

    def show_tickets_view(self):
        """Display all purchased tickets"""
        self.clear_content()

        self.create_header(_t("taxi.tickets.title"), _t("taxi.tickets.subtitle"))

        # Tickets table container
        table_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_CARD)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Create Treeview
        columns = ("ticket", "service", "customer", "route", "distance", "fare", "payment", "date")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                           style="Custom.Treeview", height=20)

        # Define headings
        headings = {
            "ticket": (_t("taxi.tickets.ticket_num"), 150),
            "service": (_t("taxi.tickets.service"), 120),
            "customer": (_t("taxi.tickets.customer"), 120),
            "route": (_t("taxi.tickets.route"), 200),
            "distance": (_t("taxi.tickets.distance"), 80),
            "fare": (_t("taxi.tickets.fare"), 80),
            "payment": (_t("taxi.tickets.payment"), 120),
            "date": (_t("taxi.tickets.date"), 100)
        }

        for col, (heading, width) in headings.items():
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="center")

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Load tickets
        tickets = self.db.get_all_tickets()

        for ticket in tickets:
            (t_id, ticket_num, service_id, customer, pickup, dropoff, distance,
             total, payment, status, date, time, service_name, vehicle) = ticket

            route = f"{pickup[:15]}... → {dropoff[:15]}..." if len(pickup) > 15 or len(dropoff) > 15 else f"{pickup} → {dropoff}"

            tree.insert("", "end", values=(
                ticket_num,
                service_name,
                customer,
                route,
                f"{distance:.1f} km",
                f"£{total:.2f}",
                payment,
                date
            ), tags=(str(t_id),))

        # Bind double-click to view receipt
        tree.bind("<Double-1>", lambda e: self.view_ticket_receipt(tree))

        tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        v_scrollbar.grid(row=0, column=1, sticky="ns", pady=10)
        h_scrollbar.grid(row=1, column=0, sticky="ew", padx=10)

        # Configure grid weights
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Info label
        info_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_PRIMARY)
        info_frame.pack(fill=tk.X, pady=10)

        tk.Label(info_frame, text=f"💡 {_t('taxi.tickets.double_click_hint')}",
                font=ModernStyle.FONT_SMALL, bg=ModernStyle.BG_PRIMARY,
                fg=ModernStyle.TEXT_SECONDARY).pack()

        # Stats
        if tickets:
            total_spent = sum(t[7] for t in tickets)
            stats_label = tk.Label(info_frame,
                                   text=f"📊 {_t('taxi.tickets.total_bookings')}: {len(tickets)} | {_t('taxi.tickets.total_spent')}: £{total_spent:.2f}",
                                   font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_PRIMARY,
                                   fg=ModernStyle.ACCENT)
            stats_label.pack(pady=5)

        self.tickets_tree = tree

    def view_ticket_receipt(self, tree):
        """View receipt for selected ticket"""
        selection = tree.selection()
        if selection:
            item = tree.item(selection[0])
            ticket_num = item['values'][0]

            # Find ticket by number
            tickets = self.db.get_all_tickets()
            for ticket in tickets:
                if ticket[1] == ticket_num:
                    full_ticket = self.db.get_ticket_by_id(ticket[0])
                    self.show_receipt(ticket[0])
                    break

    def show_refunds_view(self):
        """Display refunds management interface"""
        self.clear_content()

        self.create_header(_t("taxi.refunds.title", default="Taxi Booking Refunds"),
                           _t("taxi.refunds.subtitle", default="Process refunds for taxi bookings"))

        # Table container
        table_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_CARD, padx=10, pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Search frame
        search_frame = tk.Frame(table_frame, bg=ModernStyle.BG_CARD)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(search_frame, text="🔍", font=("Segoe UI", 14),
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY).pack(side=tk.LEFT, padx=(0, 5))

        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var,
                                font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_SECONDARY,
                                fg=ModernStyle.TEXT_PRIMARY, insertbackground=ModernStyle.TEXT_PRIMARY)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)

        # Buttons frame
        buttons_frame = tk.Frame(table_frame, bg=ModernStyle.BG_CARD)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))

        refresh_btn = self.create_button(buttons_frame, _t("common.refresh", default="Refresh"),
                                          self.refresh_refunds_list)
        refresh_btn.pack(side=tk.LEFT, padx=(0, 10))

        refund_btn = self.create_button(buttons_frame, _t("taxi.refunds.process_refund", default="Process Refund"),
                                         self.process_taxi_refund, "success")
        refund_btn.pack(side=tk.LEFT, padx=(0, 10))

        export_btn = self.create_button(buttons_frame, _t("common.export", default="Export to CSV"),
                                         self.export_taxi_refunds_to_csv)
        export_btn.pack(side=tk.LEFT)

        # Create Treeview with 8 columns
        columns = ('ticket_id', 'ticket_number', 'date', 'customer', 'route', 'amount', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                         style="Custom.Treeview", height=20)

        # Define headings and column widths
        headings = {
            'ticket_id': (_t("taxi.refunds.ticket_id", default="Ticket ID"), 80),
            'ticket_number': (_t("taxi.refunds.ticket_number", default="Ticket Number"), 150),
            'date': (_t("common.date", default="Date"), 100),
            'customer': (_t("taxi.refunds.customer", default="Customer"), 120),
            'route': (_t("taxi.refunds.route", default="Route"), 180),
            'amount': (_t("taxi.refunds.amount", default="Amount"), 100),
            'payment_method': (_t("taxi.refunds.payment_method", default="Payment Method"), 130),
            'status': (_t("taxi.refunds.status", default="Status"), 100)
        }

        for col, (heading, width) in headings.items():
            self.refunds_tree.heading(col, text=heading)
            self.refunds_tree.column(col, width=width, anchor='center' if col != 'route' else 'w')

        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)

        self.refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to view details
        self.refunds_tree.bind('<Double-1>', lambda e: self.view_taxi_ticket_details())

        # Info label
        info_frame = tk.Frame(self.content_frame, bg=ModernStyle.BG_PRIMARY)
        info_frame.pack(fill=tk.X, pady=10)

        tk.Label(info_frame, text=f"💡 {_t('taxi.refunds.hint', default='Double-click to view ticket details')}",
                font=ModernStyle.FONT_SMALL, bg=ModernStyle.BG_PRIMARY,
                fg=ModernStyle.TEXT_SECONDARY).pack()

        # Search functionality
        def search_refunds(*args):
            search_term = search_var.get().lower()
            for item in self.refunds_tree.get_children():
                values = self.refunds_tree.item(item)['values']
                if search_term in str(values).lower():
                    self.refunds_tree.item(item, tags=())
                else:
                    self.refunds_tree.item(item, tags=('hidden',))
            self.refunds_tree.tag_configure('hidden', foreground='')

        search_var.trace('w', search_refunds)

        # Load refunds
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list from database"""
        if not hasattr(self, 'refunds_tree'):
            return

        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Get all tickets with their status (using payment_status as status indicator)
            cursor.execute('''
                SELECT
                    t.id,
                    t.ticket_number,
                    t.booking_date,
                    t.customer_name,
                    t.pickup_location,
                    t.dropoff_location,
                    t.total_fare,
                    t.payment_method,
                    COALESCE(t.payment_status, 'Completed') as status
                FROM taxi_booking_tickets t
                ORDER BY t.id DESC
            ''')

            tickets = cursor.fetchall()
            conn.close()

            for ticket in tickets:
                ticket_id, ticket_number, date, customer, pickup, dropoff, amount, payment_method, status = ticket

                # Format route
                route = f"{pickup[:20]}... → {dropoff[:20]}..." if len(pickup) > 20 or len(dropoff) > 20 else f"{pickup} → {dropoff}"

                # Determine display status
                display_status = status if status else 'Completed'

                # Color coding based on status
                tag = 'refunded' if 'refund' in display_status.lower() else 'active'

                self.refunds_tree.insert('', 'end', values=(
                    ticket_id,
                    ticket_number,
                    date,
                    customer,
                    route,
                    f"£{amount:.2f}",
                    payment_method,
                    display_status
                ), tags=(tag,))

            # Configure tags for color coding
            self.refunds_tree.tag_configure('active', foreground=ModernStyle.SUCCESS)
            self.refunds_tree.tag_configure('refunded', foreground=ModernStyle.ACCENT)

        except Exception as e:
            logger.error(f"Error refreshing refunds list: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.error_loading", default=f"Error loading tickets: {str(e)}"))
