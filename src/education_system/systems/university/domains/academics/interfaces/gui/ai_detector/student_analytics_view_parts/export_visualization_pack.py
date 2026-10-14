"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def export_visualization_pack(self):
    """Export all charts/graphs as image pack for reports"""
    try:
        # Select export directory
        export_dir = filedialog.askdirectory(title=_t('gui.academics.ai_detector.student_analytics_view_parts.export_visualization_pack.dialogs.select_export_directory', default="Select Export Directory"))
        if not export_dir:
            return

        self.update_status("Exporting visualization pack...")

        # Create export folder
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pack_dir = os.path.join(export_dir, f"ai_detection_report_{timestamp}")
        os.makedirs(pack_dir, exist_ok=True)

        # Export each analysis as text (since we don't have matplotlib)
        analyses = [
            ("confidence_distribution.txt", self.show_detection_confidence_distribution),
            ("word_analysis.txt", self.generate_word_cloud),
            ("timeline.txt", self.plot_submission_timeline),
            ("correlations.txt", self.show_correlation_matrix),
            ("clustering.txt", self.cluster_similar_submissions),
            ("department_comparison.txt", self.generate_department_comparison),
            ("weekly_trends.txt", self.show_weekly_trends)
        ]

        exported = 0
        for filename, func in analyses:
            try:
                func()
                content = self.analytics_results_text.get('1.0', tk.END)
                file_path = os.path.join(pack_dir, filename)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                exported += 1
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        # Create summary file
        summary = "AI Detection Analytics Export\n"
        summary += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        summary += f"Files Exported: {exported}\n\n"
        summary += "Contents:\n"
        for filename, _ in analyses:
            summary += f"  - {filename}\n"

        with open(os.path.join(pack_dir, "README.txt"), 'w', encoding='utf-8') as f:
            f.write(summary)

        messagebox.showinfo(_t('gui.academics.ai_detector.student_analytics_view_parts.export_visualization_pack.dialogs.success', default="Success"),
                          f"Visualization pack exported!\n\n"
                          f"Location: {pack_dir}\n"
                          f"Files: {exported + 1}")
        self.update_status("Export complete")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.export_visualization_pack.dialogs.error', default="Error"), f"Failed to export: {str(e)}")
