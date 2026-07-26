import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime


class AppointmentReportsMixin:
    """Mixin for appointment statistics reports."""

    def create_appointment_statistics_report(self, parent):
        """Create appointment statistics report"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.appointment_report_text = scrolledtext.ScrolledText(main_frame, width=80, height=25, font=('Consolas', 10))
        self.appointment_report_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Button(main_frame, text="Generate Appointment Statistics Report",
                  command=self.generate_appointment_report).grid(row=1, column=0, pady=10)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self.generate_appointment_report()

    def generate_appointment_report(self):
        """Generate appointment statistics report"""
        try:
            self.appointment_report_text.delete(1.0, tk.END)

            conn = self.get_connection()
            cursor = conn.cursor()

            report = []
            report.append("APPOINTMENT STATISTICS REPORT")
            report.append("=" * 50)
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")

            cursor.execute("SELECT COUNT(*) FROM health_appointments")
            total_appointments = cursor.fetchone()[0]

            cursor.execute("""
                SELECT status, COUNT(*)
                FROM health_appointments
                GROUP BY status
                ORDER BY COUNT(*) DESC
            """)
            status_breakdown = cursor.fetchall()

            report.append("APPOINTMENT STATUS BREAKDOWN")
            report.append("-" * 35)
            report.append(f"Total Appointments: {total_appointments}")
            report.append("")

            for status, count in status_breakdown:
                percentage = (count / total_appointments * 100) if total_appointments > 0 else 0
                report.append(f"{status.title()}: {count} ({percentage:.1f}%)")
            report.append("")

            cursor.execute("""
                SELECT appointment_type, COUNT(*)
                FROM health_appointments
                GROUP BY appointment_type
                ORDER BY COUNT(*) DESC
            """)
            type_breakdown = cursor.fetchall()

            report.append("APPOINTMENT TYPE BREAKDOWN")
            report.append("-" * 30)
            for apt_type, count in type_breakdown:
                percentage = (count / total_appointments * 100) if total_appointments > 0 else 0
                report.append(f"{apt_type}: {count} ({percentage:.1f}%)")
            report.append("")

            cursor.execute("""
                SELECT provider, COUNT(*)
                FROM health_appointments
                GROUP BY provider
                ORDER BY COUNT(*) DESC
            """)
            provider_workload = cursor.fetchall()

            report.append("PROVIDER WORKLOAD")
            report.append("-" * 20)
            for provider, count in provider_workload:
                percentage = (count / total_appointments * 100) if total_appointments > 0 else 0
                report.append(f"{provider}: {count} appointments ({percentage:.1f}%)")
            report.append("")

            cursor.execute("""
                SELECT strftime('%Y-%m', appointment_date) as month, COUNT(*)
                FROM health_appointments
                WHERE appointment_date >= date('now', '-12 months')
                GROUP BY strftime('%Y-%m', appointment_date)
                ORDER BY month
            """)
            monthly_trends = cursor.fetchall()

            if monthly_trends:
                report.append("MONTHLY APPOINTMENT TRENDS (Last 12 Months)")
                report.append("-" * 45)
                for month, count in monthly_trends:
                    report.append(f"{month}: {count} appointments")
                report.append("")

            cursor.execute("SELECT COUNT(*) FROM health_appointments WHERE status = 'no-show'")
            no_shows = cursor.fetchone()[0]
            no_show_rate = (no_shows / total_appointments * 100) if total_appointments > 0 else 0

            cursor.execute("SELECT COUNT(*) FROM health_appointments WHERE status = 'cancelled'")
            cancellations = cursor.fetchone()[0]
            cancellation_rate = (cancellations / total_appointments * 100) if total_appointments > 0 else 0

            report.append("APPOINTMENT RELIABILITY METRICS")
            report.append("-" * 35)
            report.append(f"No-Show Rate: {no_show_rate:.1f}% ({no_shows} appointments)")
            report.append(f"Cancellation Rate: {cancellation_rate:.1f}% ({cancellations} appointments)")

            conn.close()

            self.appointment_report_text.insert(tk.END, "\n".join(report))

            self.log_audit_event('generate_appointment_report', 'report', 'appointment_statistics')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate appointment report: {str(e)}")
