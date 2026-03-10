"""Report generation and operations methods mixin for the enhanced reporting GUI."""

from ..standalone.constants import (
    tk, ttk, filedialog, messagebox,
    ScrolledText,
    threading, webbrowser, os, json, logging,
    datetime, timedelta, pd,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
    _t,
    load_templates, generate_report as _service_generate_report,
    generate_enhanced_excel_report as _standalone_generate_enhanced_excel_report,
    generate_interactive_report as _standalone_generate_interactive_report,
)

logger = logging.getLogger(__name__)


class ReportsMixin:
    """Mixin providing report generation and operations methods."""

    def load_recent_reports(self):
        """Load recent reports into the GUI"""
        try:
            # Get reports from the reports directory
            reports_dir = CONFIG.get('reports_dir', 'reports') if ENHANCED_AVAILABLE else 'reports'

            if not os.path.exists(reports_dir):
                return

            reports = []
            for file in os.listdir(reports_dir):
                if file.endswith(('.pdf', '.xlsx', '.html')):
                    file_path = os.path.join(reports_dir, file)
                    stat = os.stat(file_path)

                    reports.append({
                        'name': file,
                        'path': file_path,
                        'generated': datetime.fromtimestamp(stat.st_mtime),
                        'size': stat.st_size,
                        'format': file.split('.')[-1].upper()
                    })

            # Sort by generation time (newest first)
            reports.sort(key=lambda x: x['generated'], reverse=True)

            self.root.after(0, lambda: self._update_reports_tree(reports))

        except Exception as e:
            logger.error(f"Error loading recent reports: {str(e)}")

    def _update_reports_tree(self, reports):
        """Update reports tree in main thread"""
        # Clear existing items
        for item in self.reports_tree.get_children():
            self.reports_tree.delete(item)

        self.reports_data = reports

        for report in reports[:50]:  # Show last 50 reports
            size_mb = report['size'] / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb > 1 else f"{report['size'] / 1024:.1f} KB"

            values = (
                report['name'],
                report['generated'].strftime('%Y-%m-%d %H:%M'),
                report['format'],
                size_str,
                "Available"
            )

            self.reports_tree.insert('', tk.END, values=values)

    def generate_from_template(self):
        """Generate report from selected template"""
        selection = self.template_listbox.curselection()
        if not selection or not hasattr(self, 'templates_data'):
            messagebox.showwarning("No Selection", "Please select a template to generate report.")
            return

        template_data = self.templates_data[selection[0]]

        # Switch to reports tab and set template
        self.notebook.select(1)  # Reports tab
        self.template_combo.set(template_data['name'])

    # Report generation methods

    def generate_report(self):
        """Generate a report using the selected template and parameters"""
        template_name = self.template_combo.get()
        if not template_name:
            messagebox.showwarning("No Template", "Please select a template.")
            return

        try:
            start_date = self.start_date.get()
            end_date = self.end_date.get()
            format_type = self.format_combo.get().lower()

            # Validate dates
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")

        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter valid dates in YYYY-MM-DD format.")
            return

        self.update_status("Generating report...")
        self.start_progress()

        def generate_task():
            try:
                if ENHANCED_AVAILABLE:
                    format_map = {'pdf': 'pdf', 'excel': 'excel', 'interactive html': 'interactive'}
                    report_format = format_map.get(format_type, 'pdf')

                    report_path = _service_generate_report(template_name, start_date, end_date, report_format)

                    if report_path:
                        self.root.after(0, lambda: [
                            self.stop_progress(),
                            self.update_status("Report generated successfully"),
                            self.show_report_success(report_path),
                            self.refresh_reports()
                        ])
                    else:
                        self.root.after(0, lambda: [
                            self.stop_progress(),
                            self.update_status("Report generation failed", "error"),
                            messagebox.showerror("Error", "Failed to generate report")
                        ])
                else:
                    # Fallback for basic functionality
                    self.root.after(0, lambda: [
                        self.stop_progress(),
                        self.update_status("Enhanced reporting not available", "warning"),
                        messagebox.showwarning("Feature Unavailable",
                                             "Enhanced reporting features require the full system to be available.")
                    ])

            except Exception as e:
                self.root.after(0, lambda: [
                    self.stop_progress(),
                    self.update_status(f"Error: {str(e)}", "error"),
                    messagebox.showerror("Error", f"Failed to generate report: {str(e)}")
                ])

        threading.Thread(target=generate_task, daemon=True).start()

    def show_report_success(self, report_path):
        """Show success dialog with options to open/share report"""
        result = messagebox.askyesnocancel("Report Generated",
                                          f"Report generated successfully!\n\nFile: {os.path.basename(report_path)}\n\nWould you like to open it now?")

        if result is True:  # Yes - open report
            try:
                webbrowser.open(f"file://{os.path.abspath(report_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open report: {str(e)}")
        elif result is False:  # No - show in file manager
            try:
                import subprocess
                import platform
                report_dir = os.path.dirname(report_path)
                if platform.system() == 'Windows':
                    os.startfile(report_dir)
                elif platform.system() == 'Darwin':
                    subprocess.run(['open', report_dir], check=False)
                else:
                    subprocess.run(['xdg-open', report_dir], check=False)
            except Exception:
                pass

    def refresh_reports(self):
        """Refresh the reports list"""
        self.load_recent_reports()

    def open_report(self):
        """Open selected report"""
        selection = self.reports_tree.selection()
        if not selection or not hasattr(self, 'reports_data'):
            messagebox.showwarning("No Selection", "Please select a report to open.")
            return

        item = self.reports_tree.item(selection[0])
        report_name = item['values'][0]

        # Find report in data
        report = next((r for r in self.reports_data if r['name'] == report_name), None)
        if report:
            try:
                webbrowser.open(f"file://{os.path.abspath(report['path'])}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open report: {str(e)}")

    def share_report(self):
        """Share selected report"""
        selection = self.reports_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a report to share.")
            return

        # Get selected report
        item = self.reports_tree.item(selection[0])
        report_name = item['values'][0]

        # Find report in data
        report = next((r for r in self.reports_data if r['name'] == report_name), None)
        if not report:
            messagebox.showerror("Error", "Report not found")
            return

        # Create share dialog
        share_dialog = tk.Toplevel(self.root)
        share_dialog.title("Share Report")
        share_dialog.geometry("600x500")
        share_dialog.transient(self.root)
        share_dialog.grab_set()

        main_frame = ttk.Frame(share_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Share Report: {report_name}", font=('Arial', 12, 'bold')).pack(pady=10)

        # Report info
        info_frame = ttk.LabelFrame(main_frame, text="Report Information", padding=10)
        info_frame.pack(fill='x', pady=10)

        ttk.Label(info_frame, text=f"Format: {report['format']}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Size: {report['size'] / 1024:.1f} KB").pack(anchor='w')
        ttk.Label(info_frame, text=f"Generated: {report['generated']}").pack(anchor='w')

        # Email settings
        email_frame = ttk.LabelFrame(main_frame, text="Email Settings", padding=10)
        email_frame.pack(fill='both', expand=True, pady=10)

        ttk.Label(email_frame, text="Recipient Email(s):").pack(anchor='w', pady=(0, 5))
        ttk.Label(email_frame, text="(Separate multiple emails with commas)", font=('Arial', 8)).pack(anchor='w')

        # Get admin email from database
        admin_email = ""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                admin_row = cursor.fetchone()
                if admin_row and admin_row[0]:
                    admin_email = admin_row[0]
        except Exception:
            pass

        recipients_var = tk.StringVar(value=admin_email)
        ttk.Entry(email_frame, textvariable=recipients_var, width=60).pack(fill='x', pady=5)

        ttk.Label(email_frame, text="Subject:").pack(anchor='w', pady=(10, 5))
        subject_var = tk.StringVar(value=f"University Report: {report_name}")
        ttk.Entry(email_frame, textvariable=subject_var, width=60).pack(fill='x', pady=5)

        ttk.Label(email_frame, text="Message:").pack(anchor='w', pady=(10, 5))
        message_text = tk.Text(email_frame, height=8, width=60)
        message_text.pack(fill='both', expand=True, pady=5)
        message_text.insert('1.0', f"""Please find attached the university report: {report_name}

This report was generated on {report['generated']}.

Best regards,
University Reporting System""")

        def send_report():
            recipients = recipients_var.get().strip()
            if not recipients:
                messagebox.showwarning("Missing Recipients", "Please enter at least one recipient email address")
                return

            # Parse recipients
            recipient_list = [email.strip() for email in recipients.split(',')]

            try:
                from education_system.university_system.infrastructure.email.email_service import send_email

                # Get message body
                body = message_text.get('1.0', tk.END)

                # Prepare attachment
                attachments = report['path']

                # Send to each recipient
                success_count = 0
                for recipient_email in recipient_list:
                    try:
                        success = send_email(
                            recipient_email=recipient_email,
                            subject=subject_var.get(),
                            body=body,
                            attachments=attachments
                        )
                        if success:
                            success_count += 1
                    except Exception as e:
                        logging.error(f"Failed to send to {recipient_email}: {str(e)}")

                if success_count > 0:
                    messagebox.showinfo("Report Shared", f"Report sent successfully to {success_count} of {len(recipient_list)} recipient(s)!")
                    share_dialog.destroy()
                else:
                    messagebox.showerror("Share Failed", "Failed to share report with any recipients")

            except Exception as e:
                messagebox.showerror("Share Failed", f"Failed to share report: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Send", command=send_report).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=share_dialog.destroy).pack(side='left', padx=5)

    def delete_report(self):
        """Delete selected report"""
        selection = self.reports_tree.selection()
        if not selection or not hasattr(self, 'reports_data'):
            messagebox.showwarning("No Selection", "Please select a report to delete.")
            return

        item = self.reports_tree.item(selection[0])
        report_name = item['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{report_name}'?"):
            # Find and delete report
            report = next((r for r in self.reports_data if r['name'] == report_name), None)
            if report:
                try:
                    os.remove(report['path'])
                    self.refresh_reports()
                    messagebox.showinfo("Success", "Report deleted successfully!")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete report: {str(e)}")

    def _save_analytics_report(self, content, report_type):
        """Save analytics report to file"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if file_path:
                with open(file_path, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved successfully to:\n{file_path}")
                self.update_status(f"Report saved to {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {str(e)}")
            self.update_status(f"Failed to save report: {str(e)}", "error")

    def _send_report_to_admin(self, content, report_title):
        """Send analytics report to admin via email"""
        try:
            # Get admin email from database
            admin_email = None
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email FROM users
                WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                LIMIT 1
            """)
            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                admin_email = result[0]

            if not admin_email:
                messagebox.showerror("Error", "No admin email found in database.")
                return

            # Save report to temporary file
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            temp_file.write(content)
            temp_file.close()

            # Import email service
            try:
                from education_system.university_system.infrastructure.email.email_service import send_email

                # Send email with attachment
                subject = f"{report_title} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                body = f"""
