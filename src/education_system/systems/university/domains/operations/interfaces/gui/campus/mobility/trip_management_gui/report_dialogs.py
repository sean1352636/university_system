
from education_system.systems.university.infrastructure.i18n import get_text as _t
import html
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.simpledialog import Dialog
from datetime import datetime
import logging

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._imports import (
    logger,
    PDF_AVAILABLE,
    EMAIL_SERVICE_AVAILABLE,
    TEMPLATE_AVAILABLE,
    TRIP_REPORTS_AVAILABLE,
    TripReportGenerator,
    send_email,
)
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, run_async, show_error,
)

if TEMPLATE_AVAILABLE:
    from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._imports import render_template

_K = 'gui.operations.campus.mobility.trip_management_gui.report_dialogs'


def build_report(auth, report_type, trip_id=None):
    """``(content, data)`` for a report — runs on a worker thread.

    The data come from the domain's ``TripReportGenerator`` on the domain's
    read connection; special-category fields appear only as "recorded".
    """
    generator = TripReportGenerator(auth)
    with tm('database').read_connection() as conn:
        if report_type == "TRIP_SUMMARY":
            data = generator.get_trip_summary_data(conn)
        elif report_type == "PARTICIPANT_LIST":
            data = generator.get_participant_report_data(conn, trip_id)
        elif report_type == "FINANCIAL_REPORT":
            data = generator.get_financial_report_data(conn)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
    return generator.generate_report_content_as_string(data, report_type), data


