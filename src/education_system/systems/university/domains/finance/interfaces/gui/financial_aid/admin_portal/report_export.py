"""
Report export and email mixin for AdminPortal.

File writing is done by ``finance.domain.services.financial_aid.report_export``
(shared with the financial aid CLI); this mixin only asks where to save.
"""

from education_system.systems.university.domains.finance.interfaces.gui.financial_aid.admin_portal._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    csv, logging, datetime,
    get_connection, log_activity,
    send_email,
    show_error, show_success, show_warning,
    get_text, render_template,
)
from education_system.systems.university.domains.finance.domain.services.financial_aid.report_export import (
    default_report_filename,
    write_report_file,
)

logger = logging.getLogger(__name__)

_FILETYPES = {
    "csv": [("CSV files", "*.csv"), ("All files", "*.*")],
    "txt": [("Text files", "*.txt"), ("All files", "*.*")],
    "pdf": [("PDF files", "*.pdf"), ("All files", "*.*")],
}


class ReportExportMixin:
    """Methods for exporting and emailing reports."""

    def _export_report(self, report_text: str, filename_base: str, fmt: str):
        """Ask for a destination, then write the report in ``fmt``."""
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=f".{fmt}",
                filetypes=_FILETYPES[fmt],
                initialfile=default_report_filename(filename_base, fmt),
            )
            if not filepath:
                return
            written = write_report_file(report_text, filepath, fmt)
            show_success(get_text("financial_aid.admin_portal.dialogs.export_successful", "Export Successful"),
                         get_text("financial_aid.admin_portal.messages.report_exported", "Report exported to:\n{filepath}").format(filepath=written))
            log_activity('export', 'financial_aid_report', str(written), {'report_type': filename_base, 'format': fmt})
        except ImportError:
            show_error(
                get_text("financial_aid.admin_portal.dialogs.pdf_library_missing", "PDF Library Missing"),
                get_text("financial_aid.admin_portal.messages.install_reportlab", "Please install reportlab to export to PDF:\npip install reportlab")
            )
        except Exception as e:
            logger.error(f"Error exporting report to {fmt}: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"),
                       get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e)))

    def _export_report_to_csv(self, report_text: str, filename_base: str):
        """Export report to CSV file"""
        self._export_report(report_text, filename_base, "csv")

    def _export_report_to_txt(self, report_text: str, filename_base: str):
        """Export report to text file"""
        self._export_report(report_text, filename_base, "txt")

    def _export_report_text(self, report_text: str, filename_base: str):
        """Alias for _export_report_to_txt for backward compatibility"""
        self._export_report_to_txt(report_text, filename_base)

    def _export_report_to_pdf(self, report_text: str, filename_base: str):
        """Export report to PDF file"""
        self._export_report(report_text, filename_base, "pdf")

    def _email_report(self, report_text: str, report_name: str):
        """Email report to admin"""
        try:
            # Get admin email from database
            admin_email = None
            with get_connection() as conn:
                result = conn.execute("""
                    SELECT email
                    FROM users
                    WHERE role = 'admin' AND email IS NOT NULL
                    ORDER BY id ASC
                    LIMIT 1
                """).fetchone()

                if result:
                    admin_email = result['email'] if isinstance(result, dict) else result[0]

            if not admin_email:
                show_warning(get_text("financial_aid.admin_portal.dialogs.no_admin_email", "No Admin Email"), get_text("financial_aid.admin_portal.messages.no_admin_email", "No admin email address found in the database."))
                return

            # Send email with report using template
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            subject, body = render_template('reports/financial_aid_report', {
                'report_name': report_name,
                'timestamp': timestamp,
                'report_content': report_text
            })

            # Fallback if template not found
            if not subject or not body:
                subject = get_text("financial_aid.admin_portal.email.report_subject", "Financial Aid Report: {name}", name=report_name)
                body = get_text("financial_aid.admin_portal.email.report_body", "Financial Aid Report: {name}\nGenerated: {timestamp}\n\n{content}", name=report_name, timestamp=timestamp, content=report_text)

            send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            show_success(get_text("financial_aid.admin_portal.dialogs.email_sent", "Email Sent"), get_text("financial_aid.admin_portal.messages.report_emailed", "Report has been emailed to:\n{email}").format(email=admin_email))
            log_activity('email', 'financial_aid_report', admin_email, {
                'report_name': report_name,
                'recipient': admin_email
            })

        except Exception as e:
            logger.error(f"Error emailing report: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.email_error", "Email Error"), get_text("financial_aid.admin_portal.errors.failed_email_report", "Failed to email report:\n{error}").format(error=str(e)))
