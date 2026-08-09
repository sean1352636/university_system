"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_weekly_trends(self):
    """Weekly trend analysis with anomaly highlighting"""
    try:
        self.update_status("Analyzing trends...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT strftime('%Y-W%W', analysis_date) as week,
                       COUNT(*) as submissions,
                       AVG(ai_probability) as avg_score,
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
                FROM ai_analysis_history
                WHERE analysis_date IS NOT NULL
                GROUP BY week
                ORDER BY week DESC
                LIMIT 12
            ''')
            weeks = cursor.fetchall()
        finally:
            conn.close()

        result = "Weekly Trend Analysis\n"
        result += "=" * 50 + "\n\n"

        if not weeks:
            result += "No weekly data available.\n"
            self.analytics_results_text.insert('1.0', result)
            return

        result += f"{'Week':<12} {'Subs':<8} {'Avg Score':<12} {'High Risk':<10}\n"
        result += "-" * 50 + "\n"

        # Calculate averages for anomaly detection
        avg_subs = sum(w[1] for w in weeks) / len(weeks)
        avg_score = sum(w[2] for w in weeks) / len(weeks)

        anomalies = []
        for week, subs, score, high_risk in reversed(weeks):
            flags = []
            if subs > avg_subs * 1.5:
                flags.append("high volume")
            if score > avg_score + 10:
                flags.append("high AI score")
            if high_risk / max(subs, 1) > 0.3:
                flags.append("many flagged")

            flag_str = " [" + ", ".join(flags) + "]" if flags else ""
            result += f"{week:<12} {subs:<8} {score:>6.1f}%     {high_risk:<5}{flag_str}\n"

            if flags:
                anomalies.append((week, flags))

        result += "\n" + "-" * 50 + "\n"

        # Trend direction
        if len(weeks) >= 4:
            recent = sum(w[2] for w in weeks[:4]) / 4
            older = sum(w[2] for w in weeks[-4:]) / 4

            result += "\nTrend Analysis:\n"
            if recent > older + 5:
                result += "ALERT: AI detection scores are INCREASING\n"
                result += f"Recent avg: {recent:.1f}% vs Earlier avg: {older:.1f}%\n"
            elif recent < older - 5:
                result += "POSITIVE: AI detection scores are DECREASING\n"
            else:
                result += "Scores are relatively stable\n"

        if anomalies:
            result += f"\nAnomalous Weeks: {len(anomalies)}\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Trend analysis complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.show_weekly_trends.dialogs.error', default="Error"), f"Failed to analyze trends: {str(e)}")
