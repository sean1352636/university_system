"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def generate_department_comparison(self):
    """Compare AI detection rates across departments"""
    try:
        self.update_status("Generating comparison...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT course_name, COUNT(*) as submissions,
                       AVG(ai_probability) as avg_score,
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
                FROM ai_analysis_history
                WHERE course_name IS NOT NULL
                GROUP BY course_name
                ORDER BY avg_score DESC
            ''')
            departments = cursor.fetchall()
        finally:
            conn.close()

        result = "Department/Course Comparison\n"
        result += "=" * 50 + "\n\n"

        if not departments:
            result += "No departmental data available.\n"
            self.analytics_results_text.insert('1.0', result)
            return

        result += f"{'Course/Dept':<25} {'Subs':<8} {'Avg':<8} {'High Risk':<10}\n"
        result += "-" * 55 + "\n"

        total_subs = sum(d[1] for d in departments)
        total_high_risk = sum(d[3] for d in departments)

        for course, subs, avg, high_risk in departments:
            course_short = (course or "Unknown")[:23]
            risk_pct = high_risk / max(subs, 1) * 100
            flag = " !!!" if risk_pct > 20 else ""
            result += f"{course_short:<25} {subs:<8} {avg:>5.1f}%  {high_risk:<5} ({risk_pct:.0f}%){flag}\n"

        result += "\n" + "-" * 55 + "\n"
        result += "\nOverall Statistics:\n"
        result += f"Total Submissions: {total_subs}\n"
        result += f"Total High-Risk: {total_high_risk} ({total_high_risk/max(total_subs,1)*100:.1f}%)\n"

        # Identify outliers
        if departments:
            avg_all = sum(d[2] for d in departments) / len(departments)
            outliers = [d for d in departments if d[2] > avg_all + 15]
            if outliers:
                result += "\nCourses with above-average AI scores:\n"
                for d in outliers:
                    result += f"  - {d[0]}: {d[2]:.1f}%\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Comparison complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.generate_department_comparison.dialogs.error', default="Error"), f"Failed to generate comparison: {str(e)}")
