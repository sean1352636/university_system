"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def plot_submission_timeline(self):
    """Interactive timeline of submissions with risk indicators"""
    try:
        self.update_status("Generating timeline...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT date(analysis_date) as date, COUNT(*) as count,
                       AVG(ai_probability) as avg_score,
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
                FROM ai_analysis_history
                WHERE analysis_date IS NOT NULL
                GROUP BY date(analysis_date)
                ORDER BY date DESC
                LIMIT 30
            ''')
            data = cursor.fetchall()
        finally:
            conn.close()

        result = "Submission Timeline (Last 30 Days)\n"
        result += "=" * 50 + "\n\n"

        if not data:
            result += "No timeline data available.\n"
            self.analytics_results_text.insert('1.0', result)
            return

        result += f"{'Date':<12} {'Count':<8} {'Avg Score':<12} {'High Risk':<10}\n"
        result += "-" * 50 + "\n"

        for date, count, avg_score, high_risk in reversed(data):
            risk_indicator = "!!!" if high_risk > 0 else ""
            result += f"{date:<12} {count:<8} {avg_score:>6.1f}%     {high_risk:<5} {risk_indicator}\n"

        # Show visual timeline
        result += "\n" + "-" * 50 + "\n"
        result += "Activity Graph:\n\n"

        max_count = max(d[1] for d in data) if data else 1
        for date, count, avg_score, high_risk in reversed(data[-14:]):
            bar_length = int(count / max_count * 20)
            bar = "#" * bar_length
            risk_mark = "[!]" if high_risk > 0 else "   "
            result += f"{date[-5:]}: {bar:<20} {count:>3} {risk_mark}\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Timeline generated")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.plot_submission_timeline.dialogs.error', default="Error"), f"Failed to plot timeline: {str(e)}")
