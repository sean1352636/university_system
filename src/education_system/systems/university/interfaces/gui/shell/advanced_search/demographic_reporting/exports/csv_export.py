"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *

class AdvancedExportsCsvExportMixin:
    def _export_all_csv(self):
        """Export all raw data to CSV"""
        if not self.raw_data:
            messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.no_data', default="No Data"), _t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.please_generate_report_first', default="Please generate report first."))
            return

        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title=_t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.export_all_data_to_csv', default="Export All Data to CSV"),
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"demographic_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Student ID', 'Full Name', 'Gender', 'Age', 'Course',
                    'Status', 'Ethnicity', 'Academic Level', 'Age Group', 'Enrollment Date'
                ])
                for row in self.raw_data:
                    writer.writerow([
                        row[0],
                        row[1].strip() if row[1] else '',
                        row[2] or '',
                        row[3] or '',
                        row[4] or '',
                        row[5] or '',
                        row[6] or '',
                        row[7] or '',
                        row[8] or '',
                        row[9] or ''
                    ])

            messagebox.showinfo(_t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.success', default="Success"), f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.error', default="Error"), f"Failed to export: {str(e)}")

class StudentExportsCsvExportMixin:
    def _export_csv(self):
        """Export results to CSV"""
        if not self.report_data:
            messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.no_data', default="No Data"), _t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.please_perform_a_search_first', default="Please perform a search first."))
            return

        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title=_t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.export_to_csv', default="Export to CSV"),
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"demographic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Student ID', 'Full Name', 'Gender', 'Age', 'Course', 'Status', 'Ethnicity', 'Academic Level'])
                for row in self.report_data:
                    writer.writerow([
                        row[0],
                        row[1].strip() if row[1] else '',
                        row[2] or '',
                        row[3] or '',
                        row[4] or '',
                        row[5] or '',
                        row[6] or '',
                        row[7] or ''
                    ])

            messagebox.showinfo(_t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.success', default="Success"), f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.exports.csv_export.dialogs.error', default="Error"), f"Failed to export: {str(e)}")
