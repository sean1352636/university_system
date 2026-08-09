"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def generate_student_report_card(self):
    """Generate academic integrity report card for a student"""
    student_id = self.mgmt_student_var.get().strip()
    if not student_id:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.generate_student_report_card.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.generate_student_report_card.dialogs.please_enter_a_student_id', default="Please enter a student ID"))
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Get comprehensive student data
        cursor.execute('''
            SELECT u.first_name, u.last_name, u.email
            FROM users u WHERE u.username = ? OR u.id = ?
        ''', (student_id, student_id))
        student = cursor.fetchone()

        cursor.execute('''
            SELECT COUNT(*), AVG(ai_probability),
                   SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN ai_probability > 50 THEN 1 ELSE 0 END)
            FROM ai_analysis_history WHERE student_id = ?
        ''', (student_id,))
        stats = cursor.fetchone()

        cursor.execute('''
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name='ai_dean_escalations'
        ''')
        if cursor.fetchone()[0]:
            cursor.execute('''
                SELECT COUNT(*) FROM ai_dean_escalations
                WHERE student_name LIKE ?
            ''', (f'%{student_id}%',))
            escalations = cursor.fetchone()[0]
        else:
            escalations = 0

        conn.close()

        # Generate report
        report = "=" * 60 + "\n"
        report += "ACADEMIC INTEGRITY REPORT CARD\n"
        report += "=" * 60 + "\n\n"

        report += f"Student ID: {student_id}\n"
        if student:
            report += f"Name: {student[0] or ''} {student[1] or ''}\n"
        report += f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

        report += "-" * 60 + "\n"
        report += "INTEGRITY METRICS\n"
        report += "-" * 60 + "\n\n"

        if stats and stats[0]:
            total, avg_score, high_risk, moderate_risk = stats

            # Calculate integrity grade
            if avg_score < 30 and high_risk == 0:
                grade = "A"
                status = "Excellent Standing"
            elif avg_score < 50 and high_risk / max(total, 1) < 0.1:
                grade = "B"
                status = "Good Standing"
            elif avg_score < 70:
                grade = "C"
                status = "Requires Monitoring"
            else:
                grade = "F"
                status = "High Risk - Action Required"

            report += f"Integrity Grade: {grade}\n"
            report += f"Status: {status}\n\n"
            report += f"Total Submissions Analyzed: {total}\n"
            report += f"Average AI Detection Score: {avg_score:.1f}%\n"
            report += f"High-Risk Submissions (>80%): {high_risk}\n"
            report += f"Moderate-Risk Submissions (>50%): {moderate_risk}\n"
            report += f"Dean Escalations: {escalations}\n"
        else:
            report += "No submission data available.\n"

        report += "\n" + "=" * 60 + "\n"

        # Save report
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf")],
            initialfile=f"integrity_report_{student_id}_{datetime.now().strftime('%Y%m%d')}.txt"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            messagebox.showinfo(_t('gui.academics.ai_detector.student_analytics_view_parts.generate_student_report_card.dialogs.success', default="Success"), f"Report card saved to:\n{file_path}")

        self.student_results_text.delete('1.0', tk.END)
        self.student_results_text.insert('1.0', report)
        self.update_status("Report card generated")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.generate_student_report_card.dialogs.error', default="Error"), f"Failed to generate report: {str(e)}")
