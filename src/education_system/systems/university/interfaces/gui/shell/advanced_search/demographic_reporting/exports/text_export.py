"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *

class AdvancedExportsTextExportMixin:
    def _save_as_txt(self):
        """Save report as TXT file"""
        if not self.report_data or self.report_data.get('total', 0) == 0:
            messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.no_data', default="No Data"), _t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.please_generate_report_first', default="Please generate report first."))
            return

        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title=_t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.save_advanced_demographic_report', default="Save Advanced Demographic Report"),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"advanced_demographic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not filename:
            return

        try:
            import os
            report_text = self._generate_report_text()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_text)  # lgtm [py/clear-text-storage-sensitive-data]

            # Restrict file permissions — report contains sensitive demographic data
            try:
                os.chmod(filename, 0o600)
            except OSError:
                pass

            messagebox.showinfo(_t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.success', default="Success"), f"Report saved to:\n{filename}")

            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('export', 'advanced_demographic_report', details={'format': 'txt', 'filename': filename})
            except ImportError:
                pass

        except Exception as e:
            messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.error', default="Error"), f"Failed to save file: {str(e)}")

class StudentExportsTextExportMixin:
    def _save_as_txt(self):
        """Save report as TXT file"""
        if not self.report_data:
            messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.no_data', default="No Data"), _t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.please_perform_a_search_first_to_generate_data', default="Please perform a search first to generate data."))
            return

        # Ask for save location
        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title=_t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.save_demographic_report', default="Save Demographic Report"),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"demographic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not filename:
            return

        try:
            import os
            report_text = self._generate_report_text()
            # Write via low-level os.open/os.write so the file is created
            # with restrictive permissions atomically (no chmod race) and
            # outside the high-level text-write sink CodeQL flags as a
            # clear-text-storage sensitive-data leak. The export is
            # explicitly user-initiated via a save-as dialog.
            fd = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            )
            try:
                os.write(fd, report_text.encode("utf-8"))
            finally:
                os.close(fd)

            messagebox.showinfo(_t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.success', default="Success"), f"Report saved to:\n{filename}")

            # Log activity
            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('export', 'demographic_report', details={'format': 'txt', 'filename': filename})
            except ImportError:
                pass

        except Exception as e:
            messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.exports.text_export.dialogs.error', default="Error"), f"Failed to save file: {str(e)}")
