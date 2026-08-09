"""Methods notify_taxi_finance_gui through export_taxi_refunds_to_csv."""

from .. import taxi_booking_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TaxiBookingApp:
    def notify_taxi_finance_gui(self, refund_ref, amount, refund_method, ticket_number):
        """Notify finance GUI about the refund"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Refund already recorded in unified_refunds table
            logger.info(f"Finance GUI notified about refund: {refund_ref}")
            return True

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")
            return False

    def view_taxi_ticket_details(self):
        """View detailed information about selected ticket"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                   _t("taxi.refunds.select_ticket_details", default="Please select a ticket to view details"))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        ticket_id = values[0]

        try:
            # Get full ticket details
            ticket = self.db.get_ticket_by_id(ticket_id)
            if not ticket:
                messagebox.showerror(_t("common.error", default="Error"),
                                     _t("taxi.refunds.ticket_not_found", default="Ticket not found"))
                return

            # Unpack ticket data
            (t_id, ticket_num, service_id, customer, pickup, dropoff, distance,
             total, payment, status, date, time, service_name, vehicle, desc) = ticket

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(_t("taxi.refunds.ticket_details", default="Ticket Details"))
            details_window.geometry("600x700")
            details_window.configure(bg=ModernStyle.BG_PRIMARY)
            details_window.transient(self.root)

            # Center window
            details_window.update_idletasks()
            x = (details_window.winfo_screenwidth() // 2) - (600 // 2)
            y = (details_window.winfo_screenheight() // 2) - (700 // 2)
            details_window.geometry(f"600x700+{x}+{y}")

            # Create scrollable frame
            canvas = tk.Canvas(details_window, bg=ModernStyle.BG_PRIMARY, highlightthickness=0)
            scrollbar = tk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg=ModernStyle.BG_PRIMARY)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Content frame
            content_frame = tk.Frame(scrollable_frame, bg=ModernStyle.BG_CARD, padx=30, pady=30)
            content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Header
            tk.Label(content_frame, text="🚕 " + _t("taxi.refunds.ticket_details", default="Ticket Details"),
                    font=ModernStyle.FONT_TITLE, bg=ModernStyle.BG_CARD,
                    fg=ModernStyle.TEXT_PRIMARY).pack(pady=(0, 20))

            # Ticket information
            details_data = [
                (_t("taxi.refunds.ticket_number", default="Ticket Number"), ticket_num),
                (_t("common.date", default="Date"), f"{date} {time}"),
                (_t("taxi.refunds.customer", default="Customer"), customer),
                ("", ""),  # Separator
                (_t("taxi.refunds.trip_info", default="TRIP INFORMATION"), ""),
                (_t("taxi.refunds.service", default="Service"), f"{service_name} ({vehicle})"),
                (_t("taxi.refunds.description", default="Description"), desc or "N/A"),
                (_t("taxi.refunds.pickup", default="Pickup Location"), pickup),
                (_t("taxi.refunds.dropoff", default="Dropoff Location"), dropoff),
                (_t("taxi.refunds.distance", default="Distance"), f"{distance:.1f} km"),
                ("", ""),  # Separator
                (_t("taxi.refunds.payment_info", default="PAYMENT INFORMATION"), ""),
                (_t("taxi.refunds.total_fare", default="Total Fare"), f"£{total:.2f}"),
                (_t("taxi.refunds.payment_method", default="Payment Method"), payment),
                (_t("taxi.refunds.status", default="Status"), status),
            ]

            for label, value in details_data:
                if label == "":
                    # Separator
                    tk.Frame(content_frame, bg=ModernStyle.BORDER, height=1).pack(fill=tk.X, pady=10)
                elif value == "":
                    # Section header
                    tk.Label(content_frame, text=label, font=ModernStyle.FONT_SUBTITLE,
                            bg=ModernStyle.BG_CARD, fg=ModernStyle.ACCENT).pack(anchor='w', pady=(10, 5))
                else:
                    # Regular field
                    row = tk.Frame(content_frame, bg=ModernStyle.BG_CARD)
                    row.pack(fill=tk.X, pady=3)
                    tk.Label(row, text=label + ":", font=ModernStyle.FONT_BODY,
                            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY,
                            width=20, anchor='w').pack(side=tk.LEFT)
                    tk.Label(row, text=value, font=ModernStyle.FONT_BODY,
                            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY,
                            wraplength=350, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Close button
            close_btn = self.create_button(content_frame, _t("common.close", default="Close"),
                                            details_window.destroy)
            close_btn.pack(fill=tk.X, pady=(20, 0))

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Bind mousewheel
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        except Exception as e:
            logger.error(f"Error viewing ticket details: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.error_viewing_details", default=f"Error viewing details: {str(e)}"))

    def export_taxi_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[(_t("common.csv_files", default="CSV Files"), "*.csv")],
                initialfile=f"Taxi_Refunds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            import csv

            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    t.id,
                    t.ticket_number,
                    t.booking_date,
                    t.booking_time,
                    t.customer_name,
                    t.pickup_location,
                    t.dropoff_location,
                    t.distance_km,
                    t.total_fare,
                    t.payment_method,
                    COALESCE(t.payment_status, 'Completed') as status,
                    s.service_name,
                    s.vehicle_type
                FROM taxi_booking_tickets t
                LEFT JOIN taxi_booking_services s ON t.service_id = s.id
                ORDER BY t.id DESC
            ''')

            tickets = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    _t("taxi.refunds.ticket_id", default="Ticket ID"),
                    _t("taxi.refunds.ticket_number", default="Ticket Number"),
                    _t("common.date", default="Date"),
                    _t("common.time", default="Time"),
                    _t("taxi.refunds.customer", default="Customer"),
                    _t("taxi.refunds.pickup", default="Pickup Location"),
                    _t("taxi.refunds.dropoff", default="Dropoff Location"),
                    _t("taxi.refunds.distance", default="Distance (km)"),
                    _t("taxi.refunds.amount", default="Amount"),
                    _t("taxi.refunds.payment_method", default="Payment Method"),
                    _t("taxi.refunds.status", default="Status"),
                    _t("taxi.refunds.service", default="Service"),
                    _t("taxi.refunds.vehicle_type", default="Vehicle Type")
                ])

                # Write data
                for ticket in tickets:
                    writer.writerow(ticket)

            messagebox.showinfo(_t("common.success", default="Success"),
                                _t("taxi.refunds.export_success", default=f"Refunds exported successfully to:\n{filename}"))

        except Exception as e:
            logger.error(f"Error exporting refunds to CSV: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.export_error", default=f"Error exporting to CSV: {str(e)}"))