Dear Administrator,

Please find attached the {report_title} generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

Summary:
{content[:500]}...

Full report is attached.

Best regards,
University Reporting System
"""

                success = send_email(
                    recipient_email=admin_email,
                    subject=subject,
                    body=body,
                    attachments=temp_file.name
                )

                if success:
                    messagebox.showinfo("Success", f"Report sent successfully to:\n{admin_email}")
                    self.update_status(f"Report emailed to admin")
                else:
                    messagebox.showwarning("Warning", "Email may not have been sent. Check email configuration.")

            except ImportError as e:
                messagebox.showerror("Error", f"Email service not available: {str(e)}\nPlease check your email configuration.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send email: {str(e)}")
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send report: {str(e)}")
            self.update_status(f"Failed to send report: {str(e)}", "error")

    def send_scheduled_report_email(self, recipients, report_path, template_name):
        """Send scheduled report via email"""
        try:
            subject = f"Scheduled Report: {template_name}"
            body = f"Please find attached the scheduled report generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}."

            # Note: This is a placeholder. Actual email sending would require SMTP configuration
            logging.info(f"Would send email to {recipients} with report {report_path}")

        except Exception as e:
            logging.error(f"Error sending scheduled report email: {str(e)}")

    def generate_report_method(self, template_name, start_date, end_date, format='pdf'):
        """Generate a report (wrapper method)"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return None

            self.update_status(f"Generating {format.upper()} report...")
            self.start_progress()

            def generate():
                try:
                    report_path = _service_generate_report(template_name, start_date, end_date)

                    if report_path:
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Success", f"Report generated successfully!\n\nLocation: {report_path}"))
                        self.root.after(0, lambda: self.update_status("Report generated", "success"))
                    else:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Failed", "Report generation failed"))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error", f"Report generation failed: {str(e)}"))
                finally:
                    self.root.after(0, self.stop_progress)

            threading.Thread(target=generate, daemon=True).start()
        except Exception as e:
            self.stop_progress()
            messagebox.showerror("Error", f"Failed to start report generation: {str(e)}")

    def generate_enhanced_excel_report(self, template_name, start_date, end_date):
        """Generate enhanced Excel report"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return

            self.update_status("Generating Excel report...")
            self.start_progress()

            def generate():
                try:
                    report_path = _standalone_generate_enhanced_excel_report(template_name, start_date, end_date)

                    if report_path:
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Success", f"Excel report generated!\n\nLocation: {report_path}"))
                    else:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Failed", "Excel report generation failed"))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error", f"Excel generation failed: {str(e)}"))
                finally:
                    self.root.after(0, self.stop_progress)
                    self.root.after(0, lambda: self.update_status("Ready"))

            threading.Thread(target=generate, daemon=True).start()
        except Exception as e:
            self.stop_progress()
            messagebox.showerror("Error", f"Failed to generate Excel report: {str(e)}")

    def generate_interactive_report(self, template_name, start_date, end_date):
        """Generate interactive HTML report"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return

            self.update_status("Generating interactive report...")
            self.start_progress()

            def generate():
                try:
                    report_path = _standalone_generate_interactive_report(template_name, start_date, end_date)

                    if report_path:
                        self.root.after(0, lambda: self.show_visualization_result(
                            report_path, "Interactive Report", is_html=True))
                    else:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Failed", "Interactive report generation failed"))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error", f"Interactive report failed: {str(e)}"))
                finally:
                    self.root.after(0, self.stop_progress)
                    self.root.after(0, lambda: self.update_status("Ready"))

            threading.Thread(target=generate, daemon=True).start()
        except Exception as e:
            self.stop_progress()
            messagebox.showerror("Error", f"Failed to generate interactive report: {str(e)}")

    def generate_advanced_report_menu(self):
        """Show advanced report generation dialog"""
        try:
            self.generate_report_dialog()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show report generation: {str(e)}")

    def generate_interactive_report_menu(self):
        """Show interactive report generation menu"""
        try:
            gen_window = tk.Toplevel(self.root)
            gen_window.title("Generate Interactive Report")
            gen_window.geometry("500x400")
            gen_window.transient(self.root)

            ttk.Label(gen_window, text="Generate Interactive Report",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Form
            form_frame = ttk.LabelFrame(gen_window, text="Report Configuration", padding="10")
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # Template selection
            ttk.Label(form_frame, text="Template:").grid(row=0, column=0, sticky=tk.W, pady=5)
            template_var = tk.StringVar()
            template_combo = ttk.Combobox(form_frame, textvariable=template_var, state='readonly')
            template_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)

            # Load templates
            try:
                templates = load_templates()
                template_names = [t.get('name', 'Unnamed') for t in templates]
                template_combo['values'] = template_names
                if template_names:
                    template_combo.current(0)
            except Exception:
                template_combo['values'] = []

            # Date range
            ttk.Label(form_frame, text="Start Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=5)
            start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
            ttk.Entry(form_frame, textvariable=start_date_var).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)

            ttk.Label(form_frame, text="End Date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
            end_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
            ttk.Entry(form_frame, textvariable=end_date_var).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)

            form_frame.columnconfigure(1, weight=1)

            # Buttons
            button_frame = ttk.Frame(gen_window)
            button_frame.pack(pady=10)

            def generate_action():
                template_name = template_var.get()
                if not template_name:
                    messagebox.showwarning("Validation", "Please select a template")
                    return

                self.generate_interactive_report(template_name, start_date_var.get(), end_date_var.get())
                gen_window.destroy()

            ttk.Button(button_frame, text="Generate", command=generate_action,
                      style='Success.TButton').pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=gen_window.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show generation dialog: {str(e)}")
