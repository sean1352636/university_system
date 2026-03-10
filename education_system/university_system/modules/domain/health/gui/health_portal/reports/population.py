import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, timedelta


class PopulationReportsMixin:
    """Mixin for admin-level population health reports and the reports notebook."""

    def create_health_reports(self):
        """Create health reports interface"""
        title = ttk.Label(self.content_frame, text="Health Reports & Analytics", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        population_tab = ttk.Frame(notebook)
        notebook.add(population_tab, text="Population Health")
        self.create_population_health_report(population_tab)

        vaccination_tab = ttk.Frame(notebook)
        notebook.add(vaccination_tab, text="Vaccination Coverage")
        self.create_vaccination_coverage_report(vaccination_tab)

        appointment_tab = ttk.Frame(notebook)
        notebook.add(appointment_tab, text="Appointment Statistics")
        self.create_appointment_statistics_report(appointment_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_population_health_report(self, parent):
        """Create population health metrics report"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        controls_frame = ttk.LabelFrame(main_frame, text="Report Parameters", padding="5")
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(controls_frame, text="Date From:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.report_date_from = tk.StringVar(value=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
        ttk.Entry(controls_frame, textvariable=self.report_date_from, width=15).grid(row=0, column=1, pady=2, padx=(5, 10))

        ttk.Label(controls_frame, text="Date To:").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.report_date_to = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(controls_frame, textvariable=self.report_date_to, width=15).grid(row=0, column=3, pady=2, padx=(5, 10))

        ttk.Button(controls_frame, text="Generate Report", command=self.generate_population_report).grid(row=0, column=4, padx=10)

        report_frame = ttk.Frame(main_frame)
        report_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.population_report_text = scrolledtext.ScrolledText(report_frame, width=80, height=25, font=('Consolas', 10))
        self.population_report_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(main_frame, text="Export Report", command=self.export_population_report).grid(row=2, column=0, pady=10)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        self.generate_population_report()

    def generate_population_report(self):
        """Generate population health report"""
        try:
            self.population_report_text.delete(1.0, tk.END)

            conn = self.get_connection()
            cursor = conn.cursor()

            date_from = self.report_date_from.get()
            date_to = self.report_date_to.get()

            report = []
            report.append("POPULATION HEALTH REPORT")
            report.append("=" * 50)
            report.append(f"Report Period: {date_from} to {date_to}")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")

            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]
            report.append(f"Total Registered Students: {total_students}")
            report.append("")

            cursor.execute("""
                SELECT COUNT(*) FROM health_records
                WHERE record_date BETWEEN ? AND ?
            """, (date_from, date_to))
            health_records_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT record_type, COUNT(*)
                FROM health_records
                WHERE record_date BETWEEN ? AND ?
                GROUP BY record_type
                ORDER BY COUNT(*) DESC
            """, (date_from, date_to))
            record_types = cursor.fetchall()

            report.append("HEALTH RECORDS ANALYSIS")
            report.append("-" * 30)
            report.append(f"Total Health Records: {health_records_count}")
            report.append("")
            report.append("Records by Type:")
            for record_type, count in record_types:
                percentage = (count / health_records_count * 100) if health_records_count > 0 else 0
                report.append(f"  {record_type}: {count} ({percentage:.1f}%)")
            report.append("")

            cursor.execute("""
                SELECT COUNT(*) FROM vaccination_records
                WHERE administered_date BETWEEN ? AND ?
            """, (date_from, date_to))
            vaccination_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT vaccine_name, COUNT(*)
                FROM vaccination_records
                WHERE administered_date BETWEEN ? AND ?
                GROUP BY vaccine_name
                ORDER BY COUNT(*) DESC
            """, (date_from, date_to))
            vaccine_types = cursor.fetchall()

            report.append("VACCINATION ANALYSIS")
            report.append("-" * 30)
            report.append(f"Total Vaccinations Administered: {vaccination_count}")
            report.append("")
            if vaccine_types:
                report.append("Vaccinations by Type:")
                for vaccine, count in vaccine_types:
                    percentage = (count / vaccination_count * 100) if vaccination_count > 0 else 0
                    report.append(f"  {vaccine}: {count} ({percentage:.1f}%)")
            report.append("")

            cursor.execute("""
                SELECT COUNT(*) FROM health_appointments
                WHERE appointment_date BETWEEN ? AND ?
            """, (date_from, date_to))
            appointment_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT status, COUNT(*)
                FROM health_appointments
                WHERE appointment_date BETWEEN ? AND ?
                GROUP BY status
                ORDER BY COUNT(*) DESC
            """, (date_from, date_to))
            appointment_statuses = cursor.fetchall()

            report.append("APPOINTMENT ANALYSIS")
            report.append("-" * 30)
            report.append(f"Total Appointments: {appointment_count}")
            report.append("")
            if appointment_statuses:
                report.append("Appointments by Status:")
                for status, count in appointment_statuses:
                    percentage = (count / appointment_count * 100) if appointment_count > 0 else 0
                    report.append(f"  {status.title()}: {count} ({percentage:.1f}%)")
            report.append("")

            cursor.execute("""
                SELECT record_type, COUNT(*) as frequency
                FROM health_records
                WHERE record_date BETWEEN ? AND ?
                  AND record_type NOT IN ('General Medical', 'Annual Physical')
                GROUP BY record_type
                ORDER BY COUNT(*) DESC
                LIMIT 5
            """, (date_from, date_to))
            top_concerns = cursor.fetchall()

            if top_concerns:
                report.append("TOP HEALTH CONCERNS")
                report.append("-" * 30)
                for i, (concern, count) in enumerate(top_concerns, 1):
                    report.append(f"{i}. {concern}: {count} cases")
                report.append("")

            date_diff = (datetime.strptime(date_to, '%Y-%m-%d') - datetime.strptime(date_from, '%Y-%m-%d')).days
            if date_diff > 30:
                cursor.execute("""
                    SELECT strftime('%Y-%m', record_date) as month, COUNT(*)
                    FROM health_records
                    WHERE record_date BETWEEN ? AND ?
                    GROUP BY strftime('%Y-%m', record_date)
                    ORDER BY month
                """, (date_from, date_to))
                monthly_trends = cursor.fetchall()

                if monthly_trends:
                    report.append("MONTHLY HEALTH RECORD TRENDS")
                    report.append("-" * 30)
                    for month, count in monthly_trends:
                        report.append(f"{month}: {count} records")
                    report.append("")

            conn.close()

            self.population_report_text.insert(tk.END, "\n".join(report))

            self.log_audit_event('generate_population_report', 'report', 'population_health')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def export_population_report(self):
        """Export population health report to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Population Health Report"
            )

            if filename:
                report_content = self.population_report_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(report_content)

                self.log_audit_event('export_population_report', 'report_export', filename)
                messagebox.showinfo("Success", f"Report exported to: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {str(e)}")
