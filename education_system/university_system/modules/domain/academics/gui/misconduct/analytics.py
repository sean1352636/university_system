"""Analytics and reporting for the Academic Misconduct Panel."""

from ._imports import (
    tk, ttk, messagebox, scrolledtext, _t, datetime,
    sqlite3, DEFAULT_DB_PATH, EMAIL_AVAILABLE, queue_email,
)


class MisconductAnalyticsMixin:
    """Mixin providing analytics view, CSV export, and report generation."""

    def create_analytics_view(self):
        """Create the analytics view."""
        analytics_frame = tk.Frame(self.main_content_frame, bg=self.colors['white'])
        self.views['analytics'] = analytics_frame

        # Create analytics content
        self.create_analytics_tab(analytics_frame)

    def create_analytics_tab(self, parent):
        """Create the analytics dashboard tab."""
        # Content frame with scrolling
        canvas = tk.Canvas(parent, bg=self.colors['white'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self.analytics_content = tk.Frame(canvas, bg=self.colors['white'])

        self.analytics_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.analytics_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create analytics content
        self.refresh_analytics_tab()

    def refresh_analytics_tab(self):
        """Refresh the analytics dashboard."""
        # Clear existing widgets
        for widget in self.analytics_content.winfo_children():
            widget.destroy()

        padding_frame = tk.Frame(self.analytics_content, bg=self.colors['white'])
        padding_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        header = tk.Label(
            padding_frame,
            text=_t("misconduct.sections.analytics_dashboard"),
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['white']
        )
        header.pack(anchor='w', pady=(0, 20))

        # Get analytics data from database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Overall statistics
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases")
            total_cases = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Resolved'")
            resolved_cases = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status != 'Resolved'")
            active_cases = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Pending Hearing'")
            pending_hearings = cursor.fetchone()[0]

            # Top statistics panel
            stats_container = tk.Frame(padding_frame, bg=self.colors['white'])
            stats_container.pack(fill=tk.X, pady=(0, 20))

            overview_stats = [
                ("Total Cases", total_cases, self.colors['info'], "📋"),
                ("Active Cases", active_cases, self.colors['warning'], "⚠"),
                ("Resolved Cases", resolved_cases, self.colors['success'], "✓"),
                ("Pending Hearings", pending_hearings, self.colors['danger'], "⚖")
            ]

            for i, (label, value, color, icon) in enumerate(overview_stats):
                stat_card = tk.Frame(stats_container, bg=color, relief='flat', bd=0)
                stat_card.grid(row=0, column=i, padx=5, sticky='ew')
                stats_container.grid_columnconfigure(i, weight=1)

                tk.Label(
                    stat_card,
                    text=icon,
                    font=('Segoe UI', 20),
                    fg=self.colors['white'],
                    bg=color
                ).pack(pady=(10, 0))

                tk.Label(
                    stat_card,
                    text=str(value),
                    font=('Segoe UI', 24, 'bold'),
                    fg=self.colors['white'],
                    bg=color
                ).pack()

                tk.Label(
                    stat_card,
                    text=label,
                    font=('Segoe UI', 9),
                    fg=self.colors['white'],
                    bg=color
                ).pack(pady=(0, 10))

            # Violation types breakdown
            tk.Label(
                padding_frame,
                text=_t("misconduct.sections.violation_breakdown"),
                font=('Segoe UI', 12, 'bold'),
                fg=self.colors['text_dark'],
                bg=self.colors['white']
            ).pack(anchor='w', pady=(20, 10))

            cursor.execute("""
                SELECT violation_type, COUNT(*) as count
                FROM academic_misconduct_cases
                GROUP BY violation_type
                ORDER BY count DESC
            """)
            violation_types = cursor.fetchall()

            if violation_types:
                violations_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                violations_frame.pack(fill=tk.X, pady=(0, 20))

                for violation, count in violation_types:
                    row = tk.Frame(violations_frame, bg=self.colors['light'])
                    row.pack(fill=tk.X, padx=15, pady=8)

                    tk.Label(
                        row,
                        text=violation,
                        font=('Segoe UI', 10),
                        fg=self.colors['text_dark'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        row,
                        text=f"{count} cases",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['secondary'],
                        bg=self.colors['light']
                    ).pack(side=tk.RIGHT)

            # Severity distribution
            tk.Label(
                padding_frame,
                text=_t("misconduct.sections.severity_distribution"),
                font=('Segoe UI', 12, 'bold'),
                fg=self.colors['text_dark'],
                bg=self.colors['white']
            ).pack(anchor='w', pady=(20, 10))

            cursor.execute("""
                SELECT severity, COUNT(*) as count
                FROM academic_misconduct_cases
                GROUP BY severity
                ORDER BY
                    CASE severity
                        WHEN 'Critical' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 4
                        ELSE 5
                    END
            """)
            severities = cursor.fetchall()

            if severities:
                severity_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                severity_frame.pack(fill=tk.X, pady=(0, 20))

                severity_colors = {
                    'Critical': self.colors['danger'],
                    'High': self.colors['warning'],
                    'Medium': self.colors['info'],
                    'Low': self.colors['success']
                }

                for severity, count in severities:
                    row = tk.Frame(severity_frame, bg=self.colors['light'])
                    row.pack(fill=tk.X, padx=15, pady=8)

                    indicator = tk.Label(
                        row,
                        text="●",
                        font=('Segoe UI', 14),
                        fg=severity_colors.get(severity, self.colors['text_muted']),
                        bg=self.colors['light']
                    )
                    indicator.pack(side=tk.LEFT, padx=(0, 10))

                    tk.Label(
                        row,
                        text=f"{severity} Severity",
                        font=('Segoe UI', 10),
                        fg=self.colors['text_dark'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        row,
                        text=f"{count} cases",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['secondary'],
                        bg=self.colors['light']
                    ).pack(side=tk.RIGHT)

            # Recent trends
            tk.Label(
                padding_frame,
                text=_t("misconduct.sections.recent_trends"),
                font=('Segoe UI', 12, 'bold'),
                fg=self.colors['text_dark'],
                bg=self.colors['white']
            ).pack(anchor='w', pady=(20, 10))

            cursor.execute("""
                SELECT strftime('%Y-%m', date_filed) as month, COUNT(*) as count
                FROM academic_misconduct_cases
                WHERE date_filed >= date('now', '-6 months')
                GROUP BY month
                ORDER BY month DESC
            """)
            monthly_trends = cursor.fetchall()

            if monthly_trends:
                trends_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                trends_frame.pack(fill=tk.X, pady=(0, 20))

                for month, count in monthly_trends:
                    row = tk.Frame(trends_frame, bg=self.colors['light'])
                    row.pack(fill=tk.X, padx=15, pady=8)

                    tk.Label(
                        row,
                        text=month,
                        font=('Segoe UI', 10),
                        fg=self.colors['text_dark'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

                    # Simple bar representation
                    bar_frame = tk.Frame(row, bg=self.colors['secondary'], height=20, width=count*20)
                    bar_frame.pack(side=tk.LEFT, padx=10)

                    tk.Label(
                        row,
                        text=f"{count} cases",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['secondary'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

            # Export buttons
            export_frame = tk.Frame(padding_frame, bg=self.colors['white'])
            export_frame.pack(fill=tk.X, pady=(20, 0))

            tk.Label(
                export_frame,
                text=_t("misconduct.labels.export_options"),
                font=('Segoe UI', 11, 'bold'),
                fg=self.colors['text_dark'],
                bg=self.colors['white']
            ).pack(side=tk.LEFT, padx=(0, 15))

            self.create_button(export_frame, "📄 Export to CSV", self.export_analytics_csv, 'success').pack(side=tk.LEFT, padx=5)
            self.create_button(export_frame, "📊 Generate Report", self.generate_analytics_report, 'primary').pack(side=tk.LEFT, padx=5)

            conn.close()

        except Exception as e:
            error_label = tk.Label(
                padding_frame,
                text=f"Error loading analytics: {str(e)}",
                font=('Segoe UI', 10),
                fg=self.colors['danger'],
                bg=self.colors['white']
            )
            error_label.pack(anchor='w', pady=10)

    def export_analytics_csv(self):
        """Export analytics data to CSV."""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"misconduct_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT case_id, student_name, student_id, course, violation_type,
                       severity, status, date_filed, ruling
                FROM academic_misconduct_cases
                ORDER BY date_filed DESC
            """)

            cases = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Case ID', 'Student Name', 'Student ID', 'Course', 'Violation Type',
                               'Severity', 'Status', 'Date Filed', 'Ruling'])
                writer.writerows(cases)

            messagebox.showinfo(_t("misconduct.msg_titles.export_successful"), f"Analytics data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t("misconduct.msg_titles.export_error"), f"Failed to export data: {str(e)}")

    def generate_analytics_report(self):
        """Generate a comprehensive analytics report."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("ACADEMIC MISCONDUCT ANALYTICS REPORT")
            report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("=" * 80)
            report_lines.append("")

            # Overall statistics
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases")
            total = cursor.fetchone()[0]
            report_lines.append(f"Total Cases: {total}")

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Resolved'")
            resolved = cursor.fetchone()[0]
            report_lines.append(f"Resolved Cases: {resolved}")

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status != 'Resolved'")
            active = cursor.fetchone()[0]
            report_lines.append(f"Active Cases: {active}")
            report_lines.append("")

            # Violation types
            report_lines.append("VIOLATION TYPES:")
            report_lines.append("-" * 40)
            cursor.execute("""
                SELECT violation_type, COUNT(*) FROM academic_misconduct_cases
                GROUP BY violation_type ORDER BY COUNT(*) DESC
            """)
            for violation, count in cursor.fetchall():
                report_lines.append(f"  {violation}: {count}")
            report_lines.append("")

            # Severity distribution
            report_lines.append("SEVERITY DISTRIBUTION:")
            report_lines.append("-" * 40)
            cursor.execute("""
                SELECT severity, COUNT(*) FROM academic_misconduct_cases
                GROUP BY severity
            """)
            for severity, count in cursor.fetchall():
                report_lines.append(f"  {severity}: {count}")

            conn.close()

            # Display report
            report_window = tk.Toplevel(self.root)
            report_window.title("Analytics Report")
            report_window.geometry("800x650")
            report_window.configure(bg=self.colors['light'])

            # Main container
            main_frame = tk.Frame(report_window, bg=self.colors['light'])
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            text_widget = scrolledtext.ScrolledText(
                main_frame,
                font=('Courier New', 10),
                bg=self.colors['white'],
                fg=self.colors['text_dark']
            )
            text_widget.pack(fill=tk.BOTH, expand=True)
            report_content = '\n'.join(report_lines)
            text_widget.insert('1.0', report_content)
            text_widget.configure(state='disabled')

            # Button frame
            btn_frame = tk.Frame(main_frame, bg=self.colors['light'])
            btn_frame.pack(fill=tk.X, pady=(10, 0))

            def save_report_as_txt():
                """Save the report to a text file."""
                try:
                    from tkinter import filedialog
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".txt",
                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                        initialfile=f"misconduct_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    )
                    if filename:
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(report_content)
                        messagebox.showinfo(_t("misconduct.msg_titles.success"), f"Report saved to:\n{filename}")
                except Exception as e:
                    messagebox.showerror(_t("misconduct.msg_titles.save_error"), f"Failed to save report: {str(e)}")

            def send_report_to_admin():
                """Send the report to admin users via email."""
                try:
                    if not EMAIL_AVAILABLE or queue_email is None:
                        messagebox.showerror(_t("misconduct.msg_titles.email_unavailable"), "Email system is not available.")
                        return

                    # Get admin users from database
                    admin_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    admin_cursor = admin_conn.cursor()
                    admin_cursor.execute("SELECT username, email FROM users WHERE LOWER(role) = 'admin' AND email IS NOT NULL AND email != ''")
                    admins = admin_cursor.fetchall()
                    admin_conn.close()

                    if not admins:
                        messagebox.showwarning(_t("misconduct.msg_titles.no_admins"), "No admin users with email addresses found in the system.")
                        return

                    # Send to each admin
                    subject = f"Academic Misconduct Analytics Report - {datetime.now().strftime('%Y-%m-%d')}"
                    message = f"""Academic Misconduct Analytics Report

This is an automated report from the Academic Misconduct Panel.

{report_content}

---
This report was generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}
"""

                    sent_count = 0
                    failed_admins = []

                    for admin_username, admin_email in admins:
                        try:
                            success = queue_email(admin_email, subject, message)
                            if success:
                                sent_count += 1
                            else:
                                failed_admins.append(admin_username)
                        except Exception as e:
                            failed_admins.append(f"{admin_username} ({str(e)})")

                    # Show results
                    if sent_count > 0:
                        result_msg = f"Report sent to {sent_count} admin user(s)."
                        if failed_admins:
                            result_msg += f"\n\nFailed to send to: {', '.join(failed_admins)}"
                        messagebox.showinfo(_t("misconduct.msg_titles.email_sent"), result_msg)
                    else:
                        messagebox.showerror(_t("misconduct.msg_titles.send_failed"), f"Failed to send to all admins.\n{', '.join(failed_admins)}")

                except Exception as e:
                    messagebox.showerror(_t("misconduct.msg_titles.send_error"), f"Failed to send report: {str(e)}")

            # Add buttons
            self.create_button(btn_frame, "💾 Save as TXT", save_report_as_txt, 'success').pack(side=tk.LEFT, padx=5)
            self.create_button(btn_frame, "📧 Send to Admin", send_report_to_admin, 'primary').pack(side=tk.LEFT, padx=5)
            self.create_button(btn_frame, "Close", report_window.destroy, 'secondary').pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror(_t("misconduct.msg_titles.report_error"), f"Failed to generate report: {str(e)}")
