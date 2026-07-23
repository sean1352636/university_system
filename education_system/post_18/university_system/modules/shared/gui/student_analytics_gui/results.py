"""Results display, reports, email, and export mixin for the Student Analytics GUI."""
from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    plt, pd, json, datetime, _t, CONFIG,
)


class ResultsMixin:
    """Mixin providing result display, report generation, email, and export methods."""

    def display_results_window(self, title, summary_text, figure=None):
        """Display analysis results in a GUI window with action buttons"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("900x700")
        dialog.transient(self.root)

        def on_dialog_close():
            """Clean up figure when dialog closes"""
            try:
                if figure:
                    plt.close(figure)
            except Exception:
                pass
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        # Create main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=title, font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))

        # Text results frame
        text_frame = ttk.LabelFrame(main_frame, text=_t("analytics.analysis_results", default="Analysis Results"), padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Scrolled text widget
        text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=15, font=('Courier', 10))
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert('1.0', summary_text)
        text_widget.config(state='disabled')

        # Action buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text=_t("analytics.view_chart", default="View Chart"),
                  command=lambda: plt.show() if figure else None).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("analytics.save_report", default="Save Report"),
                  command=lambda: self.save_analysis_report(title, summary_text, figure)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("analytics.copy_to_clipboard", default="Copy to Clipboard"),
                  command=lambda: self.copy_to_clipboard(summary_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("analytics.email_report", default="Email Report"),
                  command=lambda: self.email_report(title, summary_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("analytics.send_to_admin", default="Send to Admin"),
                  command=lambda: self.send_to_admin(title, summary_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("common.close", default="Close"),
                  command=on_dialog_close).pack(side=tk.RIGHT, padx=5)

    def send_to_admin(self, title, summary_text):
        """Quick send report to admin email"""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_db_connection

            # Get admin email
            admin_email = "admin@university.edu"  # Default
            try:
                with get_db_connection() as conn:
                    cursor = conn.execute("""
                        SELECT email FROM users
                        WHERE role = 'admin'
                        LIMIT 1
                    """)
                    admin_row = cursor.fetchone()
                    if admin_row and admin_row[0]:
                        admin_email = admin_row[0]
            except Exception:
                pass

            # Confirm before sending
            if messagebox.askyesno(_t("common.confirm"),
                                  _t("analytics.confirm_send_to_admin", email=admin_email)):
                self._send_report_email(admin_email, title, summary_text)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("analytics.error.send_to_admin", error=str(e)))

    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo(_t("common.success"), _t("analytics.messages.copied_to_clipboard"))

    def save_analysis_report(self, title, summary_text, figure=None):
        """Save analysis report to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                (_t("analytics.file_types.text"), "*.txt"),
                (_t("analytics.file_types.pdf"), "*.pdf"),
                (_t("analytics.file_types.all"), "*.*")
            ],
            title=_t("analytics.dialogs.save_analysis_report")
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(f"{title}\n")
                    f.write("="*80 + "\n\n")
                    f.write(summary_text)
                    f.write(f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                messagebox.showinfo(_t("common.success"), _t("analytics.messages.report_saved", filename=filename))
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("analytics.error.save_report", error=str(e)))

    def email_report(self, title, summary_text, recipient=None):
        """Send report via email to admin or specified recipient"""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_db_connection

            # If no recipient specified, get admin email from database
            if not recipient:
                # Create dialog to select recipient
                email_dialog = tk.Toplevel(self.root)
                email_dialog.title(_t("analytics.dialogs.email_report"))
                email_dialog.geometry("500x250")
                email_dialog.transient(self.root)
                email_dialog.grab_set()

                main_frame = ttk.Frame(email_dialog, padding="20")
                main_frame.pack(fill=tk.BOTH, expand=True)

                ttk.Label(main_frame, text=_t("analytics.labels.send_report_to"), font=('Arial', 12, 'bold')).pack(pady=(0, 10))

                # Radio buttons for recipient selection
                recipient_var = tk.StringVar(value="admin")

                # Get admin email
                admin_email = "admin@university.edu"  # Default
                try:
                    with get_db_connection() as conn:
                        cursor = conn.execute("""
                            SELECT email FROM users
                            WHERE role = 'admin'
                            LIMIT 1
                        """)
                        admin_row = cursor.fetchone()
                        if admin_row and admin_row[0]:
                            admin_email = admin_row[0]
                except Exception:
                    pass

                ttk.Radiobutton(main_frame, text=_t("analytics.labels.admin_recipient", email=admin_email),
                               variable=recipient_var, value="admin").pack(anchor=tk.W, pady=5)
                ttk.Radiobutton(main_frame, text=_t("analytics.labels.current_user"),
                               variable=recipient_var, value="self").pack(anchor=tk.W, pady=5)
                ttk.Radiobutton(main_frame, text=_t("analytics.labels.custom_email"),
                               variable=recipient_var, value="custom").pack(anchor=tk.W, pady=5)

                custom_email_entry = ttk.Entry(main_frame, width=40)
                custom_email_entry.pack(pady=5, padx=20)

                def send_email():
                    choice = recipient_var.get()

                    if choice == "admin":
                        final_recipient = admin_email
                    elif choice == "self":
                        # Get current user email
                        try:
                            from education_system.post_18.university_system.infrastructure.shared_context import get_auth
                            auth = get_auth()
                            if auth.current_user:
                                user = auth.current_user
                                final_recipient = user.get('email', '')
                                if not final_recipient:
                                    messagebox.showerror(_t("common.error"), _t("analytics.error.no_email_address"))
                                    return
                            else:
                                messagebox.showerror(_t("common.error"), _t("analytics.error.no_user_logged_in"))
                                return
                        except Exception as e:
                            messagebox.showerror(_t("common.error"), _t("analytics.error.get_user_email", error=str(e)))
                            return
                    else:  # custom
                        final_recipient = custom_email_entry.get().strip()
                        if not final_recipient:
                            messagebox.showerror(_t("common.error"), _t("analytics.error.enter_email_address"))
                            return

                    # Send the email
                    self._send_report_email(final_recipient, title, summary_text)
                    email_dialog.destroy()

                button_frame = ttk.Frame(main_frame)
                button_frame.pack(pady=20)

                ttk.Button(button_frame, text=_t("common.send"), command=send_email).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text=_t("common.cancel"), command=email_dialog.destroy).pack(side=tk.LEFT, padx=5)

            else:
                # Direct send to specified recipient
                self._send_report_email(recipient, title, summary_text)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("analytics.error.prepare_email", error=str(e)))

    def _send_report_email(self, recipient, title, summary_text):
        """Actually send the email report"""
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service import send_email

            # Build email body
            email_body = f"""
Analytics Report: {title}
{'='*80}

{summary_text}

{'='*80}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
This is an automated report from the University Management System.
"""

            # Send email immediately using the email service
            subject = f"Analytics Report: {title}"
            success = send_email(recipient, subject, email_body)

            if success:
                messagebox.showinfo(_t("common.success"),
                                  _t("analytics.messages.email_sent", recipient=recipient))
            else:
                messagebox.showwarning(_t("common.warning"),
                                     _t("analytics.messages.email_logged_warning"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("analytics.error.send_email", error=str(e)))

    def custom_report_builder(self):
        """Custom report builder for GUI"""
        print("Custom report builder would open a dialog in GUI version")

    def export_data(self):
        """Export data functionality for GUI"""
        print("Export data would open export dialog in GUI version")

    def email_reports(self):
        """Send email reports - GUI compatible stub"""
        print("Email functionality would be implemented here")
        print("This requires SMTP configuration and recipient setup")

    def send_email_with_attachment(self, recipient, subject, report_type):
        """Send email with attachment - GUI compatible stub"""
        print(f"Would send {report_type} report to {recipient} with subject: {subject}")

    def data_quality_check(self):
        """Perform data quality check"""
        print("Performing data quality check...")

        students_df = self.get_all_students()
        modules_df = self.get_all_modules()

        print("\nData Quality Report:")
        print(f"Students table: {len(students_df)} records")

        if not students_df.empty:
            # Check for missing values
            missing_data = students_df.isnull().sum()
            if missing_data.sum() > 0:
                print("Missing data found:")
                for col, count in missing_data.items():
                    if count > 0:
                        print(f"  {col}: {count} missing values")
            else:
                print("No missing data found in students table")

        print(f"Modules table: {len(modules_df)} records")
        print("Data quality check completed")

    def advanced_filtering(self):
        """Advanced filtering options - GUI compatible"""
        print("Advanced filtering options:")
        print("1. Age range filtering")
        print("2. GPA range filtering")
        print("3. Course-specific filtering")
        print("4. Gender-based filtering")
        print("5. Engagement score filtering")
        print("Use the GUI filter dialog for interactive filtering")

    def configuration_settings(self):
        """Configuration settings - GUI compatible"""
        print("Configuration settings available:")
        print("- Plot dimensions and DPI")
        print("- Export formats")
        print("- Email settings")
        print("- Color schemes")
        print("Use the GUI configuration dialog for settings management")

    def generate_complete_report(self):
        """Generate a complete comprehensive report"""
        print("Generating complete analytics report...")

        try:
            # Run all major analyses
            print("Running demographic analysis...")
            self.analyze_student_demographics()

            print("Running grade distribution analysis...")
            self.analyze_grade_distribution()

            print("Running course enrollment analysis...")
            self.analyze_course_enrollments()

            print("Running performance trends analysis...")
            self.analyze_performance_trends()

            print("Running risk assessment...")
            self.analyze_academic_risk()

            print("Running module popularity analysis...")
            self.analyze_module_popularity()

            print("Running engagement analysis...")
            self.analyze_engagement()

            print("Complete report generation finished!")
            print("Check the plots and reports directories for outputs")

        except Exception as e:
            print(f"Error generating complete report: {e}")

    def generate_statistical_summary_report(self, students_df, modules_df, timestamp):
        """Generate statistical summary report"""
        filename = f"{self.reports_dir}/statistical_summary_{timestamp}.txt"

        try:
            with open(filename, 'w') as f:
                f.write("STATISTICAL SUMMARY REPORT\n")
                f.write("="*50 + "\n\n")

                # Students summary
                f.write("STUDENT STATISTICS\n")
                f.write("-"*20 + "\n")
                f.write(f"Total Students: {len(students_df)}\n")

                if 'gpa' in students_df.columns:
                    f.write(f"Average GPA: {students_df['gpa'].mean():.2f}\n")
                    f.write(f"GPA Std Dev: {students_df['gpa'].std():.2f}\n")
                    f.write(f"Min GPA: {students_df['gpa'].min():.2f}\n")
                    f.write(f"Max GPA: {students_df['gpa'].max():.2f}\n")

                if 'age' in students_df.columns:
                    f.write(f"Average Age: {students_df['age'].mean():.1f}\n")
                    f.write(f"Age Range: {students_df['age'].min()}-{students_df['age'].max()}\n")

                if 'engagement_score' in students_df.columns:
                    f.write(f"Average Engagement: {students_df['engagement_score'].mean():.1f}\n")

                # Modules summary
                f.write("\nMODULE STATISTICS\n")
                f.write("-"*20 + "\n")
                f.write(f"Total Modules: {len(modules_df)}\n")

                if 'enrollment_count' in modules_df.columns:
                    f.write(f"Total Enrollments: {modules_df['enrollment_count'].sum()}\n")
                    f.write(f"Avg Enrollment per Module: {modules_df['enrollment_count'].mean():.1f}\n")

            print(f"Statistical summary saved: {filename}")

        except Exception as e:
            print(f"Error generating statistical summary: {e}")
