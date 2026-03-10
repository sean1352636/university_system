"""Barber Shop GUI - Analytics & reporting feature methods."""

from education_system.university_system.modules.domain.barber.gui.common import (
    tk, ttk, messagebox, filedialog, logging, json,
    datetime, timedelta,
    _t, log_activity,
)

logger = logging.getLogger(__name__)


class AnalyticsMixin:
    """Mixin providing analytics & reporting methods for BarberGUI."""

    def show_dashboard(self):
        """Show analytics dashboard."""
        dash_window = tk.Toplevel(self.parent)
        dash_window.title("Analytics Dashboard")
        dash_window.geometry("900x600")
        dash_window.transient(self.parent)

        # Summary cards
        cards_frame = ttk.Frame(dash_window, padding="10")
        cards_frame.pack(fill=tk.X)

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AnalyticsManager
            stats = AnalyticsManager.get_dashboard_stats()

            metrics = [
                ("Today's Appointments", stats.get('today_appointments', 0)),
                ("This Week's Revenue", f"£{(stats.get('week_revenue') or 0):.2f}"),
                ("New Customers", stats.get('new_customers', 0)),
                ("Average Rating", f"{stats.get('avg_rating', 0):.1f}/5"),
                ("Completion Rate", f"{stats.get('completion_rate', 0):.0f}%"),
                ("No-Show Rate", f"{stats.get('no_show_rate', 0):.0f}%")
            ]

            for i, (label, value) in enumerate(metrics):
                card = ttk.LabelFrame(cards_frame, text=label, padding="10")
                card.grid(row=0, column=i, padx=5, pady=5)
                ttk.Label(card, text=str(value), font=('Helvetica', 16, 'bold')).pack()

        except Exception as e:
            logger.error(f"Error loading dashboard: {e}")

        # Charts section (text-based)
        charts_frame = ttk.LabelFrame(dash_window, text="Recent Trends", padding="10")
        charts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.dashboard_text = tk.Text(charts_frame, wrap=tk.WORD, height=20)
        scrollbar = ttk.Scrollbar(charts_frame, orient=tk.VERTICAL, command=self.dashboard_text.yview)
        self.dashboard_text.configure(yscrollcommand=scrollbar.set)

        self.dashboard_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AnalyticsManager
            stats = AnalyticsManager.get_dashboard_stats()

            report = "=== Barber Shop Dashboard ===\n\n"
            report += "TODAY'S SUMMARY:\n"
            report += f"  Total Appointments: {stats['today']['total_appointments'] or 0}\n"
            report += f"  Completed: {stats['today']['completed'] or 0}\n"
            report += f"  Scheduled: {stats['today']['scheduled'] or 0}\n"
            report += f"  No-Shows: {stats['today']['no_shows'] or 0}\n"
            report += f"  Revenue: ${(stats['today']['revenue'] or 0):.2f}\n"
            report += f"  Tips: ${(stats['today']['tips'] or 0):.2f}\n\n"
            report += f"ACTIVE STAFF: {stats['active_staff'] or 0}\n\n"
            report += "THIS MONTH:\n"
            report += f"  Appointments: {stats['monthly']['appointments'] or 0}\n"
            report += f"  Revenue: ${(stats['monthly']['revenue'] or 0):.2f}\n"

            self.dashboard_text.insert('1.0', report)
        except Exception as e:
            self.dashboard_text.insert('1.0', f"Error loading trends: {e}")

    def generate_peak_hours_report(self):
        """Generate peak hours report."""
        self.analytics_text.delete('1.0', tk.END)
        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AnalyticsManager

            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            peak_hours = AnalyticsManager.get_peak_hours(start_date, end_date)

            report = f"=== Peak Hours Report ===\n"
            report += f"Period: {start_date} to {end_date}\n\n"

            if peak_hours:
                report += "Time         | Appointments\n"
                report += "-" * 30 + "\n"
                for hour in peak_hours:
                    time_str = hour['appointment_time'] if hour['appointment_time'] else 'N/A'
                    count = hour['count'] if hour['count'] else 0
                    report += f"{time_str:12} | {count}\n"
            else:
                report += "No appointment data available for this period.\n"

            self.analytics_text.insert('1.0', report)
        except Exception as e:
            self.analytics_text.insert('1.0', f"Error: {e}")

    def customer_retention_report(self):
        """Generate customer retention report."""
        self.analytics_text.delete('1.0', tk.END)
        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AnalyticsManager

            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

            retention = AnalyticsManager.get_customer_retention(start_date, end_date)

            report = f"=== Customer Retention Report ===\n"
            report += f"Period: {start_date} to {end_date}\n\n"
            report += f"Total Unique Customers: {retention.get('total_customers') or 0}\n"
            report += f"New Customers: {retention.get('new_customers') or 0}\n"
            report += f"Returning Customers: {retention.get('returning_customers') or 0}\n"
            report += f"Retention Rate: {(retention.get('retention_rate') or 0):.1f}%\n"

            self.analytics_text.insert('1.0', report)
        except Exception as e:
            self.analytics_text.insert('1.0', f"Error: {e}")

    def export_report_pdf(self):
        """Export report to PDF (currently exports as text file)."""
        report_content = self.analytics_text.get('1.0', tk.END).strip()
        if not report_content:
            messagebox.showwarning("Warning", "No report to export. Generate a report first.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Report"
        )
        if not file_path:
            return

        try:
            # Try to use reportlab for PDF export
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.units import inch

                doc = SimpleDocTemplate(file_path, pagesize=letter)
                story = []
                styles = getSampleStyleSheet()

                title = Paragraph("Barber Shop Report", styles['Title'])
                story.append(title)
                story.append(Spacer(1, 0.2*inch))

                timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal'])
                story.append(timestamp)
                story.append(Spacer(1, 0.3*inch))

                for line in report_content.split('\n'):
                    if line.strip():
                        p = Paragraph(line.replace('<', '&lt;').replace('>', '&gt;'), styles['Normal'])
                        story.append(p)
                    else:
                        story.append(Spacer(1, 0.1*inch))

                doc.build(story)
                messagebox.showinfo("Success", f"Report exported to:\n{file_path}")

            except ImportError:
                # Fallback to text export if reportlab not available
                if not file_path.endswith('.txt'):
                    file_path = file_path.rsplit('.', 1)[0] + '.txt'

                with open(file_path, 'w') as f:
                    f.write(f"Barber Shop Report\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(report_content)

            messagebox.showinfo("Success", f"Report exported to {file_path}")
            log_activity('export', 'barber_report', details={'file': file_path})
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def schedule_automated_reports(self):
        """Schedule automated reports."""
        sched_window = tk.Toplevel(self.parent)
        sched_window.title("Schedule Reports")
        sched_window.geometry("450x400")
        sched_window.transient(self.parent)
        sched_window.grab_set()

        ttk.Label(sched_window, text="Schedule Automated Reports",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(sched_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Report Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(frame, values=['daily_sales', 'weekly_summary', 'monthly_performance', 'customer_retention'], width=20)
        type_combo.set('daily_sales')
        type_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Frequency:").grid(row=1, column=0, sticky=tk.W, pady=5)
        freq_combo = ttk.Combobox(frame, values=['daily', 'weekly', 'monthly'], width=15)
        freq_combo.set('daily')
        freq_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        time_combo = ttk.Combobox(frame, values=['06:00', '08:00', '10:00', '12:00', '18:00', '20:00'], width=10)
        time_combo.set('08:00')
        time_combo.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Send to Email:").grid(row=3, column=0, sticky=tk.W, pady=5)
        email_var = tk.StringVar(value=self.current_user.get('email', ''))
        ttk.Entry(frame, textvariable=email_var, width=30).grid(row=3, column=1, pady=5)

        # Existing schedules
        ttk.Label(frame, text="Existing Schedules:").grid(row=4, column=0, sticky=tk.W, pady=(20, 5))

        listbox = tk.Listbox(frame, height=6, width=40)
        listbox.grid(row=5, column=0, columnspan=2, pady=5)

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import ScheduledReportManager
            schedules = ScheduledReportManager.get_scheduled_reports()
            for sched in schedules:
                freq_text = sched.get('frequency', 'N/A')
                report_type = sched.get('report_type', 'Unknown')
                listbox.insert(tk.END, f"{report_type} - {freq_text}")
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")

        def save_schedule():
            try:
                from education_system.university_system.modules.domain.barber.services.barber_core import ScheduledReportManager

                params_dict = {
                    'time': time_combo.get()
                }
                params_str = json.dumps(params_dict)

                ScheduledReportManager.schedule_report(
                    report_type=type_combo.get(),
                    frequency=freq_combo.get(),
                    recipients=email_var.get().strip(),
                    created_by=self.current_user.get('username', 'System'),
                    params=params_str
                )
                messagebox.showinfo("Success", "Report schedule created!")
                sched_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                logger.error(f"Error creating schedule: {e}")

        ttk.Button(sched_window, text="Save Schedule", command=save_schedule).pack(pady=10)

    def view_audit_log(self):
        """View audit log."""
        audit_window = tk.Toplevel(self.parent)
        audit_window.title("Audit Log")
        audit_window.geometry("900x500")
        audit_window.transient(self.parent)

        # Filter
        filter_frame = ttk.Frame(audit_window, padding="10")
        filter_frame.pack(fill=tk.X)

        ttk.Label(filter_frame, text="From:").pack(side=tk.LEFT)
        from_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="To:").pack(side=tk.LEFT, padx=(10, 0))
        to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=to_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="Action:").pack(side=tk.LEFT, padx=(10, 0))
        action_combo = ttk.Combobox(filter_frame, values=['All', 'create', 'update', 'delete', 'payment', 'refund'], width=12)
        action_combo.set('All')
        action_combo.pack(side=tk.LEFT, padx=5)

        columns = ('timestamp', 'user', 'action', 'entity', 'entity_id', 'details')
        tree = ttk.Treeview(audit_window, columns=columns, show='headings', height=18)

        tree.heading('timestamp', text='Timestamp')
        tree.heading('user', text='User')
        tree.heading('action', text='Action')
        tree.heading('entity', text='Entity')
        tree.heading('entity_id', text='Entity ID')
        tree.heading('details', text='Details')

        tree.column('timestamp', width=150)
        tree.column('user', width=100)
        tree.column('action', width=80)
        tree.column('entity', width=100)
        tree.column('entity_id', width=100)
        tree.column('details', width=300)

        scrollbar = ttk.Scrollbar(audit_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_log():
            for item in tree.get_children():
                tree.delete(item)
            try:
                from education_system.university_system.modules.domain.barber.services.barber_core import AuditLogManager
                action_filter = None if action_combo.get() == 'All' else action_combo.get()

                logs = AuditLogManager.get_audit_log(
                    start_date=from_var.get(),
                    end_date=to_var.get(),
                    action_type=action_filter,
                    limit=500
                )

                for log in logs:
                    tree.insert('', tk.END, values=(
                        log.get('created_at', ''),
                        log.get('user_id', ''),
                        log.get('action_type', ''),
                        log.get('entity_type', ''),
                        log.get('entity_id', ''),
                        log.get('details', '')[:50]
                    ))
            except Exception as e:
                logger.error(f"Error loading audit log: {e}")
                messagebox.showerror("Error", f"Failed to load audit log: {e}")

        ttk.Button(filter_frame, text="Search", command=load_log).pack(side=tk.LEFT, padx=20)
        load_log()
