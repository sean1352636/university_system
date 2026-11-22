"""The Service Report: how the support service is doing over a period —
volumes by team, category and channel, first response and resolution
against the SLA, breaches, backlog age, satisfaction and survey response
rate, self-help deflection, and themes.

It is ``features.reports.service_report(actor, from, to, team)``, built on a
worker thread; only the Tk main loop touches widgets (it polls for the
result with ``after``).
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime, timedelta
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

from . import common as _c
from ._dialogs import filedialog, messagebox

logger = logging.getLogger(__name__)


def _rows(report) -> list:
    """The report flattened to ``(section, measure, value)`` rows."""
    out = [('Summary', 'Tickets raised', report.get('total_tickets', 0))]
    for name, counts in (report.get('volumes') or {}).items():
        for key, value in counts.items():
            out.append((f"Volume {name.replace('_', ' ')}", key, value))
    for section in ('first_response', 'resolution'):
        for key, value in (report.get(section) or {}).items():
            out.append((section.replace('_', ' ').title(), key.replace('_', ' '), value))
    for key, value in (report.get('breach_alerts') or {}).items():
        out.append(('Breach alerts', key.replace('_', ' '), value))
    backlog = report.get('backlog') or {}
    for key in ('open', 'oldest_days', 'avg_age_days'):
        out.append(('Backlog', key.replace('_', ' '), backlog.get(key)))
    for key, value in (backlog.get('by_age') or {}).items():
        out.append(('Backlog by age', key, value))
    for key, value in (report.get('satisfaction') or {}).items():
        out.append(('Satisfaction', key.replace('_', ' '), value))
    for key, value in (report.get('deflection') or {}).items():
        out.append(('Self-help', key.replace('_', ' '), value))
    themes = report.get('themes') or {}
    for key, value in (themes.get('top_keywords') or {}).items():
        out.append(('Theme words', key, value))
    for week, cats in (themes.get('by_week') or {}).items():
        out.append(('Themes by week', week, ", ".join(f"{k} {v}" for k, v in cats.items())))
    return out


class ServiceReportMixin:
    """Mixin for StudentSupportGUI: the Service Report screen."""

    def show_service_report(self):
        self.clear_content()
        self.set_view('service_report')
        frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(frame, text=_t('gui.pastoral.student_support.service_report.tabs.report', default="📈 Service Report"))
        if not _c.is_support_staff(self):
            ttk.Label(frame, text=_t('gui.pastoral.student_support.service_report.labels.staff_only', default="❌ Staff access required"),
                      style='Title.TLabel').pack(pady=20)
            return

        top = ttk.Frame(frame)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text=_t('gui.pastoral.student_support.service_report.labels.title', default="📈 Service Report"), style='Title.TLabel').pack(side="left", padx=(0, 20))
        ttk.Label(top, text=_t('gui.pastoral.student_support.service_report.labels.from', default="From:")).pack(side="left")
        self.sr_from = ttk.Entry(top, width=11)
        self.sr_from.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        self.sr_from.pack(side="left", padx=4)
        ttk.Label(top, text=_t('gui.pastoral.student_support.service_report.labels.to', default="To:")).pack(side="left")
        self.sr_to = ttk.Entry(top, width=11)
        self.sr_to.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.sr_to.pack(side="left", padx=4)
        ttk.Label(top, text=_t('gui.pastoral.student_support.service_report.labels.team', default="Team:")).pack(side="left", padx=(10, 0))
        self._sr_teams = {t['label']: t['key'] for t in _c.ss('routing').teams()}
        self.sr_team = ttk.Combobox(top, state="readonly", width=26,
                                    values=[_t('gui.pastoral.student_support.service_report.values.all', default="All teams")] + list(self._sr_teams))
        self.sr_team.current(0)
        self.sr_team.pack(side="left", padx=4)
        ttk.Button(top, text=_t('gui.pastoral.student_support.service_report.buttons.run', default="Run report"),
                   command=self.run_service_report).pack(side="left", padx=8)
        ttk.Button(top, text=_t('gui.pastoral.student_support.service_report.buttons.json', default="Save JSON…"),
                   command=lambda: self._save_service_report('json')).pack(side="right")
        ttk.Button(top, text=_t('gui.pastoral.student_support.service_report.buttons.excel', default="Save Excel…"),
                   command=lambda: self._save_service_report('xlsx')).pack(side="right", padx=4)

        self.sr_status = ttk.Label(frame, foreground=self.colors['text_secondary'])
        self.sr_status.pack(anchor="w")
        self.sr_body = ttk.Frame(frame)
        self.sr_body.pack(fill="both", expand=True)
        self.service_report_data = None
        self.run_service_report()

    def run_service_report(self):
        start, end = self.sr_from.get().strip(), self.sr_to.get().strip()
        for value in (start, end):
            try:
                datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror(_t('gui.pastoral.student_support.service_report.dialogs.dates', default="Dates"),
                                     _t('gui.pastoral.student_support.service_report.dialogs.date_format', default="Dates are YYYY-MM-DD."))
                return
        team = self._sr_teams.get(self.sr_team.get())
        actor = _c.actor(self)
        results = queue.Queue()
        self.sr_status.config(text=_t('gui.pastoral.student_support.service_report.status.running', default="Building the report…"))

        def work():
            try:
                results.put(('ok', _c.ss('features.reports').service_report(actor, start, end, team)))
            except Exception as exc:  # handed to the main thread to show
                results.put(('error', exc))

        def poll():
            try:
                kind, value = results.get_nowait()
            except queue.Empty:
                self.root.after(150, poll)
                return
            if not self.sr_body.winfo_exists():
                return
            if kind == 'error':
                if not isinstance(value, (PermissionError, ValueError)):
                    logger.error("Service report failed: %s", value)
                self.sr_status.config(text=str(value))
                return
            self.service_report_data = value
            self._render_service_report(value)

        threading.Thread(target=work, daemon=True).start()
        self.root.after(150, poll)

    def _render_service_report(self, report):
        for child in self.sr_body.winfo_children():
            child.destroy()
        rng = report.get('date_range') or {}
        self.sr_status.config(text=f"{rng.get('start')} to {rng.get('end')}"
                                   + (f" — {_c.team_label(report['team'])}" if report.get('team') else " — all teams"))
        fr, res = report.get('first_response') or {}, report.get('resolution') or {}
        sat, defl = report.get('satisfaction') or {}, report.get('deflection') or {}
        backlog = report.get('backlog') or {}
        tiles = [
            ("Tickets raised", report.get('total_tickets', 0)),
            ("First response within SLA", f"{fr.get('met_pct') if fr.get('met_pct') is not None else '—'}%  ({fr.get('met', 0)}/{fr.get('measured', 0)})"),
            ("Avg first response", f"{fr.get('avg_hours') if fr.get('avg_hours') is not None else '—'} h"),
            ("Resolved within SLA", f"{res.get('met_pct') if res.get('met_pct') is not None else '—'}%  ({res.get('met', 0)}/{res.get('measured', 0)})"),
            ("Avg resolution", f"{res.get('avg_hours') if res.get('avg_hours') is not None else '—'} h"),
            ("Breaches", f"{fr.get('breached', 0)} response, {res.get('breached', 0)} resolution"),
            ("Open backlog", f"{backlog.get('open', 0)} (oldest {backlog.get('oldest_days', 0)} days)"),
            ("Satisfaction", f"{sat.get('avg_rating') if sat.get('avg_rating') is not None else '—'}/5 from {sat.get('ratings', 0)}; survey response {sat.get('response_rate', 0)}%"),
            ("Self-help deflection", f"{defl.get('deflection_rate', 0)}% of {defl.get('with_suggestions', 0)} visits with suggestions"),
        ]
        grid = ttk.Frame(self.sr_body)
        grid.pack(fill="x", pady=(4, 8))
        for i, (label, value) in enumerate(tiles):
            box = ttk.Frame(grid, style='Card.TFrame', padding=8)
            box.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
            ttk.Label(box, text=label, foreground=self.colors['text_secondary']).pack(anchor="w")
            ttk.Label(box, text=str(value), font=('Segoe UI', 12, 'bold')).pack(anchor="w")
        for c in range(3):
            grid.columnconfigure(c, weight=1)

        tree = _c.tree_with_scroll(self.sr_body, ('section', 'measure', 'value'),
                                   {'section': 'Section', 'measure': 'Measure', 'value': 'Value'},
                                   {'section': 200, 'measure': 260, 'value': 520}, height=14)
        for section, measure, value in _rows(report):
            tree.insert('', 'end', values=(section, measure, '' if value is None else value))

    def _save_service_report(self, fmt):
        report = getattr(self, 'service_report_data', None)
        if not report:
            messagebox.showinfo(_t('gui.pastoral.student_support.service_report.dialogs.save', default="Save report"),
                                _t('gui.pastoral.student_support.service_report.dialogs.run_first', default="Run the report first."))
            return
        path = filedialog.asksaveasfilename(
            title=_t('gui.pastoral.student_support.service_report.dialogs.save', default="Save report"),
            defaultextension=f".{fmt}", initialfile=f"service_report.{fmt}",
            filetypes=[(f"{fmt.upper()} files", f"*.{fmt}")])
        if not path:
            return
        try:
            if fmt == 'json':
                with open(path, 'w', encoding='utf-8') as fh:
                    json.dump(report, fh, indent=2, default=str)
            else:
                _c.write_xlsx(path, ['Section', 'Measure', 'Value'], _rows(report), sheet="Service report")
        except OSError as exc:
            messagebox.showerror(_t('gui.pastoral.student_support.service_report.dialogs.save', default="Save report"), str(exc))
            return
        self.update_status(f"Service report saved to {path}")


__all__ = ['ServiceReportMixin']
