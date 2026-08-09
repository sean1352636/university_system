"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_detection_confidence_distribution(self):
    """Histogram of confidence scores across all submissions"""
    try:
        self.update_status("Generating distribution...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('SELECT ai_probability FROM ai_analysis_history')
            scores = [row[0] for row in cursor.fetchall() if row[0] is not None]
        finally:
            conn.close()

        if not scores:
            self.analytics_results_text.insert('1.0', "No data available for distribution analysis.")
            return

        # Create distribution buckets
        buckets = {
            '0-20%': 0, '20-40%': 0, '40-60%': 0,
            '60-80%': 0, '80-100%': 0
        }

        for score in scores:
            if score < 20:
                buckets['0-20%'] += 1
            elif score < 40:
                buckets['20-40%'] += 1
            elif score < 60:
                buckets['40-60%'] += 1
            elif score < 80:
                buckets['60-80%'] += 1
            else:
                buckets['80-100%'] += 1

        result = "AI Detection Confidence Distribution\n"
        result += "=" * 50 + "\n\n"
        result += f"Total Submissions: {len(scores)}\n"
        result += f"Average Score: {sum(scores)/len(scores):.1f}%\n"
        result += f"Median Score: {sorted(scores)[len(scores)//2]:.1f}%\n\n"

        result += "Distribution:\n"
        result += "-" * 40 + "\n"

        max_count = max(buckets.values()) if buckets.values() else 1
        for bucket, count in buckets.items():
            bar_length = int(count / max_count * 30)
            bar = "#" * bar_length
            pct = count / len(scores) * 100
            result += f"{bucket:<10} {bar:<30} {count:>5} ({pct:.1f}%)\n"

        result += "\n" + "-" * 40 + "\n"

        # Risk assessment
        high_risk = buckets['80-100%']
        moderate_risk = buckets['60-80%']
        result += f"\nHigh Risk (>80%): {high_risk} ({high_risk/len(scores)*100:.1f}%)\n"
        result += f"Moderate Risk (60-80%): {moderate_risk} ({moderate_risk/len(scores)*100:.1f}%)\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Distribution analysis complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.show_detection_confidence_distribution.dialogs.error', default="Error"), f"Failed to generate distribution: {str(e)}")
