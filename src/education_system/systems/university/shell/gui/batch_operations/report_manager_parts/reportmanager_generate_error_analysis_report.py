"""Error analysis report, parsed from the application log.

The previous version opened with ``total_operations = 1247  # Simulated
data`` and built every category, trend and recommendation from constants
chosen to look plausible. Errors are now read out of the log file and
grouped by an actual keyword classifier; login failures come from
``login_attempts``. See :mod:`..system_metrics`.
"""

import logging
import tkinter as tk

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import report_manager_shared as _shared
from education_system.systems.university.shell.gui.batch_operations import (
    report_view as rv,
)
from . import _report_common as common

globals().update({name: value for name, value in _shared.__dict__.items()
                  if not name.startswith("__")})

logger = logging.getLogger(__name__)


class ReportManager:
    def generate_error_analysis_report(self):
        """Read the log and present what actually failed."""
        progress = None
        try:
            progress = common.ProgressDialog(
                self.gui.root, _t("batch_ops.windows.error_analysis",
                                  "Error Analysis"))
            data = common.collect_with_progress(self.gui, progress)
            path = common.save_report(data, "error_analysis_report")
            progress.close()
            progress = None

            window = common.result_window(
                self.gui, _t("batch_ops.windows.error_analysis",
                             "Error Analysis"), "800x660")
            view = rv.ReportView(window)
            view.pack(fill=tk.BOTH, expand=True, padx=14, pady=(14, 8))
            self._render_error_analysis(view, data)
            view.freeze()
            common.footer(window, view, path)

        except Exception as exc:
            logger.exception("Error analysis report failed")
            if progress is not None:
                progress.close()
            messagebox.showerror(
                _t("batch_ops.msg_titles.error"),
                _t("batch_ops.errors.generic_error", error=str(exc)))

    def _render_error_analysis(self, view, data):
        logs = data['logs']
        auth = data['auth']
        operations = data['operations']

        view.title(_t("batch_ops.windows.error_analysis", "Error Analysis"),
                   data['generated_at'].replace('T', ' at '))

        if not logs.get('available'):
            view.empty(_t("batch_ops.labels.no_log",
                          "No application log could be read, so there is "
                          "nothing to analyse."))
            common.unavailable_note(view, logs, "Application log")
            common.source_footer(view, data)
            return

        errors = logs['errors']
        rate = logs.get('error_rate_percent')
        view.scorecard([
            (_t("batch_ops.labels.errors", "Errors"), f"{errors:,}",
             'good' if not errors else 'bad'),
            (_t("batch_ops.labels.warnings", "Warnings"),
             f"{logs['warnings']:,}",
             'good' if not logs['warnings'] else 'warn'),
            (_t("batch_ops.labels.error_rate", "Error rate"),
             f"{rate}%" if rate is not None else '—',
             rv.tone_for(rate, 'lower_better')),
            (_t("batch_ops.labels.records_parsed", "Records parsed"),
             f"{logs['parsed_records']:,}", 'info'),
        ])
        if logs.get('first_timestamp'):
            view.note(_t("batch_ops.labels.log_window",
                         "Covering {first} to {last}."
                         ).replace("{first}", str(logs['first_timestamp'])
                                   ).replace("{last}", str(logs['last_timestamp'])))

        view.section(_t("batch_ops.labels.by_level", "Records by level"))
        level_tone = {'CRITICAL': 'bad', 'ERROR': 'bad', 'WARNING': 'warn',
                      'INFO': 'info', 'DEBUG': 'muted'}
        for level in ('CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'):
            count = logs['levels'].get(level, 0)
            if count:
                view.kv(level.title(), f"{count:,}",
                        tone=level_tone.get(level, 'muted'))

        view.section(_t("batch_ops.labels.error_categories",
                        "Errors by category"))
        if logs['categories']:
            view.distribution(
                [(row['category'], row['count']) for row in logs['categories']],
                total=errors or None)
        else:
            view.note(_t("batch_ops.labels.no_errors_logged",
                         "No errors were logged in the window scanned."),
                      tone='good')

        view.section(_t("batch_ops.labels.recent_errors", "Most recent errors"))
        if logs['recent_errors']:
            for entry in reversed(logs['recent_errors']):
                view.item(entry['message'], tone='bad',
                          detail=None,
                          meta=f"{entry['timestamp']}  ·  {entry['category']}"
                               f"  ·  {entry['logger']}")
        else:
            view.note(_t("batch_ops.labels.no_errors_logged",
                         "No errors were logged in the window scanned."),
                      tone='good')

        view.section(_t("batch_ops.labels.failed_logins", "Failed logins"))
        if auth.get('available'):
            view.kv(_t("batch_ops.labels.failed_attempts", "Failed attempts"),
                    f"{auth['failed']:,} of {auth['total_attempts']:,} "
                    f"in {auth['window_hours']}h",
                    tone='good' if not auth['failed'] else 'warn')
            if auth['repeat_failures']:
                view.table(
                    [_t("batch_ops.labels.username", "Username"),
                     _t("batch_ops.labels.failures", "Failures")],
                    [(row['username'] or '(blank)', row['failures'])
                     for row in auth['repeat_failures']])
            else:
                view.note(_t("batch_ops.labels.no_repeat_failures",
                             "No account had three or more failures."),
                          tone='good')
        else:
            common.unavailable_note(view, auth, "Login history")

        if operations.get('available') and operations.get('failed'):
            view.section(_t("batch_ops.labels.batch_failures", "Batch failures"))
            view.kv(_t("batch_ops.labels.failed_records", "Failed records"),
                    f"{operations['failed']:,}", tone='bad')
            view.table(
                [_t("batch_ops.labels.operation", "Operation"),
                 _t("batch_ops.labels.failed", "Failed"),
                 _t("batch_ops.labels.success_rate", "Success rate")],
                [(row['operation'], f"{row['failed']:,}",
                  f"{row['success_rate']}%" if row['success_rate'] is not None
                  else '—')
                 for row in operations['by_operation'] if row['failed']])

        view.section(_t("batch_ops.labels.findings", "Findings"))
        common.render_findings(
            view, data['findings'],
            _t("batch_ops.labels.no_findings",
               "Nothing needing attention was found in what could be measured."))

        common.source_footer(view, data)
