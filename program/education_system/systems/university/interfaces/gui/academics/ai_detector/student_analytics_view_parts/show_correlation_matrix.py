"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_correlation_matrix(self):
    """Show correlations between different detection metrics"""
    try:
        self.update_status("Calculating correlations...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ai_probability, LENGTH(text_content),
                       (LENGTH(text_content) - LENGTH(REPLACE(text_content, ' ', ''))) as word_count
                FROM ai_analysis_history
                WHERE text_content IS NOT NULL
                LIMIT 500
            ''')
            data = cursor.fetchall()
        finally:
            conn.close()

        if len(data) < 10:
            self.analytics_results_text.insert('1.0', "Insufficient data for correlation analysis.")
            return

        # Calculate correlations
        ai_scores = [d[0] for d in data if d[0] is not None]
        lengths = [d[1] for d in data if d[1] is not None]
        words = [d[2] for d in data if d[2] is not None]

        def correlation(x, y):
            n = min(len(x), len(y))
            if n < 2:
                return 0
            x, y = x[:n], y[:n]
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
            den_x = sum((xi - mean_x)**2 for xi in x) ** 0.5
            den_y = sum((yi - mean_y)**2 for yi in y) ** 0.5
            if den_x * den_y == 0:
                return 0
            return num / (den_x * den_y)

        corr_ai_length = correlation(ai_scores, lengths)
        corr_ai_words = correlation(ai_scores, words)
        corr_length_words = correlation(lengths, words)

        result = "Correlation Matrix\n"
        result += "=" * 50 + "\n\n"
        result += "Correlations between detection metrics:\n\n"

        result += f"{'Metric Pair':<35} {'Correlation':<15}\n"
        result += "-" * 50 + "\n"
        result += f"{'AI Score vs Text Length':<35} {corr_ai_length:>+.3f}\n"
        result += f"{'AI Score vs Word Count':<35} {corr_ai_words:>+.3f}\n"
        result += f"{'Text Length vs Word Count':<35} {corr_length_words:>+.3f}\n"

        result += "\n" + "-" * 50 + "\n"
        result += "\nInterpretation:\n"
        result += "Values close to +1: Strong positive correlation\n"
        result += "Values close to -1: Strong negative correlation\n"
        result += "Values close to 0: No correlation\n\n"

        if abs(corr_ai_length) > 0.5:
            result += f"NOTE: {'Longer' if corr_ai_length > 0 else 'Shorter'} texts tend to have higher AI scores.\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Correlation analysis complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.show_correlation_matrix.dialogs.error', default="Error"), f"Failed to calculate correlations: {str(e)}")
