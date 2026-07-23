"""
Report export and email mixin for AdminPortal.
"""

from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    csv, logging, datetime,
    get_connection, log_activity,
    send_email,
    show_error, show_success, show_warning,
    get_text, render_template,
)

logger = logging.getLogger(__name__)


class ReportExportMixin:
    """Methods for exporting and emailing reports."""

    def _export_report_to_csv(self, report_text: str, filename_base: str):
        """Export report to CSV file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"{filename_base}_{timestamp}.csv"
            )

            if filepath:
                # Convert report text to CSV format
                lines = report_text.split('\n')
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for line in lines:
                        # Write each line as a single CSV row
                        writer.writerow([line])

                show_success(get_text("financial_aid.admin_portal.dialogs.export_successful", "Export Successful"), get_text("financial_aid.admin_portal.messages.report_exported", "Report exported to:\n{filepath}").format(filepath=filepath))
                log_activity('export', 'financial_aid_report', filepath, {'report_type': filename_base, 'format': 'csv'})

        except Exception as e:
            logger.error(f"Error exporting report to CSV: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"), get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e)))

    def _export_report_to_txt(self, report_text: str, filename_base: str):
        """Export report to text file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"{filename_base}_{timestamp}.txt"
            )

            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_text)

                show_success(get_text("financial_aid.admin_portal.dialogs.export_successful", "Export Successful"), get_text("financial_aid.admin_portal.messages.report_exported", "Report exported to:\n{filepath}").format(filepath=filepath))
                log_activity('export', 'financial_aid_report', filepath, {'report_type': filename_base, 'format': 'txt'})

        except Exception as e:
            logger.error(f"Error exporting report to text: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"), get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e)))

    def _export_report_text(self, report_text: str, filename_base: str):
        """Alias for _export_report_to_txt for backward compatibility"""
        self._export_report_to_txt(report_text, filename_base)

    def _export_report_to_pdf(self, report_text: str, filename_base: str):
        """Export report to PDF file"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_LEFT

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = messagebox.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"{filename_base}_{timestamp}.pdf"
            )

            if filepath:
                # Create PDF document
                doc = SimpleDocTemplate(filepath, pagesize=letter,
                                       rightMargin=72, leftMargin=72,
                                       topMargin=72, bottomMargin=18)

                # Container for PDF elements
                story = []

                # Get default styles
                styles = getSampleStyleSheet()

                # Create custom style for report text
                report_style = ParagraphStyle(
                    'ReportStyle',
                    parent=styles['Normal'],
                    fontName='Courier',
                    fontSize=9,
                    leading=12,
                    alignment=TA_LEFT,
                    spaceAfter=6
                )

                # Split report into lines and add to story
                for line in report_text.split('\n'):
                    if line.strip():
                        # Replace special characters that might cause issues
                        line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        p = Paragraph(line, report_style)
                        story.append(p)
                    else:
                        story.append(Spacer(1, 0.1 * inch))

                # Build PDF
                doc.build(story)

                show_success(
                    get_text("financial_aid.admin_portal.dialogs.export_successful", "Export Successful"),
                    get_text("financial_aid.admin_portal.messages.report_exported", "Report exported to:\n{filepath}").format(filepath=filepath)
                )
                log_activity('export', 'financial_aid_report', filepath, {'report_type': filename_base, 'format': 'pdf'})

        except ImportError:
            show_error(
                get_text("financial_aid.admin_portal.dialogs.pdf_library_missing", "PDF Library Missing"),
                get_text("financial_aid.admin_portal.messages.install_reportlab", "Please install reportlab to export to PDF:\npip install reportlab")
            )
        except Exception as e:
            logger.error(f"Error exporting report to PDF: {e}")
            show_error(
                get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"),
                get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e))
            )

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
