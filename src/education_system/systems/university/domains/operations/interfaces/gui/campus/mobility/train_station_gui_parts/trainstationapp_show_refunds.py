"""Methods show_refunds through _complete_train_refund."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import train_station_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

from education_system.systems.university.domains.operations.domain.campus.mobility.services import train_station_service


class TrainStationApp:
    def show_refunds(self):
        """Display refunds management interface"""
        self.clear_content()

        # Title
        title = tk.Label(self.content_frame,
                        text=_t("train.refunds.title", default="===== REFUNDS ====="),
                        font=("Helvetica", 18, "bold"),
                        bg="#f0f4f8", fg="#1a365d")
        title.pack(pady=(0, 15))

        # Search frame
        search_frame = tk.Frame(self.content_frame, bg="#ffffff", relief="solid", borderwidth=1)
        search_frame.pack(fill="x", pady=(0, 10), padx=10)

        tk.Label(search_frame, text=_t("common.search", default="Search:"),
                font=("Helvetica", 10), bg="#ffffff").pack(side="left", padx=10, pady=10)

        self.refund_search_var = tk.StringVar()
        self.refund_search_var.trace('w', lambda *args: self.refresh_refunds_list())
        search_entry = tk.Entry(search_frame, textvariable=self.refund_search_var, width=40, font=("Helvetica", 10))
        search_entry.pack(side="left", padx=10, pady=10)

        # Table frame
        tree_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        tree_frame.pack(fill="both", expand=True)

        # Create treeview with 7 columns
        columns = ("Ticket", "Date", "Passenger", "Route", "Amount", "Payment Method", "Status")
        self.refunds_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # Configure columns
        self.refunds_tree.heading("Ticket", text=_t("train.refunds.ticket_number", default="Ticket Number"))
        self.refunds_tree.heading("Date", text=_t("common.date", default="Date"))
        self.refunds_tree.heading("Passenger", text=_t("train.refunds.passenger", default="Passenger"))
        self.refunds_tree.heading("Route", text=_t("train.refunds.route", default="Route"))
        self.refunds_tree.heading("Amount", text=_t("common.amount", default="Amount"))
        self.refunds_tree.heading("Payment Method", text=_t("common.payment_method", default="Payment Method"))
        self.refunds_tree.heading("Status", text=_t("common.status", default="Status"))

        self.refunds_tree.column("Ticket", width=120, anchor="center")
        self.refunds_tree.column("Date", width=120, anchor="center")
        self.refunds_tree.column("Passenger", width=150)
        self.refunds_tree.column("Route", width=200)
        self.refunds_tree.column("Amount", width=100, anchor="center")
        self.refunds_tree.column("Payment Method", width=120, anchor="center")
        self.refunds_tree.column("Status", width=100, anchor="center")

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)

        self.refunds_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons frame
        buttons_frame = tk.Frame(self.content_frame, bg="#f0f4f8")
        buttons_frame.pack(fill="x", pady=10)

        tk.Button(buttons_frame, text=_t("train.refunds.process", default="Process Refund"),
                 command=self.process_train_refund,
                 font=("Helvetica", 10, "bold"),
                 bg="#3182ce", fg="white",
                 activebackground="#2c5aa0",
                 relief="flat", padx=15, pady=8,
                 cursor="hand2").pack(side="left", padx=5)

        tk.Button(buttons_frame, text=_t("common.view_details", default="View Details"),
                 command=self.view_train_ticket_details,
                 font=("Helvetica", 10, "bold"),
                 bg="#38a169", fg="white",
                 activebackground="#2f855a",
                 relief="flat", padx=15, pady=8,
                 cursor="hand2").pack(side="left", padx=5)

        tk.Button(buttons_frame, text=_t("common.refresh", default="Refresh"),
                 command=self.refresh_refunds_list,
                 font=("Helvetica", 10, "bold"),
                 bg="#718096", fg="white",
                 activebackground="#4a5568",
                 relief="flat", padx=15, pady=8,
                 cursor="hand2").pack(side="left", padx=5)

        tk.Button(buttons_frame, text=_t("common.export_csv", default="Export to CSV"),
                 command=self.export_train_refunds_to_csv,
                 font=("Helvetica", 10, "bold"),
                 bg="#805ad5", fg="white",
                 activebackground="#6b46c1",
                 relief="flat", padx=15, pady=8,
                 cursor="hand2").pack(side="left", padx=5)

        # Load data
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with search support"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            search_term = self.refund_search_var.get().lower() if hasattr(self, 'refund_search_var') else ''

            conn = self.db.get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    t.ticket_number,
                    t.purchase_date,
                    t.passenger_name,
                    s.departure_station || ' → ' || s.arrival_station as route,
                    t.price_paid,
                    t.payment_method,
                    CASE WHEN r.refund_id IS NOT NULL THEN 'refunded' ELSE 'active' END as status
                FROM train_station_tickets t
                JOIN train_station_services s ON t.service_id = s.id
                LEFT JOIN unified_refunds r ON t.ticket_number = r.reference_id AND r.source_type = 'train' AND r.reference_type = 'ticket'
                ORDER BY t.purchase_date DESC
            """

            cursor.execute(query)
            tickets = cursor.fetchall()
            conn.close()

            for ticket in tickets:
                ticket_number, date, passenger, route, amount, payment_method, status = ticket

                # Apply search filter
                if search_term:
                    searchable = f"{ticket_number} {passenger} {route} {status}".lower()
                    if search_term not in searchable:
                        continue

                # Color code by status
                if status == 'refunded':
                    self.refunds_tree.insert("", "end", values=(
                        ticket_number, date, passenger, route,
                        f"£{amount:.2f}", payment_method, status
                    ), tags=('refunded',))
                else:
                    self.refunds_tree.insert("", "end", values=(
                        ticket_number, date, passenger, route,
                        f"£{amount:.2f}", payment_method, status
                    ), tags=('active',))

            # Configure tags
            self.refunds_tree.tag_configure('refunded', background='#ffcccc')
            self.refunds_tree.tag_configure('active', background='#ccffcc')

        except Exception as e:
            logger.error(f"Error refreshing refunds list: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load refunds: {str(e)}")

    def process_train_refund(self):
        """Process a refund for a train ticket"""
        # Get selected ticket
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("train.refunds.select_ticket", default="Please select a ticket to refund."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        ticket_number = values[0]
        amount_str = values[4]
        status = values[6]

        # Check if already refunded
        if status == 'refunded':
            messagebox.showwarning(_t("train.refunds.already_refunded", default="Already Refunded"),
                                  _t("train.refunds.already_refunded_msg", default="This ticket has already been refunded."))
            return

        # Parse amount
        try:
            amount = float(amount_str.replace('£', '').replace(',', ''))
        except (ValueError, TypeError):
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.invalid_amount", default="Invalid amount format."))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("train.refunds.confirm", default="Confirm Refund"),
                                   f"Refund £{amount:.2f} for Ticket {ticket_number}?"):
            return

        try:
            # Get passenger name for student ID lookup
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT passenger_name FROM train_station_tickets WHERE ticket_number = ?",
                         (ticket_number,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror(_t("common.error", default="Error"),
                                   _t("train.refunds.ticket_not_found", default="Ticket not found."))
                return

            passenger_name = result[0]

            # Show refund method dialog
            self.show_train_refund_method_dialog(ticket_number, amount, passenger_name)

        except Exception as e:
            logger.error(f"Error processing train refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to process refund: {str(e)}")

    def show_train_refund_method_dialog(self, ticket_number, amount, passenger_name):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("train.refunds.select_method", default="Select Refund Method"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#f0f4f8")

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        header_frame = tk.Frame(dialog, bg="#1a365d", height=60)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text=_t("train.refunds.select_method", default="Select Refund Method"),
                font=("Helvetica", 14, "bold"), bg="#1a365d", fg="white").pack(pady=15)

        # Content
        content_frame = tk.Frame(dialog, bg="#f0f4f8")
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(content_frame, text=f"Refund Amount: £{amount:.2f}",
                font=("Helvetica", 12, "bold"), bg="#f0f4f8", fg="#1a365d").pack(pady=10)

        # Try to get student ID from passenger name
        student_id = self._get_student_id_from_passenger_name(passenger_name)

        # Get current balance if finance is available
        current_balance = None
        if student_id and FINANCE_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(student_id)
                tk.Label(content_frame, text=f"Current Student Account Balance: £{current_balance:.2f}",
                        font=("Helvetica", 10), bg="#f0f4f8", fg="#3182ce").pack(pady=5)
                new_balance = current_balance + amount
                tk.Label(content_frame, text=f"New Balance After Refund: £{new_balance:.2f}",
                        font=("Helvetica", 10, "bold"), bg="#f0f4f8", fg="#38a169").pack(pady=5)
            except Exception as e:
                logger.warning(f"Could not get student balance: {e}")

        # Buttons
        tk.Button(content_frame, text=_t('gui.operations.campus.mobility.train_station_gui_parts.trainstationapp_show_refunds.buttons.refund_as_cash', default="💵 Refund as Cash"),
                 command=lambda: [dialog.destroy(), self._complete_train_refund(ticket_number, amount, 'cash', student_id)],
                 font=("Helvetica", 11, "bold"),
                 bg="#4a5568", fg="white",
                 activebackground="#2d3748",
                 relief="flat", padx=20, pady=12,
                 cursor="hand2", width=25).pack(pady=8)

        tk.Button(content_frame, text=_t('gui.operations.campus.mobility.train_station_gui_parts.trainstationapp_show_refunds.buttons.refund_to_card', default="💳 Refund to Card"),
                 command=lambda: [dialog.destroy(), self._complete_train_refund(ticket_number, amount, 'card', student_id)],
                 font=("Helvetica", 11, "bold"),
                 bg="#4a5568", fg="white",
                 activebackground="#2d3748",
                 relief="flat", padx=20, pady=12,
                 cursor="hand2", width=25).pack(pady=8)

        account_btn = tk.Button(content_frame, text=_t('gui.operations.campus.mobility.train_station_gui_parts.trainstationapp_show_refunds.buttons.refund_to_student_account', default="🏦 Refund to Student Account"),
                               command=lambda: [dialog.destroy(), self.add_train_refund_to_student_account(ticket_number, amount, student_id)],
                               font=("Helvetica", 11, "bold"),
                               bg="#3182ce", fg="white",
                               activebackground="#2c5aa0",
                               relief="flat", padx=20, pady=12,
                               cursor="hand2", width=25)
        account_btn.pack(pady=8)

        if not (student_id and FINANCE_AVAILABLE):
            account_btn.config(state='disabled', bg="#a0aec0")

        tk.Button(content_frame, text=_t("common.cancel", default="Cancel"),
                 command=dialog.destroy,
                 font=("Helvetica", 10),
                 bg="#e53e3e", fg="white",
                 activebackground="#c53030",
                 relief="flat", padx=20, pady=10,
                 cursor="hand2", width=25).pack(pady=8)

    def _get_student_id_from_passenger_name(self, passenger_name):
        """Try to get student ID from passenger name"""
        # First check if current user matches
        if self.current_user and self.current_user.get('full_name', '').lower() == passenger_name.lower():
            return self._get_current_user_student_id()

        # Try to match with students table
        try:
            from education_system.systems.university.infrastructure.database.db import get_db_connection as get_central_db
            with get_central_db() as conn:
                cursor = conn.cursor()
                # Query using concatenated first_name and last_name since full_name column doesn't exist
                cursor.execute("""
                    SELECT student_id FROM students
                    WHERE TRIM(first_name || ' ' || last_name) = ?
                       OR TRIM(first_name || ' ' || COALESCE(middle_name, '') || ' ' || last_name) = ?
                """, (passenger_name.strip(), passenger_name.strip()))
                result = cursor.fetchone()
                if result:
                    return result[0]
        except Exception as e:
            logger.warning(f"Could not lookup student ID: {e}")

        return None

    def _complete_train_refund(self, ticket_number, amount, refund_method, student_id):
        """Complete the refund process (for cash/card) via the domain service."""
        try:
            processed_by = None
            if self.current_user:
                processed_by = self.current_user.get('username') or self.current_user.get('id', '')

            # The service writes the refund once and posts it to Finance.
            outcome = train_station_service.process_refund(
                ticket_number, amount, refund_method, student_id=student_id,
                processed_by=processed_by,
            )
            refund_ref = outcome['refund_ref']

            # Send receipt
            self.send_train_refund_receipt(student_id, amount, refund_method, refund_ref, ticket_number)

            # Notify finance GUI
            self.notify_train_finance_gui(ticket_number, amount, refund_method, refund_ref)

            # Refresh list if refunds view is active
            if hasattr(self, 'refunds_tree'):
                try:
                    self.refresh_refunds_list()
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund processed successfully!\nReference: {refund_ref}")

        except Exception as e:
            logger.error(f"Error completing train refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to complete refund: {str(e)}")
