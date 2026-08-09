from .. import *  # shared compatibility dependencies

class PaymentExportMixin:
        def _export_payments_csv(self):
            """Export payments to CSV file."""
            try:
                from tkinter import filedialog
                import csv

                filepath = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"dentist_payments_{datetime.now().strftime('%Y%m%d')}.csv"
                )

                if filepath:
                    with open(filepath, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['Transaction ID', 'Reference', 'Date', 'User ID', 'Patient #',
                                       'Type', 'Amount', 'Method', 'Status'])

                        for item in self.payments_tree.get_children():
                            values = self.payments_tree.item(item)['values']
                            writer.writerow(values)

                    messagebox.showinfo(_t("dentist.msg_titles.export_successful"), f"Payments exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror(_t("dentist.msg_titles.export_error"), f"Failed to export payments: {e}")
