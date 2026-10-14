"""Demographic overview tab.

Was a Courier ``tk.Text`` holding ``'='*70`` rules and ASCII bars built
by ``_create_visual_bar`` (``[####------]``). It is now a ReportView, so
the bars are real and proportional and the headline numbers read as
numbers. ``_create_visual_bar`` is still used by the full-report tab,
which is deliberately a plain-text artefact for export.
"""

from datetime import datetime

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.shell.gui import report_view as rv
from ... import *


#: Age buckets in their natural order rather than by size, so the shape
#: of the cohort is readable down the column.
AGE_ORDER = ('Under 20', '20-24', '25-29', '30-39', '40-49', '50+')


class AdvancedUiTabsOverviewMixin:
    def _create_overview_tab(self):
        """Create overview summary tab"""
        self.overview_view = rv.ReportView(self.overview_frame)
        self.overview_view.pack(fill=tk.BOTH, expand=True)
        self.overview_view.empty(
            _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.'
               'overview.labels.no_report_yet',
               default="Generate a report to see the demographic overview."))

    def _update_overview(self):
        """Update overview summary tab"""
        view = getattr(self, 'overview_view', None)
        if view is None or not view.winfo_exists():
            return
        view.clear()

        total = self.report_data['total']
        view.title(
            _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.'
               'overview.labels.demographic_overview_summary',
               default="Demographic Overview Summary"),
            datetime.now().strftime('Generated %d %b %Y at %H:%M'))

        if not total:
            view.empty(_t('gui.shell.advanced_search.demographic_reporting.'
                          'ui.tabs.overview.labels.no_students',
                          default="No students matched the current filters."))
            view.freeze()
            return

        gender = self.report_data.get('gender', {}) or {}
        status = self.report_data.get('status', {}) or {}
        course = self.report_data.get('course', {}) or {}

        view.scorecard([
            (_t('advanced_search.demographics.total_students',
                "Total students"), f"{total:,}", 'info'),
            (_t('advanced_search.demographics.courses', "Courses"),
             f"{len(course):,}", 'info'),
            (_t('advanced_search.demographics.gender_categories',
                "Gender categories"), f"{len(gender):,}", 'info'),
        ])

        view.section(_t('advanced_search.demographics.gender_distribution',
                        "Gender distribution"))
        view.distribution(
            sorted(gender.items(), key=lambda item: -item[1]), total=total)

        view.section(_t('advanced_search.demographics.status_distribution',
                        "Status distribution"))
        view.distribution(
            sorted(status.items(), key=lambda item: -item[1]), total=total)

        view.section(_t('advanced_search.demographics.age_distribution',
                        "Age distribution"))
        ages = self.report_data.get('age', {}) or {}
        # Keep the natural bucket order, and include buckets nobody falls
        # into — an empty '50+' is itself a finding.
        ordered = [(bucket, ages.get(bucket, 0)) for bucket in AGE_ORDER]
        ordered += [(name, count) for name, count in sorted(ages.items())
                    if name not in AGE_ORDER]
        view.distribution(ordered, total=total)

        view.section(_t('advanced_search.demographics.top_courses',
                        "Top 10 courses by enrolment"))
        top = sorted(course.items(), key=lambda item: -item[1])[:10]
        if top:
            view.table(
                [_t('advanced_search.demographics.course', "Course"),
                 _t('advanced_search.demographics.students', "Students"),
                 _t('advanced_search.demographics.share', "Share")],
                [(name, f"{count:,}", f"{count / total * 100:.1f}%")
                 for name, count in top])
        else:
            view.note(_t('advanced_search.demographics.no_courses',
                         "No course data recorded."))

        view.freeze()
