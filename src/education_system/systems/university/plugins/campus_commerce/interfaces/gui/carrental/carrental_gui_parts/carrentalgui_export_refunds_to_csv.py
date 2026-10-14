"""Methods export_refunds_to_csv through export_refunds_to_csv."""

from .. import carrental_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CarRentalGUI:
    def export_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            # Ask for file location
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
                initialfile=f'carrental_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

            if not file_path:
                return

            with get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        t.transaction_id,
                        t.created_at,
                        t.customer_id,
                        t.amount,
                        t.transaction_type,
                        t.payment_method,
                        t.status,
                        t.reference_number
                    FROM transactions t
                    WHERE t.source_type = 'car_rental'
                    ORDER BY t.created_at DESC
                """)

                transactions = cursor.fetchall()

            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Transaction ID', 'Date', 'Customer ID', 'Amount',
                               'Transaction Type', 'Payment Method', 'Status', 'Reference'])

                # Write data
                for trans in transactions:
                    transaction_id, date, customer_id, amount, transaction_type, payment_method, status, reference = trans
                    writer.writerow([
                        transaction_id,
                        date or '',
                        customer_id,
                        f'{amount:.2f}' if amount else '0.00',
                        transaction_type or '',
                        payment_method or '',
                        status or 'completed',
                        reference or ''
                    ])

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refunds exported successfully to:\n{file_path}")

        except Exception as e:
            logger.error(f"Error exporting refunds to CSV: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to export refunds: {str(e)}")
