import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.simpledialog import Dialog
from datetime import datetime
from threading import Thread
import logging

from education_system.university_system.modules.domain.mobility.gui.trip_management_gui._imports import (
    safe_db_operation,
    logger,
    PDF_AVAILABLE,
    EMAIL_SERVICE_AVAILABLE,
    TEMPLATE_AVAILABLE,
    TRIP_REPORTS_AVAILABLE,
    TripReportGenerator,
    send_email,
)

if TEMPLATE_AVAILABLE:
    from education_system.university_system.modules.domain.mobility.gui.trip_management_gui._imports import render_template


class ReportGeneratorDialog(Dialog):
    def __init__(self, parent, auth, report_type, log_widget):
        self.auth = auth
        self.report_type = report_type
        self.log_widget = log_widget
        super().__init__(parent, f"Generate {report_type.replace('_', ' ').title()} Report")

    def body(self, master):
        """Create the dialog body"""
        # Report type display
        ttk.Label(master, text=f"Report Type: {self.report_type.replace('_', ' ').title()}",
                 font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        # Format selection
        ttk.Label(master, text="Select format:").pack(anchor=tk.W)
        self.format_var = tk.StringVar(value="TXT")

        format_frame = ttk.Frame(master)
        format_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(format_frame, text="Text (TXT)", variable=self.format_var,
                       value="TXT").pack(side=tk.LEFT, padx=(0, 20))

        if PDF_AVAILABLE:
            ttk.Radiobutton(format_frame, text="PDF", variable=self.format_var,
                           value="PDF").pack(side=tk.LEFT)

        # Specific options for participant reports
        if self.report_type == "PARTICIPANT_LIST":
            ttk.Label(master, text="Options:").pack(anchor=tk.W, pady=(20, 5))

            self.specific_trip_var = tk.BooleanVar()
            ttk.Checkbutton(master, text="Generate for specific trip only",
                           variable=self.specific_trip_var,
                           command=self.toggle_trip_selection).pack(anchor=tk.W)

            self.trip_selection_frame = ttk.Frame(master)
            self.trip_selection_frame.pack(fill=tk.X, pady=5)

            ttk.Label(self.trip_selection_frame, text="Select trip:").pack(side=tk.LEFT)
            self.trip_var = tk.StringVar()
            self.trip_combo = ttk.Combobox(self.trip_selection_frame, textvariable=self.trip_var,
                                          state="disabled", width=40)
            self.trip_combo.pack(side=tk.LEFT, padx=(5, 0))

            self.load_trips_for_selection()

        return None

    def toggle_trip_selection(self):
        """Toggle trip selection availability"""
        if self.specific_trip_var.get():
            self.trip_combo.config(state="readonly")
        else:
            self.trip_combo.config(state="disabled")

    def load_trips_for_selection(self):
        """Load trips for selection"""
        def get_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT id, trip_name FROM trips ORDER BY trip_name')
            return cursor.fetchall()

        trips = safe_db_operation(get_trips_operation)

        if trips:
            trip_list = [f"{trip[0]} - {trip[1]}" for trip in trips]
            self.trip_combo['values'] = trip_list

    def apply(self):
        """Generate the report"""
        try:
            # Determine trip ID for participant reports
            trip_id = None
            if (self.report_type == "PARTICIPANT_LIST" and
                hasattr(self, 'specific_trip_var') and
                self.specific_trip_var.get()):

                trip_selection = self.trip_var.get()
                if trip_selection:
                    trip_id = int(trip_selection.split(' - ')[0])

            format_type = self.format_var.get()
            parent_widget = getattr(self, "parent", None) or self.log_widget

            def log_async(message):
                if parent_widget:
                    try:
                        parent_widget.after(0, lambda m=message: self.log_message(m))
                    except Exception as e:
                        logger.debug(f"Failed to schedule async log message: {e}")
                else:
                    self.log_message(message)

            if not TRIP_REPORTS_AVAILABLE or TripReportGenerator is None:
                log_async("Trip report generator module is not available in this environment.")
                messagebox.showerror("Reports Unavailable",
                                     "Trip report generation support is not installed.")
                return

            if not self.auth or not self.auth.current_user:
                log_async("You must be logged in to generate reports.")
                messagebox.showerror("Authentication Required",
                                     "You must be logged in to generate reports.")
                return

            if not self.auth.check_permission('view_trip_reports'):
                log_async("You do not have permission to generate reports.")
                messagebox.showerror("Permission Denied",
                                     "You do not have permission to generate trip reports.")
                return

            if (self.report_type == "FINANCIAL_REPORT"
                    and not self.auth.check_permission('view_financial_reports')):
                log_async("Financial reports require additional permissions.")
                messagebox.showerror("Permission Denied",
                                     "You do not have permission to generate financial reports.")
                return

            log_async("Starting report generation...")

            def generate_report_thread():
                def show_viewer(report_content, report_data):
                    if parent_widget:
                        try:
                            parent_widget.after(0, lambda: ReportViewerDialog(
                                parent_widget,
                                self.auth,
                                report_content,
                                report_data,
                                self.report_type
                            ))
                        except Exception as e:
                            logger.debug(f"Failed to show report preview dialog: {e}")

                def notify_error(message):
                    if parent_widget:
                        try:
                            parent_widget.after(0, lambda: messagebox.showerror("Report Error", message))
                        except Exception as e:
                            logger.debug(f"Failed to show error dialog: {e}")

                def log_message(message):
                    if parent_widget:
                        try:
                            parent_widget.after(0, lambda m=message: self.log_message(m))
                        except Exception as e:
                            logger.debug(f"Failed to schedule async log message: {e}")

                try:
                    report_generator = TripReportGenerator(self.auth)

                    def generate_operation(conn):
                        # Get report data
                        if self.report_type == "TRIP_SUMMARY":
                            data = report_generator.get_trip_summary_data(conn)
                        elif self.report_type == "PARTICIPANT_LIST":
                            data = report_generator.get_participant_report_data(conn, trip_id)
                        elif self.report_type == "FINANCIAL_REPORT":
                            data = report_generator.get_financial_report_data(conn)
                        else:
                            raise ValueError(f"Unknown report type: {self.report_type}")

                        # Generate report content as string for viewing
                        report_content = report_generator.generate_report_content_as_string(
                            data, self.report_type
                        )

                        return report_content, data

                    result = safe_db_operation(generate_operation)

                    if not result:
                        log_message("\u2717 Failed to generate report.")
                        notify_error("Report generation failed. Please check the logs for details.")
                        return

                    report_content, report_data = result
                    log_message(f"\u2713 Report generated successfully")

                    # Show report viewer dialog
                    show_viewer(report_content, report_data)

                except Exception as e:
                    error_msg = f"Error generating report: {e}"
                    logging.error(error_msg)
                    log_message(f"\u2717 {error_msg}")
                    notify_error(error_msg)

            # Run in background thread
            Thread(target=generate_report_thread, daemon=True).start()

        except Exception as e:
            error_msg = f"Error starting report generation: {e}"
            self.log_message(f"\u2717 {error_msg}")
            messagebox.showerror("Error", error_msg)

    def log_message(self, message):
        """Log message to the report log widget"""
        if self.log_widget:
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.log_widget.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_widget.see(tk.END)
            self.log_widget.update_idletasks()


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

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        self.create_widgets()

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def create_widgets(self):
        """Create dialog widgets"""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame,
                 text=f"{self.report_type.replace('_', ' ').title()} Report",
                 font=('Arial', 14, 'bold')).pack()

        ttk.Label(header_frame,
                 text=f"Generated: {self.report_data['generated_at']} by {self.report_data['generated_by']}",
                 font=('Arial', 9)).pack()

        # Report content area
        content_frame = ttk.LabelFrame(self, text="Report Content")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Text widget with scrollbar
        text_scroll = ttk.Scrollbar(content_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.report_text = tk.Text(content_frame, wrap=tk.NONE, yscrollcommand=text_scroll.set,
                                   font=('Courier', 9))
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        text_scroll.config(command=self.report_text.yview)

        # Insert report content
        self.report_text.insert(1.0, self.report_content)
        self.report_text.config(state=tk.DISABLED)  # Make read-only

        # Horizontal scrollbar
        h_scroll = ttk.Scrollbar(content_frame, orient=tk.HORIZONTAL, command=self.report_text.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.report_text.config(xscrollcommand=h_scroll.set)

        # Buttons frame
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Export buttons
        ttk.Button(button_frame, text="Export as TXT", command=self.export_as_txt).pack(side=tk.LEFT, padx=5)

        if PDF_AVAILABLE:
            ttk.Button(button_frame, text="Export as PDF", command=self.export_as_pdf).pack(side=tk.LEFT, padx=5)

        # Send to admin button
        if EMAIL_SERVICE_AVAILABLE:
            ttk.Button(button_frame, text="Send to Admin", command=self.send_to_admin).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text="Close", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def export_as_txt(self):
        """Export report as TXT file"""
        try:
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"{self.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.report_content)

                messagebox.showinfo("Success", f"Report exported successfully to:\n{filename}")
                logging.info(f"Report exported as TXT: {filename}")

        except Exception as e:
            error_msg = f"Error exporting report as TXT: {e}"
            logging.error(error_msg)
            messagebox.showerror("Export Error", error_msg)

    def export_as_pdf(self):
        """Export report as PDF file"""
        if not PDF_AVAILABLE:
            messagebox.showerror("PDF Not Available",
                               "PDF export is not available. ReportLab library is required.")
            return

        try:
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"{self.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )

            if filename:
                # Generate PDF using TripReportGenerator
                report_generator = TripReportGenerator(self.auth)
                report_generator.generate_pdf_report(self.report_data, self.report_type, filename)

                messagebox.showinfo("Success", f"Report exported successfully to:\n{filename}")
                logging.info(f"Report exported as PDF: {filename}")

        except Exception as e:
            error_msg = f"Error exporting report as PDF: {e}"
            logging.error(error_msg)
            messagebox.showerror("Export Error", error_msg)

    def send_to_admin(self):
        """Send report to admin users via email"""
        if not EMAIL_SERVICE_AVAILABLE:
            messagebox.showerror("Email Not Available",
                               "Email service is not available. Please contact support.")
            return

        try:
            # Get admin emails
            report_generator = TripReportGenerator(self.auth)
            admins = report_generator.get_admin_emails()

            if not admins:
                messagebox.showerror("No Admins Found",
                                   "No admin users with email addresses found.")
                return

            # Create admin selection dialog
            admin_dialog = tk.Toplevel(self)
            admin_dialog.title("Select Admin Recipients")
            admin_dialog.geometry("400x300")
            admin_dialog.transient(self)
            admin_dialog.grab_set()

            ttk.Label(admin_dialog, text="Select admin recipients:",
                     font=('Arial', 10, 'bold')).pack(pady=10)

            # Listbox for admin selection
            list_frame = ttk.Frame(admin_dialog)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            admin_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE,
                                      yscrollcommand=scrollbar.set)
            admin_listbox.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=admin_listbox.yview)

            # Populate listbox
            for admin in admins:
                admin_listbox.insert(tk.END, f"{admin['name']} ({admin['email']})")

            # Select all by default
            admin_listbox.select_set(0, tk.END)

            # Buttons
            button_frame = ttk.Frame(admin_dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            def send_emails():
                selected_indices = admin_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("No Selection", "Please select at least one admin.")
                    return

                selected_admins = [admins[i] for i in selected_indices]

                # Close selection dialog
                admin_dialog.destroy()

                # Send emails in background thread
                def send_email_thread():
                    success_count = 0
                    for admin in selected_admins:
                        try:
                            # Try to use template first, fall back to hardcoded email
                            try:
                                if TEMPLATE_AVAILABLE:
                                    subject, body = render_template('trip_management_report', {
                                        'admin_name': admin['name'],
                                        'report_title': self.report_type.replace('_', ' ').title(),
                                        'generated_at': self.report_data['generated_at'],
                                        'report_content': self.report_content,
                                        'separator': '=' * 80
                                    })
                                else:
                                    raise Exception("Template not available")
                            except Exception as template_error:
                                logger.warning(f"Failed to render template: {template_error}. Using fallback email.")
                                subject = f"Trip Management Report: {self.report_type.replace('_', ' ').title()}"
                                body = f"""Dear {admin['name']},

Please find attached the {self.report_type.replace('_', ' ').title()} report.

Report Details:
- Type: {self.report_type.replace('_', ' ').title()}
- Generated: {self.report_data['generated_at']}
- Generated by: {self.report_data['generated_by']}

This is an automatically generated report from the Trip Management System.

Best regards,
Trip Management System
"""

                            # Create temporary file for attachment
                            from education_system.university_system.modules.shared.constants.paths import TEMP_DIR
                            temp_file = TEMP_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                            temp_file.parent.mkdir(parents=True, exist_ok=True)

                            with open(temp_file, 'w', encoding='utf-8') as f:
                                f.write(self.report_content)

                            # Send email
                            send_email(
                                recipient_email=admin['email'],
                                subject=subject,
                                body=body,
                                attachments=[str(temp_file)]
                            )

                            # Clean up temp file
                            try:
                                temp_file.unlink()
                            except Exception as e:
                                logger.debug(f"Failed to delete temporary file {temp_file}: {e}")

                            success_count += 1
                            logging.info(f"Report sent to {admin['email']}")

                        except Exception as e:
                            logging.error(f"Error sending email to {admin['email']}: {e}")

                    # Show result
                    self.after(0, lambda: messagebox.showinfo(
                        "Email Sent",
                        f"Report sent successfully to {success_count} of {len(selected_admins)} admin(s)."
                    ))

                Thread(target=send_email_thread, daemon=True).start()

            ttk.Button(button_frame, text="Send", command=send_emails).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=admin_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            error_msg = f"Error sending report to admin: {e}"
            logging.error(error_msg)
            messagebox.showerror("Email Error", error_msg)
