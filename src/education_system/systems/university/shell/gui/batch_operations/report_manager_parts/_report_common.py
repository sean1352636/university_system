"""Shared scaffolding for the measured Batch Operations reports.

The three report generators all do the same four things: show a progress
dialog, collect metrics, save a JSON artefact, and present the result.
Only the presentation differs, so everything else lives here.

The reports these support were previously built from ``random`` values;
see :mod:`..system_metrics` for what replaced that and for the rule
about never inventing a number.
"""

import datetime
import json
import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.shell.gui.batch_operations import (
    report_view as rv,
)
from education_system.systems.university.shell.gui.batch_operations import (
    system_metrics as sm,
)

logger = logging.getLogger(__name__)

#: Where report JSON is written. Under the university data directory
#: rather than the working directory, which for a GUI launched from a
#: menu is wherever the shell happened to be.
def report_dir():
    from education_system.paths import UNIVERSITY_DATA_DIR
    path = UNIVERSITY_DATA_DIR / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


class ProgressDialog:
    """A small modal progress window used while metrics are collected."""

    def __init__(self, parent, title):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("440x170")
        self.top.transient(parent)
        self.top.grab_set()
        self.top.configure(bg=rv.PAGE_BG)
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f"+{max(0, x)}+{max(0, y)}")

        tk.Label(self.top, text=title, bg=rv.PAGE_BG, fg=rv.TEXT,
                 font=rv.ui_font(11, 'bold')).pack(pady=(18, 6))
        self._var = tk.DoubleVar()
        ttk.Progressbar(self.top, variable=self._var, maximum=100
                        ).pack(fill=tk.X, padx=24, pady=6)
        self._status = tk.Label(self.top, text="", bg=rv.PAGE_BG,
                                fg=rv.TEXT_MUTED, font=rv.ui_font(9))
        self._status.pack()
        self.top.update()

    def step(self, value, message):
        if not self.top.winfo_exists():
            return
        self._var.set(value)
        self._status.config(text=message)
        self.top.update()

    def close(self):
        try:
            if self.top.winfo_exists():
                self.top.grab_release()
                self.top.destroy()
        except tk.TclError:
            logger.debug("Progress dialog already gone", exc_info=True)


def collect_with_progress(gui, progress):
    """Gather every metric, reporting what is being measured as it goes."""
    sources = sm.gui_sources(gui)
    progress.step(15, _t("batch_ops.progress.measuring_resources",
                         "Measuring host resources..."))
    resources = sm.resource_metrics()
    progress.step(35, _t("batch_ops.progress.measuring_database",
                         "Measuring the database..."))
    database = sm.database_metrics(sources['db_path'])
    records = sm.record_counts(sources['db_path'])
    progress.step(55, _t("batch_ops.progress.reading_logs",
                         "Reading the application log..."))
    logs = sm.log_metrics(sources['log_path'])
    progress.step(75, _t("batch_ops.progress.reading_activity",
                         "Reading login and activity history..."))
    auth = sm.auth_metrics(sources['db_path'])
    activity = sm.activity_metrics(sources['db_path'])
    progress.step(90, _t("batch_ops.progress.reading_history",
                         "Reading batch operation history..."))
    operations = sm.operation_metrics(history_path=sources['history_path'],
                                      history=sources['history'])
    data = {
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'resources': resources, 'database': database, 'records': records,
        'auth': auth, 'activity': activity, 'logs': logs,
        'operations': operations,
    }
    data['health'] = sm.health_assessment(resources, database, auth, logs,
                                          operations)
    data['findings'] = [
        {'severity': s, 'headline': h, 'detail': d}
        for s, h, d in sm.build_findings(resources, database, auth, logs,
                                         operations)]
    data['sources'] = {
        'database': str(sources['db_path']),
        'log': str(sources['log_path']) if sources['log_path'] else None,
        'history': str(sources['history_path']),
    }
    progress.step(100, _t("batch_ops.progress.done", "Done"))
    return data


def save_report(data, prefix):
    """Write the report JSON. Returns the path, or None on failure."""
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    path = report_dir() / f"{prefix}_{stamp}.json"
    try:
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2, default=str)
        return path
    except OSError as exc:
        logger.error("Could not save report: %s", exc)
        return None


def unavailable_note(view, metric, what):
    """Render a "not measured" line instead of inventing a figure."""
    view.note(f"{what}: not measured — {metric.get('note', 'unavailable')}.",
              tone='muted')


def render_findings(view, findings, empty_message):
    if not findings:
        view.note(empty_message, tone='good')
        return
    for finding in findings:
        view.item(finding['headline'], tone=finding['severity'],
                  detail=finding.get('detail') or None)


def result_window(gui, title, size="800x660"):
    top = tk.Toplevel(gui.root)
    top.title(title)
    top.geometry(size)
    top.transient(gui.root)
    top.configure(bg=rv.PAGE_BG)
    top.update_idletasks()
    x = (top.winfo_screenwidth() // 2) - (top.winfo_width() // 2)
    y = (top.winfo_screenheight() // 2) - (top.winfo_height() // 2)
    top.geometry(f"+{max(0, x)}+{max(0, y)}")
    return top


def footer(parent, view, path, extra=None):
    """Copy / Save / Open-JSON / Close."""
    bar = tk.Frame(parent, bg=rv.PAGE_BG)
    bar.pack(fill=tk.X, padx=14, pady=(0, 12))

    def open_json():
        import platform
        import subprocess
        import os as _os
        if not path:
            return
        try:
            if platform.system() == 'Windows':
                _os.startfile(str(path))       # noqa: S606
            elif platform.system() == 'Darwin':
                subprocess.run(['open', str(path)], check=False)
            else:
                subprocess.run(['xdg-open', str(path)], check=False)
        except Exception:
            logger.debug("Could not open the report file", exc_info=True)

    buttons = list(extra or [])
    if path:
        buttons.append((_t("batch_ops.buttons.open_report", "Open JSON"),
                        open_json))
    inner = rv.report_toolbar(bar, view, extra=buttons)
    inner.pack(side=tk.LEFT)
    ttk.Button(bar, text=_t("batch_ops.buttons.close", "Close"),
               command=parent.destroy).pack(side=tk.RIGHT)
    return bar


def source_footer(view, data):
    """Say where the numbers came from. A report should be checkable."""
    view.section(_t("batch_ops.labels.sources", "Sources"))
    sources = data.get('sources', {})
    view.kv(_t("batch_ops.labels.database", "Database"),
            sources.get('database') or '—')
    view.kv(_t("batch_ops.labels.log_file", "Log file"),
            sources.get('log') or 'not found')
    logs = data.get('logs', {})
    if logs.get('available'):
        view.kv(_t("batch_ops.labels.log_lines_scanned", "Log lines scanned"),
                f"{logs.get('lines_scanned', 0):,}"
                + (" (tail only)" if logs.get('truncated') else ""))
    view.note(_t("batch_ops.labels.measured_note",
                 "All figures are measured from this installation. Anything "
                 "that could not be measured is marked as such rather than "
                 "estimated."))
