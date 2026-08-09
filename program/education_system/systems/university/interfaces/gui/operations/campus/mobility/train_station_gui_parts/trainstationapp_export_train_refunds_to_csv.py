"""Methods export_train_refunds_to_csv through on_closing."""

from .. import train_station_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TrainStationApp:
    def export_train_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            # Ask for file location
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
                initialfile=f'train_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

            if not file_path:
                return

            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    t.ticket_number,
                    t.purchase_date,
                    t.passenger_name,
                    s.departure_station || ' → ' || s.arrival_station as route,
                    t.price_paid,
                    t.payment_method,
                    CASE WHEN r.id IS NOT NULL THEN 'refunded' ELSE 'active' END as status
                FROM train_station_tickets t
                JOIN train_station_services s ON t.service_id = s.id
                LEFT JOIN unified_refunds r ON t.ticket_number = r.reference_id AND r.source_type = 'train' AND r.reference_type = 'ticket'
                ORDER BY t.purchase_date DESC
            """)

            tickets = cursor.fetchall()
            conn.close()

            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Ticket Number', 'Date', 'Passenger', 'Route',
                               'Amount', 'Payment Method', 'Status'])

                # Write data
                for ticket in tickets:
                    ticket_number, date, passenger, route, amount, payment_method, status = ticket
                    writer.writerow([
                        ticket_number,
                        date,
                        passenger,
                        route,
                        f'{amount:.2f}',
                        payment_method,
                        status
                    ])

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refunds exported successfully to:\n{file_path}")

        except Exception as e:
            logger.error(f"Error exporting refunds to CSV: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to export refunds: {str(e)}")

    def on_closing(self):
        """Handle application closing"""
        self.db.close()
        self.root.destroy()