class ReportGeneratorDialog(Dialog):
    def __init__(self, parent, auth, report_type, log_widget):
        self.auth = auth
        self.report_type = report_type
        self.log_widget = log_widget
        super().__init__(parent, f"Generate {report_type.replace('_', ' ').title()} Report")

    def body(self, master):
        ttk.Label(master, text=f"Report Type: {self.report_type.replace('_', ' ').title()}",
                  font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        ttk.Label(master, text=_t(f"{_K}.labels.select_format", default="Select format:")).pack(anchor=tk.W)
        self.format_var = tk.StringVar(value="TXT")
        format_frame = ttk.Frame(master)
        format_frame.pack(fill=tk.X, pady=5)
        ttk.Radiobutton(format_frame, text=_t(f"{_K}.buttons.text_txt", default="Text (TXT)"), variable=self.format_var,
                        value="TXT").pack(side=tk.LEFT, padx=(0, 20))
        if PDF_AVAILABLE:
            ttk.Radiobutton(format_frame, text=_t(f"{_K}.buttons.pdf", default="PDF"), variable=self.format_var,
                            value="PDF").pack(side=tk.LEFT)

        if self.report_type == "PARTICIPANT_LIST":
            ttk.Label(master, text=_t(f"{_K}.labels.options", default="Options:")).pack(anchor=tk.W, pady=(20, 5))
            self.specific_trip_var = tk.BooleanVar()
            ttk.Checkbutton(master, text=_t(f"{_K}.buttons.generate_for_specific_trip_only", default="Generate for specific trip only"),
                            variable=self.specific_trip_var,
                            command=self.toggle_trip_selection).pack(anchor=tk.W)
            self.trip_selection_frame = ttk.Frame(master)
            self.trip_selection_frame.pack(fill=tk.X, pady=5)
            ttk.Label(self.trip_selection_frame, text=_t(f"{_K}.labels.select_trip", default="Select trip:")).pack(side=tk.LEFT)
            self.trip_var = tk.StringVar()
            self.trip_combo = ttk.Combobox(self.trip_selection_frame, textvariable=self.trip_var,
                                           state="disabled", width=40)
            self.trip_combo.pack(side=tk.LEFT, padx=(5, 0))
            self.load_trips_for_selection()
        return None

    def toggle_trip_selection(self):
        self.trip_combo.config(state="readonly" if self.specific_trip_var.get() else "disabled")

    def load_trips_for_selection(self):
        try:
            trips = tm('trips').list_trips(include_archived=True)
        except Exception as exc:
            show_error(self, exc)
            return
        self.trip_combo['values'] = [f"{t['id']} - {t['trip_name']}" for t in trips]

    def validate(self):
        if (self.report_type == "PARTICIPANT_LIST" and self.specific_trip_var.get()
                and not self.trip_var.get()):
            messagebox.showwarning(_t(f"{_K}.dialogs.no_selection", default="No Selection"),
                                   _t(f"{_K}.dialogs.pick_trip", default="Pick the trip, or untick 'specific trip only'."),
                                   parent=self)
            return False
        return True

    def apply(self):
        """Generate the report on a worker thread; results come back via ``after``."""
        trip_id = None
        if self.report_type == "PARTICIPANT_LIST" and self.specific_trip_var.get():
            trip_id = int(self.trip_var.get().split(' - ')[0])
        format_type = self.format_var.get()
        parent = self.parent
        auth, report_type = self.auth, self.report_type
        log = self.log_message

        if not TRIP_REPORTS_AVAILABLE or TripReportGenerator is None:
            log("Trip report generator module is not available in this environment.")
            messagebox.showerror(_t(f"{_K}.dialogs.reports_unavailable", default="Reports Unavailable"),
                                 _t(f"{_K}.dialogs.trip_report_generation_support_is_not_installed", default="Trip report generation support is not installed."),
                                 parent=parent)
            return
        if not auth or not auth.current_user:
            messagebox.showerror(_t(f"{_K}.dialogs.authentication_required", default="Authentication Required"),
                                 _t(f"{_K}.dialogs.you_must_be_logged_in_to_generate_reports", default="You must be logged in to generate reports."),
                                 parent=parent)
            return
        if not auth.check_permission('view_trip_reports'):
            messagebox.showerror(_t(f"{_K}.dialogs.permission_denied", default="Permission Denied"),
                                 _t(f"{_K}.dialogs.you_do_not_have_permission_to_generate_trip_reports", default="You do not have permission to generate trip reports."),
                                 parent=parent)
            return
        if report_type == "FINANCIAL_REPORT" and not auth.check_permission('view_financial_reports'):
            messagebox.showerror(_t(f"{_K}.dialogs.permission_denied", default="Permission Denied"),
                                 _t(f"{_K}.dialogs.you_do_not_have_permission_to_generate_financial_reports", default="You do not have permission to generate financial reports."),
                                 parent=parent)
            return

        pdf_path = None
        if format_type == "PDF":
            pdf_path = filedialog.asksaveasfilename(
                parent=parent, defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            if not pdf_path:
                return

        log("Starting report generation...")

        def work():
            content, data = build_report(auth, report_type, trip_id)
            if pdf_path:
                TripReportGenerator(auth).generate_pdf_report(data, report_type, pdf_path)
            return content, data

        def done(result):
            content, data = result
            log("✓ Report generated successfully" + (f" ({pdf_path})" if pdf_path else ""))
            if pdf_path:
                messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"),
                                    f"Report exported successfully to:\n{pdf_path}", parent=parent)
            ReportViewerDialog(parent, auth, content, data, report_type)

        def failed(exc):
            logging.error("Error generating report: %s", exc)
            log(f"✗ Error generating report: {exc}")
            show_error(parent, exc, _t(f"{_K}.dialogs.report_error", default="Report Error"))

        run_async(parent, work, done, failed)

    def log_message(self, message):
        """Log message to the report log widget (Tk thread only)."""
        widget = self.log_widget
        if not widget:
            return
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            widget.insert(tk.END, f"[{timestamp}] {message}\n")
            widget.see(tk.END)
        except tk.TclError:
            logger.debug("report log widget gone")


class ReportViewerDialog(tk.Toplevel):
    """Dialog to view and export trip reports"""

    def __init__(self, parent, auth, report_content, report_data, report_type):
        super().__init__(parent)
        self.auth = auth
        self.report_content = report_content
        self.report_data = report_data
        self.report_type = report_type

        self.title(f"{report_type.replace('_', ' ').title()} Report")
        self.geometry("900x700")
        self.transient(parent)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.create_widgets()
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def create_widgets(self):
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=f"{self.report_type.replace('_', ' ').title()} Report",
                  font=('Arial', 14, 'bold')).pack()
        ttk.Label(header_frame,
                  text=f"Generated: {self.report_data['generated_at']} by {self.report_data['generated_by']}",
                  font=('Arial', 9)).pack()

        # Buttons first so the report text cannot push them off screen.
        button_frame = ttk.Frame(self)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text=_t(f"{_K}.buttons.export_as_txt", default="Export as TXT"), command=self.export_as_txt).pack(side=tk.LEFT, padx=5)
        if PDF_AVAILABLE:
            ttk.Button(button_frame, text=_t(f"{_K}.buttons.export_as_pdf", default="Export as PDF"), command=self.export_as_pdf).pack(side=tk.LEFT, padx=5)
        if EMAIL_SERVICE_AVAILABLE:
            ttk.Button(button_frame, text=_t(f"{_K}.buttons.send_to_admin", default="Send to Admin"), command=self.send_to_admin).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t(f"{_K}.buttons.close", default="Close"), command=self.destroy).pack(side=tk.RIGHT, padx=5)

        content_frame = ttk.LabelFrame(self, text=_t(f"{_K}.labels.report_content", default="Report Content"))
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        text_scroll = ttk.Scrollbar(content_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll = ttk.Scrollbar(content_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.report_text = tk.Text(content_frame, wrap=tk.NONE, yscrollcommand=text_scroll.set,
                                   xscrollcommand=h_scroll.set, font=('Courier', 9))
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        text_scroll.config(command=self.report_text.yview)
        h_scroll.config(command=self.report_text.xview)
        self.report_text.insert(1.0, self.report_content)
        self.report_text.config(state=tk.DISABLED)

    def export_as_txt(self):
        try:
            filename = filedialog.asksaveasfilename(
                parent=self, defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"{self.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.report_content)
                messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), f"Report exported successfully to:\n{filename}", parent=self)
                logging.info(f"Report exported as TXT: {filename}")
        except Exception as e:
            show_error(self, e, _t(f"{_K}.dialogs.export_error", default="Export Error"))

    def export_as_pdf(self):
        if not PDF_AVAILABLE:
            messagebox.showerror(_t(f"{_K}.dialogs.pdf_not_available", default="PDF Not Available"),
                                 _t(f"{_K}.dialogs.pdf_export_is_not_available_reportlab_library_is_required", default="PDF export is not available. ReportLab library is required."),
                                 parent=self)
            return
        filename = filedialog.asksaveasfilename(
            parent=self, defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"{self.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        if not filename:
            return
        auth, data, report_type = self.auth, self.report_data, self.report_type

        def done(_):
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), f"Report exported successfully to:\n{filename}", parent=self)

        run_async(self, lambda: TripReportGenerator(auth).generate_pdf_report(data, report_type, filename), done,
                  lambda exc: show_error(self, exc, _t(f"{_K}.dialogs.export_error", default="Export Error")))

    def send_to_admin(self):
        if not EMAIL_SERVICE_AVAILABLE:
            messagebox.showerror(_t(f"{_K}.dialogs.email_not_available", default="Email Not Available"),
                                 _t(f"{_K}.dialogs.email_service_is_not_available_please_contact_support", default="Email service is not available. Please contact support."),
                                 parent=self)
            return
        admins = TripReportGenerator(self.auth).get_admin_emails()
        if not admins:
            messagebox.showerror(_t(f"{_K}.dialogs.no_admins_found", default="No Admins Found"),
                                 _t(f"{_K}.dialogs.no_admin_users_with_email_addresses_found", default="No admin users with email addresses found."),
                                 parent=self)
            return

        admin_dialog = tk.Toplevel(self)
        admin_dialog.title(_t(f"{_K}.windows.select_admin_recipients", default="Select Admin Recipients"))
        admin_dialog.geometry("400x300")
        admin_dialog.transient(self)
        ttk.Label(admin_dialog, text=_t(f"{_K}.labels.select_admin_recipients", default="Select admin recipients:"),
                  font=('Arial', 10, 'bold')).pack(pady=10)
        button_frame = ttk.Frame(admin_dialog)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        list_frame = ttk.Frame(admin_dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        admin_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set)
        admin_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=admin_listbox.yview)
        for admin in admins:
            admin_listbox.insert(tk.END, f"{admin['name']} ({admin['email']})")
        admin_listbox.select_set(0, tk.END)

        report_type, data, content = self.report_type, self.report_data, self.report_content

        def send_all(selected):
            sent = 0
            for admin in selected:
                try:
                    subject = body = None
                    if TEMPLATE_AVAILABLE:
                        try:
                            subject, body = render_template('trip_management_report', {
                                'admin_name': admin['name'],
                                'report_title': report_type.replace('_', ' ').title(),
                                'generated_at': data['generated_at'],
                                'report_content': html.escape(content),
                                'separator': '=' * 80,
                            })
                        except Exception as template_error:
                            logger.warning("Failed to render template: %s. Using fallback email.", template_error)
                    if not subject or not body:
                        subject = f"Trip Management Report: {report_type.replace('_', ' ').title()}"
                        body = (f"Dear {admin['name']},\n\nPlease find attached the "
                                f"{report_type.replace('_', ' ').title()} report.\n\n"
                                f"Report Details:\n- Type: {report_type.replace('_', ' ').title()}\n"
                                f"- Generated: {data['generated_at']}\n- Generated by: {data['generated_by']}\n\n"
                                "This is an automatically generated report from the Trip Management System.\n\n"
                                "Best regards,\nTrip Management System\n")
                    from education_system.paths import UNIVERSITY_TEMP_DIR
                    temp_file = UNIVERSITY_TEMP_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.txt"
                    temp_file.parent.mkdir(parents=True, exist_ok=True)
                    temp_file.write_text(content, encoding='utf-8')
                    try:
                        send_email(recipient_email=admin['email'], subject=subject, body=body,
                                   attachments=[str(temp_file)])
                    finally:
                        try:
                            temp_file.unlink()
                        except OSError as e:
                            logger.debug(f"Failed to delete temporary file {temp_file}: {e}")
                    sent += 1
                except Exception as e:
                    logging.error(f"Error sending email to {admin['email']}: {e}")
            return sent, len(selected)

        def send_emails():
            selected_indices = admin_listbox.curselection()
            if not selected_indices:
                messagebox.showwarning(_t(f"{_K}.dialogs.no_selection", default="No Selection"), _t(f"{_K}.dialogs.please_select_at_least_one_admin", default="Please select at least one admin."), parent=admin_dialog)
                return
            selected = [admins[i] for i in selected_indices]
            admin_dialog.destroy()
            run_async(self, lambda: send_all(selected), lambda r: messagebox.showinfo(
                _t(f"{_K}.dialogs.email_sent", default="Email Sent"),
                tf(f"{_K}.dialogs.sent_count", "Report sent successfully to {sent} of {total} admin(s).",
                   sent=r[0], total=r[1]), parent=self))

        ttk.Button(button_frame, text=_t(f"{_K}.buttons.send", default="Send"), command=send_emails).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t(f"{_K}.buttons.cancel", default="Cancel"), command=admin_dialog.destroy).pack(side=tk.RIGHT, padx=5)
