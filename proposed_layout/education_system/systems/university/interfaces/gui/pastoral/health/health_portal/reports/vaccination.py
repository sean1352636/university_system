import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta


class VaccinationReportsMixin:
    """Mixin for vaccination coverage reports."""

    def create_vaccination_coverage_report(self, parent):
        """Create vaccination coverage report"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.vaccination_report_text = scrolledtext.ScrolledText(main_frame, width=80, height=25, font=('Consolas', 10))
        self.vaccination_report_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Button(main_frame, text="Generate Vaccination Coverage Report",
                  command=self.generate_vaccination_report).grid(row=1, column=0, pady=10)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self.generate_vaccination_report()

    def generate_vaccination_report(self):
        """Generate vaccination coverage report"""
        try:
            self.vaccination_report_text.delete(1.0, tk.END)

            conn = self.get_connection()
            cursor = conn.cursor()

            report = []
            report.append("VACCINATION COVERAGE REPORT")
            report.append("=" * 50)
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")

            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]

            cursor.execute("""
                SELECT vaccine_name,
                       COUNT(DISTINCT student_id) as vaccinated_students,
                       COUNT(*) as total_doses
                FROM vaccination_records
                GROUP BY vaccine_name
                ORDER BY vaccinated_students DESC
            """)
            vaccine_coverage = cursor.fetchall()

            report.append("VACCINATION COVERAGE BY VACCINE TYPE")
            report.append("-" * 50)
            report.append(f"Total Students: {total_students}")
            report.append("")

            for vaccine, vaccinated, doses in vaccine_coverage:
                coverage_percentage = (vaccinated / total_students * 100) if total_students > 0 else 0
                avg_doses = doses / vaccinated if vaccinated > 0 else 0
                report.append(f"{vaccine}:")
                report.append(f"  Students Vaccinated: {vaccinated}/{total_students} ({coverage_percentage:.1f}%)")
                report.append(f"  Total Doses: {doses}")
                report.append(f"  Average Doses per Student: {avg_doses:.1f}")
                report.append("")

            cursor.execute("""
                SELECT COUNT(*) FROM students
                WHERE student_id NOT IN (SELECT DISTINCT student_id FROM vaccination_records)
            """)
            unvaccinated_count = cursor.fetchone()[0]

            report.append("VACCINATION STATUS SUMMARY")
            report.append("-" * 30)
            report.append(f"Students with Vaccination Records: {total_students - unvaccinated_count}")
            report.append(f"Students with No Vaccination Records: {unvaccinated_count}")
            if total_students > 0:
                vaccinated_percentage = ((total_students - unvaccinated_count) / total_students * 100)
                report.append(f"Overall Vaccination Coverage: {vaccinated_percentage:.1f}%")
            report.append("")

            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT vaccine_name, COUNT(*)
                FROM vaccination_records
                WHERE administered_date >= ?
                GROUP BY vaccine_name
                ORDER BY COUNT(*) DESC
            """, (thirty_days_ago,))
            recent_vaccinations = cursor.fetchall()

            if recent_vaccinations:
                report.append("RECENT VACCINATIONS (Last 30 Days)")
                report.append("-" * 40)
                for vaccine, count in recent_vaccinations:
                    report.append(f"  {vaccine}: {count} doses")
                report.append("")

            cursor.execute("""
                SELECT vaccine_name, COUNT(*) as adverse_count,
                       (SELECT COUNT(*) FROM vaccination_records vr2
                        WHERE vr2.vaccine_name = vr1.vaccine_name) as total_doses
                FROM vaccination_records vr1
                WHERE adverse_reaction = 1
                GROUP BY vaccine_name
                ORDER BY adverse_count DESC
            """)
            adverse_reactions = cursor.fetchall()

            if adverse_reactions:
                report.append("ADVERSE REACTIONS")
                report.append("-" * 20)
                for vaccine, adverse_count, total_doses in adverse_reactions:
                    adverse_rate = (adverse_count / total_doses * 100) if total_doses > 0 else 0
                    report.append(f"{vaccine}: {adverse_count}/{total_doses} ({adverse_rate:.2f}%)")
                report.append("")

            conn.close()

            self.vaccination_report_text.insert(tk.END, "\n".join(report))

            self.log_audit_event('generate_vaccination_report', 'report', 'vaccination_coverage')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate vaccination report: {str(e)}")
