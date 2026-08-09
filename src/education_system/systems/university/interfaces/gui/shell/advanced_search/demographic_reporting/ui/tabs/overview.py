"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from ... import *

class AdvancedUiTabsOverviewMixin:
    def _create_overview_tab(self):
        """Create overview summary tab"""
        # Summary statistics text area
        ttk.Label(
            self.overview_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.overview.labels.demographic_overview_summary', default="Demographic Overview Summary"),
            style='SectionTitle.TLabel'
        ).pack(anchor='w', pady=(0, 10))

        # Create scrollable text area for overview
        text_frame = ttk.Frame(self.overview_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        self.overview_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.overview_text.yview)

        self.overview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _update_overview(self):
        """Update overview summary tab"""
        self.overview_text.delete(1.0, tk.END)

        total = self.report_data['total']
        report = f"""
{'='*70}
                    DEMOGRAPHIC OVERVIEW SUMMARY
{'='*70}
Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Students: {total:,}
{'='*70}

GENDER DISTRIBUTION
{'-'*40}
"""
        for gender, count in sorted(self.report_data['gender'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            bar = self._create_visual_bar(pct, 20)
            report += f"  {gender:<20} {count:>6,}  ({pct:5.1f}%)  {bar}\n"

        report += f"""
STATUS DISTRIBUTION
{'-'*40}
"""
        for status, count in sorted(self.report_data['status'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            bar = self._create_visual_bar(pct, 20)
            report += f"  {status:<20} {count:>6,}  ({pct:5.1f}%)  {bar}\n"

        report += f"""
AGE DISTRIBUTION
{'-'*40}
"""
        age_order = ['Under 20', '20-24', '25-29', '30-39', '40-49', '50+']
        for age_bucket in age_order:
            count = self.report_data['age'].get(age_bucket, 0)
            pct = (count / total * 100) if total > 0 else 0
            bar = self._create_visual_bar(pct, 20)
            report += f"  {age_bucket:<20} {count:>6,}  ({pct:5.1f}%)  {bar}\n"

        report += f"""
TOP 10 COURSES BY ENROLLMENT
{'-'*40}
"""
        sorted_courses = sorted(self.report_data['course'].items(), key=lambda x: -x[1])[:10]
        for course, count in sorted_courses:
            pct = (count / total * 100) if total > 0 else 0
            course_display = course[:30] + '...' if len(course) > 30 else course
            report += f"  {course_display:<35} {count:>5,}  ({pct:4.1f}%)\n"

        report += f"\n{'='*70}\n"

        self.overview_text.insert(tk.END, report)
