"""Comprehensive report — every measured signal, in three tabs.

The previous version generated 78 ``random`` values: health scores,
uptime, response times, security counts, and a list of "recommendations"
picked from a fixed set regardless of the system's actual state. Every
number here is now measured, and the findings are derived from
thresholds against those measurements rather than chosen at random.
See :mod:`..system_metrics`.
"""

import logging
import tkinter as tk
from tkinter import ttk

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
    def generate_comprehensive_report(self):
        """Measure everything and present it across three tabs."""
        progress = None
        try:
            progress = common.ProgressDialog(
                self.gui.root, _t("batch_ops.windows.generating_comprehensive",
                                  "Comprehensive Report"))
            data = common.collect_with_progress(self.gui, progress)
            path = common.save_report(data, "comprehensive_report")
            progress.close()
            progress = None

            window = common.result_window(
                self.gui, _t("batch_ops.windows.comprehensive_report",
                             "Comprehensive System Report"), "860x680")

            notebook = ttk.Notebook(window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(14, 6))

            views = []

            def tab(label):
                frame = ttk.Frame(notebook)
                notebook.add(frame, text=label)
                view = rv.ReportView(frame)
                view.pack(fill=tk.BOTH, expand=True)
                views.append(view)
                return view

            self._comprehensive_overview(
                tab(_t("batch_ops.tabs.overview", "Overview")), data)
            self._comprehensive_detail(
                tab(_t("batch_ops.tabs.detail", "Detail")), data)
            self._comprehensive_findings(
                tab(_t("batch_ops.tabs.findings", "Findings")), data)
            for view in views:
                view.freeze()

            # The toolbar exports whichever tab is in front, so Copy and
            # Save match what the reader is actually looking at.
            def current_view():
                index = notebook.index(notebook.select())
                return views[index] if 0 <= index < len(views) else views[0]

            class _Proxy:
                def to_text(_self):
                    return current_view().to_text()

            common.footer(window, _Proxy(), path)

        except Exception as exc:
            logger.exception("Comprehensive report failed")
            if progress is not None:
                progress.close()
            messagebox.showerror(
                _t("batch_ops.msg_titles.error"),
                _t("batch_ops.errors.generic_error", error=str(exc)))

    # ── Tab 1: overview ────────────────────────────────────────────

    def _comprehensive_overview(self, view, data):
        health = data['health']
        resources = data['resources']
        operations = data['operations']
        logs = data['logs']

        view.title(_t("batch_ops.labels.comprehensive_report_title",
                      "Comprehensive System Report"),
                   data['generated_at'].replace('T', ' at '))

        if health.get('available'):
            findings = data['findings']
            view.scorecard([
                (_t("batch_ops.labels.health_score", "Health score"),
                 f"{health['overall_score']:.0f}",
                 rv.tone_for(health['overall_score'])),
                (_t("batch_ops.labels.rating", "Rating"), health['rating'],
                 rv.tone_for(health['overall_score'])),
                (_t("batch_ops.labels.findings", "Findings"),
                 len(findings),
                 'good' if not findings else
                 ('bad' if any(f['severity'] == 'bad' for f in findings)
                  else 'warn')),
                (_t("batch_ops.labels.factors", "Factors measured"),
                 health['factors_measured'], 'info'),
            ])
            view.section(_t("batch_ops.labels.health_factors",
                            "Health factors"))
            view.note(_t("batch_ops.labels.headroom_note",
                         "Resource factors are headroom: higher is better."))
            for name, score in health['factors'].items():
                view.metric(name, f"{score:.0f}/100", score)
        else:
            view.empty(_t("batch_ops.labels.nothing_measured",
                          "Nothing could be measured on this system."))
            common.unavailable_note(view, health, "Health score")

        view.section(_t("batch_ops.labels.at_a_glance", "At a glance"))
        if resources.get('available'):
            view.kv(_t("batch_ops.labels.cpu", "CPU"),
                    f"{resources['cpu_percent']}% of "
                    f"{resources['cpu_count']} cores",
                    tone=rv.tone_for(resources['cpu_percent'], 'lower_better'))
            view.kv(_t("batch_ops.labels.memory", "Memory"),
                    f"{resources['memory_used_mb']:,} / "
                    f"{resources['memory_total_mb']:,} MB",
                    tone=rv.tone_for(resources['memory_percent'],
                                     'lower_better'))
            view.kv(_t("batch_ops.labels.disk_free", "Disk free"),
                    f"{resources['disk_free_gb']} GB",
                    tone=rv.tone_for(resources['disk_percent'], 'lower_better'))
        if operations.get('available') and operations.get('success_rate') is not None:
            view.kv(_t("batch_ops.labels.batch_success_rate",
                       "Batch success rate"),
                    f"{operations['success_rate']}% over "
                    f"{operations['runs']} run(s)",
                    tone=rv.tone_for(operations['success_rate']))
        if logs.get('available'):
            view.kv(_t("batch_ops.labels.errors_in_log", "Errors in the log"),
                    f"{logs['errors']:,}",
                    tone='good' if not logs['errors'] else 'bad')

        common.source_footer(view, data)

    # ── Tab 2: detail ──────────────────────────────────────────────

    def _comprehensive_detail(self, view, data):
        view.title(_t("batch_ops.labels.detailed_metrics",
                      "Detailed Metrics"))

        resources = data['resources']
        view.section(_t("batch_ops.labels.host_resources", "Host resources"))
        if resources.get('available'):
            view.metric(_t("batch_ops.labels.cpu_usage", "CPU usage"),
                        f"{resources['cpu_percent']}%",
                        resources['cpu_percent'], direction='lower_better')
            view.metric(_t("batch_ops.labels.memory_usage", "Memory usage"),
                        f"{resources['memory_percent']}%",
                        resources['memory_percent'], direction='lower_better')
            view.metric(_t("batch_ops.labels.disk_usage", "Disk usage"),
                        f"{resources['disk_percent']}%",
                        resources['disk_percent'], direction='lower_better')
        else:
            common.unavailable_note(view, resources, "Host resources")

        database = data['database']
        view.section(_t("batch_ops.labels.database", "Database"))
        if database.get('available'):
            view.kv(_t("batch_ops.labels.size_on_disk", "Size on disk"),
                    f"{database['size_mb']:,} MB")
            view.kv(_t("batch_ops.labels.tables", "Tables"),
                    f"{database['tables']:,}")
            view.kv(_t("batch_ops.labels.indexes", "Indexes"),
                    f"{database['indexes']:,}")
            view.kv(_t("batch_ops.labels.catalogue_query", "Catalogue query"),
                    f"{database['catalogue_query_ms']} ms",
                    tone=rv.tone_for(database['catalogue_query_ms'],
                                     'lower_better'))
            view.kv(_t("batch_ops.labels.journal_mode", "Journal mode"),
                    database['journal_mode'],
                    tone='good' if str(database['journal_mode']).lower() == 'wal'
                         else 'warn')
        else:
            common.unavailable_note(view, database, "Database")

        counts = data['records']
        if counts.get('available') and counts['counts']:
            view.section(_t("batch_ops.labels.record_counts", "Record counts"))
            view.table([_t("batch_ops.labels.table", "Table"),
                        _t("batch_ops.labels.rows", "Rows")],
                       [(name, f"{count:,}")
                        for name, count in sorted(counts['counts'].items())])
            if counts['missing_tables']:
                view.note(_t("batch_ops.labels.tables_absent",
                             "Not present in this database: ")
                          + ", ".join(counts['missing_tables']))

        auth = data['auth']
        view.section(_t("batch_ops.labels.authentication", "Authentication"))
        if auth.get('available'):
            if auth['success_rate'] is not None:
                view.metric(_t("batch_ops.labels.login_success_rate",
                               "Login success rate"),
                            f"{auth['success_rate']}%", auth['success_rate'])
            view.kv(_t("batch_ops.labels.attempts_window",
                       "Attempts in window"),
                    f"{auth['total_attempts']:,} "
                    f"(last {auth['window_hours']}h)")
            view.kv(_t("batch_ops.labels.successful", "Successful"),
                    f"{auth['successful']:,}")
            view.kv(_t("batch_ops.labels.failed", "Failed"),
                    f"{auth['failed']:,}",
                    tone='good' if not auth['failed'] else 'warn')
            view.kv(_t("batch_ops.labels.distinct_users", "Distinct users"),
                    f"{auth['distinct_users']:,}")
            view.kv(_t("batch_ops.labels.distinct_ips", "Distinct IPs"),
                    f"{auth['distinct_ips']:,}")
            view.kv(_t("batch_ops.labels.all_time_attempts",
                       "All-time attempts"),
                    f"{auth['all_time_attempts']:,}")
        else:
            common.unavailable_note(view, auth, "Authentication")

        activity = data['activity']
        view.section(_t("batch_ops.labels.activity", "Activity"))
        if activity.get('available'):
            view.kv(_t("batch_ops.labels.total_events", "Total events"),
                    f"{activity['total_events']:,}")
            if activity.get('recent_events') is not None:
                view.kv(_t("batch_ops.labels.recent_events", "Recent events"),
                        f"{activity['recent_events']:,} in "
                        f"{activity['window_days']} days")
            if activity['by_action']:
                view.distribution([(row['action'], row['count'])
                                   for row in activity['by_action']])
        else:
            common.unavailable_note(view, activity, "Activity")

        logs = data['logs']
        view.section(_t("batch_ops.labels.log_records", "Log records"))
        if logs.get('available'):
            for level, count in sorted(logs['levels'].items(),
                                       key=lambda kv: -kv[1]):
                view.kv(level.title(), f"{count:,}")
        else:
            common.unavailable_note(view, logs, "Application log")

    # ── Tab 3: findings ────────────────────────────────────────────

    def _comprehensive_findings(self, view, data):
        findings = data['findings']
        view.title(_t("batch_ops.labels.findings", "Findings"),
                   _t("batch_ops.labels.findings_subtitle",
                      "Derived from the measurements in this report"))

        if not findings:
            view.empty(_t("batch_ops.labels.no_findings",
                          "Nothing needing attention was found in what "
                          "could be measured."))
        else:
            for severity, label in (('bad', _t("batch_ops.labels.needs_attention",
                                               "Needs attention")),
                                    ('warn', _t("batch_ops.labels.worth_watching",
                                                "Worth watching")),
                                    ('info', _t("batch_ops.labels.notes",
                                                "Notes"))):
                group = [f for f in findings if f['severity'] == severity]
                if not group:
                    continue
                view.section(label)
                for finding in group:
                    view.item(finding['headline'], tone=severity,
                              detail=finding.get('detail') or None)

        # What was *not* measured is as important as what was: a clean
        # findings list means nothing if half the checks never ran.
        view.section(_t("batch_ops.labels.coverage", "Coverage"))
        for key, label in (('resources', 'Host resources'),
                           ('database', 'Database'),
                           ('records', 'Record counts'),
                           ('auth', 'Authentication'),
                           ('activity', 'Activity'),
                           ('logs', 'Application log'),
                           ('operations', 'Batch history')):
            metric = data.get(key, {})
            if metric.get('available'):
                view.kv(label, _t("batch_ops.labels.measured", "measured"),
                        tone='good')
            else:
                view.kv(label,
                        metric.get('note',
                                   _t("batch_ops.labels.not_measured",
                                      "not measured")),
                        tone='muted')
