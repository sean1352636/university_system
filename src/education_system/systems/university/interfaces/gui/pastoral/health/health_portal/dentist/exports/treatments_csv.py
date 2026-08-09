from .. import *  # shared compatibility dependencies

class TreatmentExportMixin:
        def export_treatments_csv(self):
            """Export treatment history to CSV."""
            if not self.patient:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
                return

            try:
                from tkinter import filedialog
                import csv

                filepath = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"treatments_{self.user_id}_{datetime.now().strftime('%Y%m%d')}.csv"
                )

                if filepath:
                    with open(filepath, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['Treatment ID', 'Date', 'Treatment Type', 'Dentist',
                                       'Fee (GBP)', 'Payment Status', 'Follow-up Required'])

                        for item in self.treatments_tree.get_children():
                            values = self.treatments_tree.item(item)['values']
                            writer.writerow(values)

                    messagebox.showinfo(_t("dentist.msg_titles.export_successful"), f"Treatments exported to:\n{filepath}")
                    log_activity('export', 'dentist_treatments', user_id=self.user_id,
                               details={'file': filepath})

            except Exception as e:
                messagebox.showerror(_t("dentist.msg_titles.export_error"), f"Failed to export treatments: {e}")
