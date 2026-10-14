"""Performance report, measured from this installation.

Previously every figure here came from ``random.uniform`` — CPU, memory,
query times, cache ratios, network latency. They are now measured, and
the ones that cannot be measured from this system (network latency,
packet loss, a database cache-hit ratio for a SQLite file with no cache
layer) have been removed rather than estimated. See
:mod:`..system_metrics`.
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
    def generate_performance_report(self):
        """Measure and display system performance."""
        progress = None
        try:
            progress = common.ProgressDialog(
                self.gui.root, _t("batch_ops.windows.performance_report",
                                  "Performance Report"))
            data = common.collect_with_progress(self.gui, progress)
            path = common.save_report(data, "performance_report")
            progress.close()
            progress = None

            window = common.result_window(
                self.gui, _t("batch_ops.windows.performance_report",
                             "Performance Report"), "780x660")
            view = rv.ReportView(window)
            view.pack(fill=tk.BOTH, expand=True, padx=14, pady=(14, 8))
            self._render_performance(view, data)
            view.freeze()
            common.footer(window, view, path)

        except Exception as exc:
            logger.exception("Performance report failed")
            if progress is not None:
                progress.close()
            messagebox.showerror(
                _t("batch_ops.msg_titles.error"),
                _t("batch_ops.errors.generic_error", error=str(exc)))

    def _render_performance(self, view, data):
        resources = data['resources']
        database = data['database']
        logs = data['logs']
        operations = data['operations']
        health = data['health']

        view.title(_t("batch_ops.labels.performance_report_title",
                      "Performance Report"),
                   data['generated_at'].replace('T', ' at '))

        tiles = []
        if health.get('available'):
            tiles.append((_t("batch_ops.labels.health_score", "Health score"),
                          f"{health['overall_score']:.0f}",
                          rv.tone_for(health['overall_score'])))
            tiles.append((_t("batch_ops.labels.rating", "Rating"),
                          health['rating'],
                          rv.tone_for(health['overall_score'])))
        if resources.get('available'):
            tiles.append((_t("batch_ops.labels.cpu", "CPU"),
                          f"{resources['cpu_percent']}%",
                          rv.tone_for(resources['cpu_percent'], 'lower_better')))
            tiles.append((_t("batch_ops.labels.memory", "Memory"),
                          f"{resources['memory_percent']}%",
                          rv.tone_for(resources['memory_percent'],
                                      'lower_better')))
        if tiles:
            view.scorecard(tiles)
        if health.get('available'):
            view.note(_t("batch_ops.labels.factors_measured",
                         "Score is the mean of {n} measured factor(s)."
                         ).replace("{n}", str(health['factors_measured'])))

        # ── Host resources ─────────────────────────────────────────
        view.section(_t("batch_ops.labels.host_resources", "Host resources"))
        if resources.get('available'):
            view.metric(_t("batch_ops.labels.cpu_usage", "CPU usage"),
                        f"{resources['cpu_percent']}% "
                        f"({resources['cpu_count']} cores)",
                        resources['cpu_percent'], direction='lower_better')
            view.metric(_t("batch_ops.labels.memory_usage", "Memory usage"),
                        f"{resources['memory_percent']}% "
                        f"({resources['memory_used_mb']:,} / "
                        f"{resources['memory_total_mb']:,} MB)",
                        resources['memory_percent'], direction='lower_better')
            view.metric(_t("batch_ops.labels.disk_usage", "Disk usage"),
                        f"{resources['disk_percent']}% "
                        f"({resources['disk_free_gb']} GB free)",
                        resources['disk_percent'], direction='lower_better')
            if resources.get('load_average'):
                view.kv(_t("batch_ops.labels.load_average", "Load average"),
                        ", ".join(str(v) for v in resources['load_average']))
            view.kv(_t("batch_ops.labels.process_memory", "This process"),
                    f"{resources['process_memory_mb']} MB, up "
                    f"{resources['process_uptime_hours']} h")
        else:
            common.unavailable_note(view, resources, "Host resources")

        # ── Database ───────────────────────────────────────────────
        view.section(_t("batch_ops.labels.database", "Database"))
        if database.get('available'):
            query_ms = database['catalogue_query_ms']
            view.kv(_t("batch_ops.labels.catalogue_query", "Catalogue query"),
                    f"{query_ms} ms (median of 3)",
                    tone=rv.tone_for(query_ms, 'lower_better'))
            view.kv(_t("batch_ops.labels.size_on_disk", "Size on disk"),
                    f"{database['size_mb']:,} MB")
            view.kv(_t("batch_ops.labels.tables", "Tables"),
                    f"{database['tables']:,}")
            view.kv(_t("batch_ops.labels.indexes", "Indexes"),
                    f"{database['indexes']:,}")
            view.kv(_t("batch_ops.labels.journal_mode", "Journal mode"),
                    database['journal_mode'],
                    tone='good' if str(database['journal_mode']).lower() == 'wal'
                         else 'warn')
        else:
            common.unavailable_note(view, database, "Database")

        counts = data['records']
        if counts.get('available') and counts.get('counts'):
            view.section(_t("batch_ops.labels.record_counts", "Record counts"))
            view.table([_t("batch_ops.labels.table", "Table"),
                        _t("batch_ops.labels.rows", "Rows")],
                       [(name, f"{count:,}")
                        for name, count in sorted(counts['counts'].items())])

        # ── Batch throughput ───────────────────────────────────────
        view.section(_t("batch_ops.labels.batch_operations", "Batch operations"))
        if operations.get('available'):
            rate = operations.get('success_rate')
            if rate is not None:
                view.metric(_t("batch_ops.labels.success_rate", "Success rate"),
                            f"{rate}%", rate)
            view.kv(_t("batch_ops.labels.runs_recorded", "Runs recorded"),
                    f"{operations['runs']:,}")
            view.kv(_t("batch_ops.labels.records_processed",
                       "Records processed"),
                    f"{operations['total_records']:,}")
            if operations['by_operation']:
                view.table(
                    [_t("batch_ops.labels.operation", "Operation"),
                     _t("batch_ops.labels.runs", "Runs"),
                     _t("batch_ops.labels.records", "Records"),
                     _t("batch_ops.labels.success_rate", "Success rate")],
                    [(row['operation'], f"{row['runs']:,}",
                      f"{row['records']:,}",
                      f"{row['success_rate']}%" if row['success_rate'] is not None
                      else '—')
                     for row in operations['by_operation']])
        else:
            common.unavailable_note(view, operations, "Batch operations")

        # ── Errors ─────────────────────────────────────────────────
        view.section(_t("batch_ops.labels.errors_in_log", "Errors in the log"))
        if logs.get('available'):
            rate = logs.get('error_rate_percent')
            if rate is not None:
                view.metric(_t("batch_ops.labels.error_rate", "Error rate"),
                            f"{rate}% of {logs['parsed_records']:,} records",
                            rate, direction='lower_better')
            view.kv(_t("batch_ops.labels.errors", "Errors"),
                    f"{logs['errors']:,}",
                    tone='good' if not logs['errors'] else 'bad')
            view.kv(_t("batch_ops.labels.warnings", "Warnings"),
                    f"{logs['warnings']:,}",
                    tone='good' if not logs['warnings'] else 'warn')
        else:
            common.unavailable_note(view, logs, "Application log")

        # ── Findings ───────────────────────────────────────────────
        view.section(_t("batch_ops.labels.findings", "Findings"))
        common.render_findings(
            view, data['findings'],
            _t("batch_ops.labels.no_findings",
               "Nothing needing attention was found in what could be measured."))

        common.source_footer(view, data)
