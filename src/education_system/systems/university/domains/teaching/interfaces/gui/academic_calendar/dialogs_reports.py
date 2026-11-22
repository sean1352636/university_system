
from education_system.systems.university.infrastructure.i18n import get_text as _t
import html
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, simpledialog
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Tuple
from education_system.systems.university.infrastructure.i18n import get_text as _
from education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar.utils import safe_grab_set
# Message boxes parented to the window that raised them, not the main
# GUI — see _dialogs.
from education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar._dialogs import messagebox
from education_system.systems.university.infrastructure.ui import report_widgets as _report

gui_logger = logging.getLogger(__name__)

#: Academic calendar events. They live in unified_events tagged
#: source_type 'academic_calendar'; the legacy academic_calendar_events table
#: is retired and empty, which is why the reports and the Event Distribution
#: chart that still read it all showed 0.
_CALENDAR_EVENTS = (
    "(SELECT source_event_id AS id, title AS name, event_date AS date, "
    "start_datetime AS date_start, end_datetime AS date_end, description, "
    "event_type, created_at AS date_added, location, trip_id "
    "FROM unified_events WHERE source_type = 'academic_calendar')"
)

#: House window size; window_sizing clamps it to smaller screens.
_WINDOW_SIZE = "1400x900"
_WINDOW_MIN = (1200, 800)


def _center(window):
    """Centre *window* on screen, never at a negative (off-screen) position."""
    window.update_idletasks()
    x = max(0, (window.winfo_screenwidth() - window.winfo_width()) // 2)
    y = max(0, (window.winfo_screenheight() - window.winfo_height()) // 2)
    window.geometry(f"+{x}+{y}")


def _merge_types(rows, key='event_type', count='count'):
    """Fold event types that differ only by case or spacing ('academic' / 'Academic').

    Returns ``[{'label', 'count', 'rows'}, ...]`` largest first; the label is
    the spelling carrying the most events.
    """
    merged = {}
    for row in rows:
        row = dict(row)
        raw = (row.get(key) or '').strip() or 'Unspecified'
        entry = merged.setdefault(raw.lower(), {'label': raw, 'count': 0, 'best': -1, 'rows': []})
        n = row.get(count) or 0
        if n > entry['best']:
            entry['label'], entry['best'] = raw, n
        entry['count'] += n
        entry['rows'].append(row)
    return sorted(merged.values(), key=lambda e: (-e['count'], e['label'].lower()))


def _month_label(month):
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except (ValueError, TypeError):
        return month or "Undated"


def _trim(text, limit):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def _event_date(event):
    return (event.get('date') or event.get('date_start') or '')[:10]


def _bar_list(parent, items, colour=_report.ACCENT):
    """Labelled proportion bars for ``[(label, value), ...]`` — no matplotlib needed."""
    body = tk.Frame(parent, bg=_report.CARD)
    body.pack(fill=tk.X)
    body.columnconfigure(1, weight=1)
    top = max((value for _label, value in items), default=0) or 1
    for row, (label, value) in enumerate(items):
        tk.Label(body, text=_trim(label, 34), font=(_report.FONT, 9), bg=_report.CARD,
                 fg=_report.HEADER, anchor="w", width=30).grid(row=row, column=0, sticky="w", pady=2)
        track = tk.Canvas(body, height=16, bg="#f1f3f5", highlightthickness=0)
        track.grid(row=row, column=1, sticky="ew", padx=8, pady=2)

        def _draw(event, canvas=track, share=value / top):
            canvas.delete("bar")
            if share:
                canvas.create_rectangle(0, 0, max(2, int(event.width * share)), 16,
                                        fill=colour, width=0, tags="bar")
        track.bind("<Configure>", _draw)
        tk.Label(body, text=f"{value:,}", font=(_report.FONT, 9, "bold"), bg=_report.CARD,
                 fg=_report.VALUE, anchor="e", width=10).grid(row=row, column=2, sticky="e")
    return body


def _table_block(parent, heading, columns, rows, widths=None):
    """A headed table; an empty one says so instead of showing blank rows."""
    if not rows:
        body = _report.card(parent, heading, accent=_report.MUTED)
        tk.Label(body, text="Nothing recorded.", font=(_report.FONT, 9),
                 bg=_report.CARD, fg=_report.MUTED).pack(anchor="w")
        return None
    tk.Label(parent, text=heading, font=(_report.FONT, 10, "bold"), bg=_report.BG,
             fg=_report.HEADER, anchor="w").pack(fill=tk.X, padx=12, pady=(10, 0))
    return _report.table(parent, columns, rows, widths=widths, height=15)


def _render_sections(surface, title, sections):
    """Draw a structured report.

    *sections* is ``{'subtitle': str, 'stats': [(value, label), ...],
    'blocks': [...]}``, each block one of ``('kv', title, pairs)``,
    ``('bars', title, [(label, value), ...])``,
    ``('table', title, columns, rows[, widths])`` or ``('note', title, text)``.
    """
    _report.banner(surface, title, sections.get('subtitle', ''))
    if sections.get('stats'):
        _report.stat_strip(surface, sections['stats'])
    for block in sections.get('blocks', []):
        kind = block[0]
        if kind == 'kv':
            _report.kv_grid(_report.card(surface, block[1]), block[2])
        elif kind == 'bars':
            body = _report.card(surface, block[1])
            if block[2]:
                _bar_list(body, block[2])
            else:
                tk.Label(body, text="Nothing recorded.", font=(_report.FONT, 9),
                         bg=_report.CARD, fg=_report.MUTED).pack(anchor="w")
        elif kind == 'table':
            _table_block(surface, block[1], block[2], block[3],
                         block[4] if len(block) > 4 else None)
        elif kind == 'note':
            body = _report.card(surface, block[1], accent=_report.MUTED)
            tk.Label(body, text=block[2], font=(_report.FONT, 9), bg=_report.CARD,
                     fg=_report.VALUE, anchor="w", justify="left",
                     wraplength=900).pack(anchor="w")

class ReportsDialog:
    """Dialog for generating reports with larger window"""

    def __init__(self, parent, calendar_manager):
        self.calendar_manager = calendar_manager
        self.parent = parent

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.reports.title"))
        self.dialog.geometry(_WINDOW_SIZE)
        self.dialog.minsize(*_WINDOW_MIN)
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.reports.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Report types with descriptions
        reports_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.reports.available_reports"), padding=15)
        reports_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        reports = [
            (_("academic_calendar.messages.report_names.events_summary"), _("academic_calendar.messages.report_names.events_summary_desc"), self._show_events_summary),
            (_("academic_calendar.messages.report_names.academic_year_report"), _("academic_calendar.messages.report_names.academic_year_report_desc"), self._show_academic_year_report),
            (_("academic_calendar.messages.report_names.statistics_report"), _("academic_calendar.messages.report_names.statistics_report_desc"), self._show_statistics_report),
            (_("academic_calendar.messages.report_names.upcoming_events"), _("academic_calendar.messages.report_names.upcoming_events_desc"), self._show_upcoming_events),
            (_("academic_calendar.messages.report_names.monthly_overview"), _("academic_calendar.messages.report_names.monthly_overview_desc"), self._show_monthly_overview),
            (_("academic_calendar.messages.report_names.event_type_analysis"), _("academic_calendar.messages.report_names.event_type_analysis_desc"), self._show_type_analysis)
        ]

        for report_name, description, command in reports:
            report_frame = ttk.Frame(reports_frame)
            report_frame.pack(fill=tk.X, pady=8)

            ttk.Button(report_frame, text=report_name, width=22,
                      command=command).pack(side=tk.LEFT)
            ttk.Label(report_frame, text=description, wraplength=950).pack(side=tk.LEFT, padx=(15, 0))

        # Quick export section
        export_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.reports.quick_export"), padding=10)
        export_frame.pack(fill=tk.X, pady=(0, 15))

        export_btns = ttk.Frame(export_frame)
        export_btns.pack(fill=tk.X)

        ttk.Button(export_btns, text=_("academic_calendar.buttons.export_all_csv"),
                  command=self._export_all_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_btns, text=_("academic_calendar.buttons.export_summary"),
                  command=self._export_summary).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(10, 0))

    def _show_monthly_overview(self):
        """Show monthly overview report"""
        try:
            current_date = datetime.now()
            start_date = (current_date - timedelta(days=180)).strftime("%Y-%m-%d")
            end_date = (current_date + timedelta(days=180)).strftime("%Y-%m-%d")

            events = self.calendar_manager.get_events_by_date_range(start_date, end_date)

            monthly_data = {}
            for event in events:
                date_str = _event_date(event)
                if date_str:
                    monthly_data.setdefault(date_str[:7], []).append(event)
            months = sorted(monthly_data)

            report = "MONTHLY OVERVIEW\n" + "="*60 + "\n\n"
            for month in months:
                report += f"{_month_label(month)} ({len(monthly_data[month])} events)\n"
                report += "-" * 40 + "\n"
                for event in monthly_data[month]:
                    report += f"  {_event_date(event)}: {event.get('name') or ''}\n"
                report += "\n"

            busiest = max(months, key=lambda m: len(monthly_data[m]), default=None)
            blocks = [('bars', "Events per month",
                       [(_month_label(m), len(monthly_data[m])) for m in months])]
            for month in months:
                rows = [(_event_date(e), e.get('name') or '', e.get('event_type') or '',
                         e.get('location') or '')
                        for e in sorted(monthly_data[month], key=_event_date)]
                blocks.append(('table', f"{_month_label(month)} — {len(rows):,} events",
                               ("Date", "Event", "Type", "Location"), rows,
                               {"Date": 110, "Event": 520, "Type": 180, "Location": 200}))
            sections = {
                'subtitle': f"{_month_label(start_date[:7])} to {_month_label(end_date[:7])}",
                'stats': [
                    (f"{len(events):,}", "Events"),
                    (len(months), "Months with events"),
                    (f"{_month_label(busiest)} ({len(monthly_data[busiest]):,})" if busiest else "—",
                     "Busiest month"),
                ],
                'blocks': blocks,
            }
            ReportViewDialog(self.dialog, "Monthly Overview", report, sections)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_generate_monthly", error=str(e)), parent=self.dialog)

    def _show_type_analysis(self):
        """Show event type analysis"""
        try:
            rows = self.calendar_manager.db_manager.execute_query(
                "SELECT event_type, COUNT(*) AS count, "
                "MIN(COALESCE(date, date_start)) AS first_date, "
                "MAX(COALESCE(date, date_start)) AS last_date "
                f"FROM {_CALENDAR_EVENTS} GROUP BY event_type"
            )
            types = _merge_types(rows)
            total = sum(t['count'] for t in types)
            for t in types:
                firsts = [r['first_date'] for r in t['rows'] if r.get('first_date')]
                lasts = [r['last_date'] for r in t['rows'] if r.get('last_date')]
                t['first'] = min(firsts)[:10] if firsts else None
                t['last'] = max(lasts)[:10] if lasts else None

            report = "EVENT TYPE ANALYSIS\n" + "="*60 + "\n\n"
            for t in types:
                pct = (t['count'] / total * 100) if total > 0 else 0
                report += f"{t['label']}\n"
                report += f"  Count: {t['count']} ({pct:.1f}%)\n"
                report += f"  First: {t['first'] or 'N/A'}\n"
                report += f"  Last:  {t['last'] or 'N/A'}\n\n"
            report += f"{'='*60}\nTotal Events: {total}"

            all_first = [t['first'] for t in types if t['first']]
            all_last = [t['last'] for t in types if t['last']]
            sections = {
                'subtitle': "Every calendar event type, with when it first and last occurs",
                'stats': [
                    (f"{total:,}", "Events"),
                    (len(types), "Event types"),
                    (min(all_first) if all_first else "—", "Earliest event"),
                    (max(all_last) if all_last else "—", "Latest event"),
                ],
                'blocks': [
                    ('bars', "Events by type", [(t['label'], t['count']) for t in types]),
                    ('table', "Type breakdown", ("Type", "Events", "Share", "First", "Last"),
                     [(t['label'], f"{t['count']:,}",
                       f"{(t['count'] / total * 100) if total else 0:.1f}%",
                       t['first'] or "—", t['last'] or "—") for t in types],
                     {"Type": 280, "Events": 110, "Share": 100, "First": 140, "Last": 140}),
                ],
            }
            ReportViewDialog(self.dialog, "Event Type Analysis", report, sections)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_generate_analysis", error=str(e)), parent=self.dialog)

    def _export_all_csv(self):
        """Export all events to CSV"""
        filename = filedialog.asksaveasfilename(
            title=_("academic_calendar.messages.file_dialog.export_events_csv"),
            defaultextension=".csv",
            filetypes=[(_("academic_calendar.messages.file_dialog.csv_files"), "*.csv"), (_("academic_calendar.messages.file_dialog.all_files"), "*.*")],
            parent=self.dialog
        )

        if filename:
            try:
                events = self.calendar_manager.db_manager.execute_query(
                    f"SELECT * FROM {_CALENDAR_EVENTS} ORDER BY COALESCE(date, date_start) DESC"
                )

                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("Name,Date,End Date,Type,Description\n")
                    for row in events:
                        event = dict(row)
                        # Private events (personal invitations) belong to the
                        # people they name, not in an institution-wide export.
                        if str(event.get('audience') or '').strip().lower() == 'private':
                            continue
                        name = (event.get('name', '') or event.get('title', '') or '').replace(',', ';')
                        date = event.get('date') or event.get('date_start', '')
                        end_date = event.get('date_end', '')
                        etype = event.get('event_type', '')
                        desc = (event.get('description', '') or '').replace(',', ';').replace('\n', ' ')[:100]
                        f.write(f"{name},{date},{end_date},{etype},{desc}\n")

                messagebox.showinfo(_("common.success"), _("academic_calendar.messages.exported_events", count=len(events), filename=filename), parent=self.dialog)

            except Exception as e:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_export", error=str(e)), parent=self.dialog)

    def _export_summary(self):
        """Export calendar summary to text file"""
        filename = filedialog.asksaveasfilename(
            title=_("academic_calendar.messages.file_dialog.export_summary"),
            defaultextension=".txt",
            filetypes=[(_("academic_calendar.messages.file_dialog.text_files"), "*.txt"), (_("academic_calendar.messages.file_dialog.all_files"), "*.*")],
            parent=self.dialog
        )

        if filename:
            try:
                stats = self.calendar_manager.get_system_stats()

                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("CALENDAR SUMMARY REPORT\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(f"Current Academic Year: {stats.get('current_academic_year', 'None')}\n")
                    f.write(f"Current Semester: {stats.get('current_semester', 'None')}\n")
                    f.write(f"Total Academic Years: {stats.get('total_academic_years', 0)}\n")
                    f.write(f"Total Semesters: {stats.get('total_semesters', 0)}\n")
                    f.write(f"Upcoming Events (30 days): {stats.get('upcoming_events', 0)}\n\n")
                    f.write("Events by Type:\n")
                    for event_type, count in stats.get('events_by_type', {}).items():
                        f.write(f"  {event_type}: {count}\n")

                messagebox.showinfo(_("common.success"), _("academic_calendar.messages.summary_exported", filename=filename), parent=self.dialog)

            except Exception as e:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_export", error=str(e)), parent=self.dialog)

    def _generate_report(self, report_type):
        """Generate selected report"""
        try:
            if "Events Summary" in report_type:
                self._show_events_summary()
            elif "Academic Year" in report_type:
                self._show_academic_year_report()
            elif "Statistics" in report_type:
                self._show_statistics_report()
            elif "Upcoming Events" in report_type:
                self._show_upcoming_events()
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate report: {e}")

    def _show_events_summary(self):
        """Show events summary"""
        try:
            rows = self.calendar_manager.db_manager.execute_query(
                f"SELECT event_type, COUNT(*) AS count FROM {_CALENDAR_EVENTS} GROUP BY event_type"
            )
            types = _merge_types(rows)
            total_events = sum(t['count'] for t in types)

            summary = "EVENTS SUMMARY\n" + "="*50 + "\n\n"
            for t in types:
                summary += f"{t['label']}: {t['count']} events\n"
            summary += f"\nTotal Events: {total_events}"

            sections = {
                'subtitle': "All academic calendar events, by type",
                'stats': [
                    (f"{total_events:,}", "Events"),
                    (len(types), "Event types"),
                    (types[0]['label'] if types else "—", "Most common type"),
                ],
                'blocks': [
                    ('bars', "Events by type", [(t['label'], t['count']) for t in types]),
                    ('table', "Breakdown", ("Type", "Events", "Share"),
                     [(t['label'], f"{t['count']:,}",
                       f"{(t['count'] / total_events * 100) if total_events else 0:.1f}%")
                      for t in types],
                     {"Type": 320, "Events": 120, "Share": 120}),
                ],
            }
            ReportViewDialog(self.dialog, "Events Summary", summary, sections)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate events summary: {e}")

    def _show_academic_year_report(self):
        """Show academic year report"""
        try:
            if not self.calendar_manager:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.calendar_manager_not_available"))
                return

            # Fetch available academic years
            year_rows = self.calendar_manager.db_manager.execute_query(
                "SELECT id, start_date, end_date FROM academic_years ORDER BY start_date DESC"
            )

            if not year_rows:
                messagebox.showinfo(
                    _t('gui.academics.academic_calendar.dialogs_reports.dialogs.academic_year_report', default="Academic Year Report"),
                    _t('gui.academics.academic_calendar.dialogs_reports.dialogs.no_academic_years_found_please_add_an_academic_year_before_gener', default="No academic years found. Please add an academic year before generating a report.")
                )
                return

            year_lookup = {row['id']: dict(row) for row in year_rows}

            # Determine which academic year to report on
            if len(year_lookup) == 1:
                selected_year_id = next(iter(year_lookup))
            else:
                default_year_id = None
                current_year = None
                try:
                    current_year = self.calendar_manager.get_current_academic_year()
                except Exception as err:
                    gui_logger.warning(f"Unable to determine current academic year: {err}")

                if current_year and current_year.get('id') in year_lookup:
                    default_year_id = current_year['id']

                options_text = "\n".join(f" • {row['id']} ({row['start_date']} → {row['end_date']})"
                                         for row in year_rows)
                prompt = ("Enter the academic year identifier to report on:\n\n"
                          f"{options_text}\n\n"
                          "Leave blank to cancel.")

                selected_year_id = simpledialog.askstring(
                    _t('gui.academics.academic_calendar.dialogs_reports.dialogs.select_academic_year', default="Select Academic Year"),
                    prompt,
                    parent=self.dialog,
                    initialvalue=default_year_id or year_rows[0]['id']
                )

                if not selected_year_id:
                    return  # User cancelled

                selected_year_id = selected_year_id.strip()
                if selected_year_id not in year_lookup:
                    messagebox.showerror(
                        _t('gui.academics.academic_calendar.dialogs_reports.dialogs.invalid_selection', default="Invalid Selection"),
                        f"The academic year '{selected_year_id}' is not in the available list."
                    )
                    return

            # Generate the detailed summary from the calendar manager
            summary = self.calendar_manager.advanced_reporting.generate_academic_year_summary(selected_year_id)
            if not summary or not summary.get('success'):
                message = summary.get('error') if isinstance(summary, dict) else "Unknown error."
                messagebox.showerror(_t('gui.academics.academic_calendar.dialogs_reports.dialogs.error', default="Error"), f"Failed to generate report: {message}")
                return

            year_info = summary['academic_year']
            semesters = summary.get('semesters', [])
            events = summary.get('events', [])
            event_stats = summary.get('event_statistics', {})
            monthly_dist = summary.get('monthly_distribution', {})

            start_date = year_info.get('start_date', 'N/A')
            end_date = year_info.get('end_date', 'N/A')
            try:
                duration_days = (datetime.strptime(end_date, "%Y-%m-%d") -
                                 datetime.strptime(start_date, "%Y-%m-%d")).days + 1
            except Exception:
                duration_days = "N/A"

            report_lines = [
                f"ACADEMIC YEAR REPORT: {selected_year_id}",
                "=" * 60,
                "",
                f"Date Range       : {start_date} → {end_date}",
                f"Duration         : {duration_days} days" if isinstance(duration_days, int)
                                   else f"Duration         : {duration_days}",
                f"Total Semesters  : {len(semesters)}",
                f"Total Events     : {summary.get('total_events', 0)}",
                ""
            ]

            # Semesters overview
            report_lines.append("Semesters")
            report_lines.append("-" * 60)
            if semesters:
                for idx, semester in enumerate(semesters, start=1):
                    report_lines.append(
                        f"{idx}. {semester.get('name', 'Unnamed')} "
                        f"({semester.get('start_date', '?')} → {semester.get('end_date', '?')})"
                    )
            else:
                report_lines.append("No semesters recorded for this academic year.")
            report_lines.append("")

            # Event statistics by type
            report_lines.append("Events by Type")
            report_lines.append("-" * 60)
            if event_stats:
                for event_type, count in sorted(event_stats.items(), key=lambda item: (-item[1], item[0])):
                    report_lines.append(f"{event_type}: {count} event(s)")
            else:
                report_lines.append("No events recorded for this academic year.")
            report_lines.append("")

            # Monthly distribution
            report_lines.append("Monthly Distribution")
            report_lines.append("-" * 60)
            if monthly_dist:
                for month, count in sorted(monthly_dist.items()):
                    try:
                        month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
                    except Exception:
                        month_label = month
                    report_lines.append(f"{month_label}: {count} event(s)")
            else:
                report_lines.append("No monthly activity recorded.")
            report_lines.append("")

            # Highlight of key events (first 10 chronologically)
            report_lines.append("Key Events")
            report_lines.append("-" * 60)
            if events:
                def event_sort_key(evt: Dict[str, Any]) -> Tuple[Optional[datetime], str]:
                    date_str = evt.get('date') or evt.get('date_start')
                    # Undated events sort last. They used to sort as None,
                    # which cannot be compared with a datetime and aborted the
                    # whole report as soon as one dated and one undated event
                    # were both present.
                    try:
                        sort_date = datetime.strptime((date_str or '')[:10], "%Y-%m-%d")
                    except Exception:
                        sort_date = datetime.max
                    return (sort_date, evt.get('name') or '')

                sorted_events = sorted(events, key=event_sort_key)
                for event in sorted_events[:10]:
                    event_date = event.get('date') or event.get('date_start') or "N/A"
                    event_type = event.get('event_type', 'Unknown')
                    event_name = event.get('name', 'Untitled Event')
                    semester_name = event.get('semester_name') or 'Unassigned'
                    report_lines.append(f"{event_date} • {event_name} [{event_type}] — Semester: {semester_name}")
                    description = event.get('description')
                    if description:
                        trimmed = description.strip()
                        if len(trimmed) > 120:
                            trimmed = trimmed[:117] + "..."
                        report_lines.append(f"    {trimmed}")
                if len(sorted_events) > 10:
                    report_lines.append(f"...and {len(sorted_events) - 10} additional event(s).")
            else:
                report_lines.append("No events recorded for this academic year.")
            report_lines.append("")

            report_lines.append(f"Report generated at: {summary.get('generated_at', datetime.now().isoformat())}")

            report_content = "\n".join(report_lines)

            year_types = _merge_types([{'event_type': k, 'count': v} for k, v in event_stats.items()])
            ordered_events = sorted(events, key=lambda evt: (_event_date(evt) or '9999-99-99',
                                                             evt.get('name') or ''))
            sections = {
                'subtitle': f"{start_date} → {end_date}",
                'stats': [
                    (f"{summary.get('total_events', 0):,}", "Events"),
                    (len(semesters), "Semesters"),
                    (f"{duration_days:,}" if isinstance(duration_days, int) else duration_days, "Days"),
                    (len(year_types), "Event types"),
                ],
                'blocks': [
                    ('table', "Semesters", ("Semester", "Start", "End"),
                     [(s.get('name') or 'Unnamed', s.get('start_date') or '?', s.get('end_date') or '?')
                      for s in semesters],
                     {"Semester": 360, "Start": 160, "End": 160}),
                    ('bars', "Events by type", [(t['label'], t['count']) for t in year_types]),
                    ('bars', "Events per month",
                     [(_month_label(m), c) for m, c in sorted(monthly_dist.items())]),
                    ('table', f"Events ({len(ordered_events):,})", ("Date", "Event", "Type", "Semester"),
                     [(_event_date(e) or '—', e.get('name') or 'Untitled Event',
                       e.get('event_type') or 'Unknown', e.get('semester_name') or 'Unassigned')
                      for e in ordered_events],
                     {"Date": 110, "Event": 520, "Type": 180, "Semester": 220}),
                ],
            }
            ReportViewDialog(self.dialog, f"Academic Year Report ({selected_year_id})",
                             report_content, sections)

        except PermissionError as perm_err:
            messagebox.showerror(_t('gui.academics.academic_calendar.dialogs_reports.dialogs.permission_denied', default="Permission Denied"), str(perm_err))
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.academic_calendar.dialogs_reports.dialogs.error', default="Error"), f"Failed to generate academic year report: {exc}")

    def _show_statistics_report(self):
        """Show statistics report"""
        try:
            stats = self.calendar_manager.get_system_stats()
            types = _merge_types([{'event_type': k, 'count': v}
                                  for k, v in stats.get('events_by_type', {}).items()])
            total = sum(t['count'] for t in types)

            report = "CALENDAR STATISTICS\n" + "="*50 + "\n\n"
            report += f"Current Academic Year: {stats.get('current_academic_year', 'None')}\n"
            report += f"Current Semester: {stats.get('current_semester', 'None')}\n"
            report += f"Total Academic Years: {stats.get('total_academic_years', 0)}\n"
            report += f"Total Semesters: {stats.get('total_semesters', 0)}\n"
            report += f"Upcoming Events (30 days): {stats.get('upcoming_events', 0)}\n\n"
            report += "Events by Type:\n"
            for t in types:
                report += f"  {t['label']}: {t['count']}\n"

            sections = {
                'subtitle': "Calendar-wide figures",
                'stats': [
                    (f"{total:,}", "Events"),
                    (stats.get('upcoming_events', 0), "Next 30 days"),
                    (stats.get('total_academic_years', 0), "Academic years"),
                    (stats.get('total_semesters', 0), "Semesters"),
                ],
                'blocks': [
                    ('kv', "Current period", [
                        ("Academic year", stats.get('current_academic_year', 'None')),
                        ("Semester", stats.get('current_semester', 'None')),
                    ]),
                    ('bars', "Events by type", [(t['label'], t['count']) for t in types]),
                ],
            }
            ReportViewDialog(self.dialog, "Statistics Report", report, sections)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate statistics: {e}")

    def _show_upcoming_events(self):
        """Show upcoming events"""
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

            events = sorted(self.calendar_manager.get_events_by_date_range(current_date, future_date),
                            key=_event_date)

            report = "UPCOMING EVENTS (Next 30 Days)\n" + "="*50 + "\n\n"
            if events:
                for event in events:
                    report += f"{_event_date(event)}: {event.get('name') or ''} ({event.get('event_type') or ''})\n"
                    if event.get('description'):
                        report += f"   {_trim(event['description'], 100)}\n"
                    report += "\n"
            else:
                report += "No upcoming events found."

            rows = [(_event_date(e), e.get('name') or '', e.get('event_type') or '',
                     e.get('location') or '', _trim(e.get('description'), 90))
                    for e in events]
            sections = {
                'subtitle': f"{current_date} to {future_date}",
                'stats': [
                    (len(events), "Upcoming events"),
                    (len({r[2].lower() for r in rows}), "Event types"),
                    (rows[0][0] if rows else "—", "Next event"),
                ],
                'blocks': ([('table', "Next 30 days", ("Date", "Event", "Type", "Location", "Details"), rows,
                             {"Date": 110, "Event": 380, "Type": 160, "Location": 160, "Details": 420})]
                           if rows else [('note', "Next 30 days", "No events in the next 30 days.")]),
            }
            ReportViewDialog(self.dialog, "Upcoming Events", report, sections)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to get upcoming events: {e}")

    def _center_dialog(self):
        """Center dialog on parent"""
        _center(self.dialog)


class ReportViewDialog:
    """Dialog for viewing generated reports with save and email functionality.

    *content* is the plain-text version of the report, kept for Save, Copy
    and Email. When *sections* is given (see ``_render_sections``) the window
    shows the report as headline figures, cards, bars and tables instead of a
    wall of monospace text.
    """

    def __init__(self, parent, title, content, sections=None):
        self.parent = parent
        self.content = content
        self.title_text = title
        self.sections = sections

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry(_WINDOW_SIZE)
        self.dialog.minsize(*_WINDOW_MIN)
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets(content)
        self._center_dialog()

    def _create_widgets(self, content):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=8 if self.sections else 20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Buttons first, against the bottom, so a long report can never push
        # them out of the window.
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        self.text_widget = None
        if self.sections:
            body = tk.Frame(main_frame, bg=_report.BG)
            body.pack(fill=tk.BOTH, expand=True)
            _render_sections(_report.scrollable(body), self.title_text, self.sections)
        else:
            ttk.Label(main_frame, text=self.title_text,
                     font=('Arial', 12, 'bold')).pack(pady=(0, 10))
            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
            self.text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=('Consolas', 10))
            self.text_widget.pack(fill=tk.BOTH, expand=True)
            self.text_widget.insert(1.0, content)
            self.text_widget.config(state=tk.DISABLED)

        # Left side buttons
        left_btns = ttk.Frame(button_frame)
        left_btns.pack(side=tk.LEFT)

        ttk.Button(left_btns, text=_("academic_calendar.buttons.save_txt"),
                  command=lambda: self._save_report(content, 'txt')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_btns, text=_("academic_calendar.buttons.save_csv"),
                  command=lambda: self._save_report(content, 'csv')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_btns, text=_("academic_calendar.buttons.copy"),
                  command=lambda: self._copy_report(content)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_btns, text=_("academic_calendar.buttons.email_admin"),
                  command=lambda: self._email_to_admin(content)).pack(side=tk.LEFT, padx=(0, 5))

        # Right side close button
        ttk.Button(button_frame, text=_("common.close"), command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _save_report(self, content, file_type='txt'):
        """Save report to file"""
        if file_type == 'csv':
            filename = filedialog.asksaveasfilename(
                title=_("academic_calendar.messages.file_dialog.save_report"),
                defaultextension=".csv",
                filetypes=[(_("academic_calendar.messages.file_dialog.csv_files"), "*.csv"), (_("academic_calendar.messages.file_dialog.all_files"), "*.*")],
                parent=self.dialog
            )
        else:
            filename = filedialog.asksaveasfilename(
                title=_("academic_calendar.messages.file_dialog.save_report"),
                defaultextension=".txt",
                filetypes=[(_("academic_calendar.messages.file_dialog.text_files"), "*.txt"), (_("academic_calendar.messages.file_dialog.all_files"), "*.*")],
                parent=self.dialog
            )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo(_("common.success"), _("academic_calendar.messages.report_saved", filename=filename), parent=self.dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_save_report", error=str(e)), parent=self.dialog)

    def _copy_report(self, content):
        """Copy report to clipboard"""
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(content)
        messagebox.showinfo(_("academic_calendar.messages.copied"), _("academic_calendar.messages.report_copied"), parent=self.dialog)

    def _email_to_admin(self, content):
        """Email report to admin"""
        try:
            # Try to import email service
            try:
                from education_system.systems.university.infrastructure.email.email_service import queue_email
                from education_system.systems.university.infrastructure.database.db import get_connection
                from education_system.systems.university.infrastructure.email.template_utils import render_template
                email_available = True
            except ImportError:
                email_available = False

            if not email_available:
                messagebox.showwarning(_("academic_calendar.messages.email_unavailable"),
                    _("academic_calendar.messages.email_unavailable_message"),
                    parent=self.dialog)
                return

            # Get admin email from database
            admin_email = None
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT email FROM users
                        WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                    if result and result[0]:
                        admin_email = result[0]
            except Exception as e:
                gui_logger.warning(f"Failed to get admin email: {e}")

            if not admin_email:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.no_admin_email"), parent=self.dialog)
                return

            # Render email from template
            try:
                subject, body = render_template("calendar_report", {
                    "report_title": self.title_text,
                    "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    # Escaped: the template drops this into a pre-wrap div,
                    # so a '<' or '&' in the report would mangle the HTML.
                    "report_content": html.escape(content),
                    "separator": "-" * 50
                })
                if not subject or not body:
                    raise ValueError("template render returned no content")
            except Exception as template_error:
                gui_logger.warning(f"Failed to render email template: {template_error}. Using fallback.")
                # Fallback to simple text if template fails
                subject = f"Calendar Report: {self.title_text}"
                body = f"""Academic Calendar Report

Report: {self.title_text}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'-' * 50}

{content}

{'-' * 50}

This report was generated by the Academic Calendar System.
"""

            result = queue_email(admin_email, subject, body)

            if result:
                messagebox.showinfo(_("common.success"), _("academic_calendar.messages.report_sent_to", email=admin_email), parent=self.dialog)
            else:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_send_email"), parent=self.dialog)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_email_report", error=str(e)), parent=self.dialog)

    def _center_dialog(self):
        """Center dialog on parent"""
        _center(self.dialog)


class DataVisualizationDialog:
    """Dialog for data visualization options with full matplotlib visualizations"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        self.parent = parent

        # Check matplotlib availability
        self.matplotlib_available = False
        try:
            import matplotlib
            matplotlib.use('TkAgg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            self.matplotlib_available = True
            self.plt = plt
            self.Figure = Figure
            self.FigureCanvasTkAgg = FigureCanvasTkAgg
        except ImportError:
            pass

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.visualization.title"))
        self.dialog.geometry(_WINDOW_SIZE)
        self.dialog.minsize(*_WINDOW_MIN)
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.visualization.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Status indicator
        status_text = _("academic_calendar.messages.matplotlib_available") if self.matplotlib_available else _("academic_calendar.messages.matplotlib_not_installed")
        status_color = "green" if self.matplotlib_available else "orange"
        status_label = ttk.Label(main_frame, text=status_text, foreground=status_color)
        status_label.pack(pady=(0, 10))

        # Create paned window for buttons and visualization area
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Left panel - visualization buttons
        left_frame = ttk.LabelFrame(paned, text=_("academic_calendar.dialogs.visualization.list"), padding=10)
        paned.add(left_frame, weight=1)

        visualizations = [
            (_("academic_calendar.messages.visualization_names.calendar_heatmap"), _("academic_calendar.messages.visualization_names.calendar_heatmap_desc"), self._create_heatmap),
            (_("academic_calendar.messages.visualization_names.event_distribution"), _("academic_calendar.messages.visualization_names.event_distribution_desc"), self._create_distribution),
            (_("academic_calendar.messages.visualization_names.monthly_trends"), _("academic_calendar.messages.visualization_names.monthly_trends_desc"), self._create_monthly_trends),
            (_("academic_calendar.messages.visualization_names.event_timeline"), _("academic_calendar.messages.visualization_names.event_timeline_desc"), self._create_timeline),
            (_("academic_calendar.messages.visualization_names.utilization_chart"), _("academic_calendar.messages.visualization_names.utilization_chart_desc"), self._create_utilization),
            (_("academic_calendar.messages.visualization_names.attendance_trends"), _("academic_calendar.messages.visualization_names.attendance_trends_desc"), self._create_attendance)
        ]

        for viz_name, description, command in visualizations:
            viz_btn = ttk.Button(left_frame, text=viz_name, width=20, command=command)
            viz_btn.pack(fill=tk.X, pady=3)
            ttk.Label(left_frame, text=description, font=('Arial', 8)).pack(anchor=tk.W)

        # Right panel - visualization display area
        self.viz_frame = ttk.LabelFrame(paned, text=_("academic_calendar.dialogs.visualization.display"), padding=10)
        paned.add(self.viz_frame, weight=3)

        # Initial message
        self.viz_content = ttk.Label(self.viz_frame, text=_("academic_calendar.dialogs.reports.select_visualization"),
                                     font=('Arial', 12))
        self.viz_content.pack(expand=True)

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(10, 0))

    def _clear_viz_area(self):
        """Clear visualization area"""
        for widget in self.viz_frame.winfo_children():
            widget.destroy()

    def _embed(self, fig, parent):
        """Draw a matplotlib figure into *parent*, keeping the canvas alive."""
        canvas = self.FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.X, expand=True)
        self.__dict__.setdefault('_canvases', []).append(canvas)
        return canvas

    @staticmethod
    def _style_axes(ax):
        """Recessive chrome: no box, faint value grid only."""
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#d5d4d0')
        ax.spines['bottom'].set_color('#d5d4d0')
        ax.xaxis.grid(True, color='#eceae6', linewidth=0.8)
        ax.set_axisbelow(True)

    def _create_heatmap(self):
        """Create calendar heatmap visualization"""
        year = simpledialog.askinteger(_t('gui.academics.academic_calendar.dialogs_reports.dialogs.calendar_heatmap', default="Calendar Heatmap"), _t('gui.academics.academic_calendar.dialogs_reports.dialogs.enter_year', default="Enter year:"),
                                     initialvalue=datetime.now().year,
                                     parent=self.dialog)
        if not year:
            return

        try:
            # Get event data for the year
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
            events = self.calendar_manager.get_events_by_date_range(start_date, end_date)

            # Count events by date
            event_counts = {}
            for event in events:
                date = event.get('date') or event.get('date_start', '')
                if date:
                    event_counts[date] = event_counts.get(date, 0) + 1

            self._clear_viz_area()

            if self.matplotlib_available and event_counts:
                # Create matplotlib heatmap
                fig = self.Figure(figsize=(8, 5), dpi=100)
                ax = fig.add_subplot(111)

                # Create monthly data
                months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                monthly_counts = [0] * 12

                for date_str, count in event_counts.items():
                    try:
                        month = int(date_str.split('-')[1]) - 1
                        monthly_counts[month] += count
                    except (IndexError, ValueError):
                        pass

                colors = self.plt.cm.YlOrRd([c/max(monthly_counts) if max(monthly_counts) > 0 else 0
                                             for c in monthly_counts])
                bars = ax.bar(months, monthly_counts, color=colors)
                ax.set_xlabel('Month')
                ax.set_ylabel('Event Count')
                ax.set_title(f'Event Heatmap for {year}')

                # Add value labels on bars
                for bar, count in zip(bars, monthly_counts):
                    if count > 0:
                        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                               str(count), ha='center', va='bottom', fontsize=9)

                fig.tight_layout()

                canvas = self.FigureCanvasTkAgg(fig, master=self.viz_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            else:
                # Text-based visualization
                text_widget = scrolledtext.ScrolledText(self.viz_frame, wrap=tk.WORD, font=('Consolas', 10))
                text_widget.pack(fill=tk.BOTH, expand=True)

                report = f"CALENDAR HEATMAP - {year}\n{'='*50}\n\n"
                report += f"Total Events: {len(events)}\n\n"
                report += "Events by Month:\n" + "-"*30 + "\n"

                monthly_counts = {}
                for date_str, count in event_counts.items():
                    try:
                        month = date_str[:7]
                        monthly_counts[month] = monthly_counts.get(month, 0) + count
                    except (TypeError, IndexError):
                        pass

                for month in sorted(monthly_counts.keys()):
                    count = monthly_counts[month]
                    bar = "*" * min(count, 50)
                    report += f"{month}: {bar} ({count})\n"

                text_widget.insert(tk.END, report)
                text_widget.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_create_heatmap", error=str(e)), parent=self.dialog)

    def _create_distribution(self):
        """Event counts by type, as sorted bars.

        Bars rather than a pie: one type holds most of the events here, which
        turns a pie into one huge slice with unreadable slivers.
        """
        try:
            rows = self.calendar_manager.db_manager.execute_query(
                f"SELECT event_type, COUNT(*) AS count FROM {_CALENDAR_EVENTS} GROUP BY event_type"
            )
            types = _merge_types(rows)
            total = sum(t['count'] for t in types)

            self._clear_viz_area()
            surface = _report.scrollable(self.viz_frame)
            _report.stat_strip(surface, [
                (f"{total:,}", "Calendar events"),
                (len(types), "Event types"),
                (types[0]['label'] if types else "—", "Most common type"),
            ])

            if not types:
                body = _report.card(surface, "Event distribution", accent=_report.MUTED)
                tk.Label(body, text="No academic calendar events found.", font=(_report.FONT, 9),
                         bg=_report.CARD, fg=_report.MUTED).pack(anchor="w")
                return

            if self.matplotlib_available:
                ordered = list(reversed(types))   # largest at the top
                labels = [t['label'] for t in ordered]
                counts = [t['count'] for t in ordered]
                fig = self.Figure(figsize=(9, max(3.5, 0.45 * len(ordered) + 1.4)), dpi=100)
                ax = fig.add_subplot(111)
                bars = ax.barh(labels, counts, color='#2a78d6', height=0.65)
                span = max(counts)
                for bar, count in zip(bars, counts):
                    ax.text(bar.get_width() + span * 0.01, bar.get_y() + bar.get_height() / 2,
                            f"{count:,} ({count / total * 100:.1f}%)", va='center',
                            fontsize=9, color='#52514e')
                ax.set_xlim(0, span * 1.22)
                ax.set_xlabel('Events')
                ax.set_title(f'Event Distribution by Type ({total:,} events)')
                self._style_axes(ax)
                fig.tight_layout()
                self._embed(fig, _report.card(surface, "Events by type"))
            else:
                _bar_list(_report.card(surface, "Events by type"),
                          [(t['label'], t['count']) for t in types])

            _table_block(surface, "Breakdown", ("Type", "Events", "Share"),
                         [(t['label'], f"{t['count']:,}", f"{t['count'] / total * 100:.1f}%")
                          for t in types],
                         {"Type": 320, "Events": 120, "Share": 120})

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_create_distribution", error=str(e)), parent=self.dialog)

    def _create_monthly_trends(self):
        """Create monthly trends line chart"""
        try:
            # Get last 12 months of data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)

            events = self.calendar_manager.get_events_by_date_range(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )

            # Aggregate by month
            monthly_data = {}
            for event in events:
                date_str = event.get('date') or event.get('date_start', '')
                if date_str:
                    month_key = date_str[:7]
                    monthly_data[month_key] = monthly_data.get(month_key, 0) + 1

            self._clear_viz_area()

            if self.matplotlib_available and monthly_data:
                fig = self.Figure(figsize=(8, 5), dpi=100)
                ax = fig.add_subplot(111)

                months = sorted(monthly_data.keys())
                counts = [monthly_data[m] for m in months]

                ax.plot(months, counts, marker='o', linewidth=2, markersize=8, color='#2196F3')
                ax.fill_between(months, counts, alpha=0.3, color='#2196F3')
                ax.set_xlabel('Month')
                ax.set_ylabel('Event Count')
                ax.set_title('Monthly Event Trends (Last 12 Months)')
                ax.tick_params(axis='x', rotation=45)

                fig.tight_layout()

                canvas = self.FigureCanvasTkAgg(fig, master=self.viz_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            else:
                # Text-based visualization
                text_widget = scrolledtext.ScrolledText(self.viz_frame, wrap=tk.WORD, font=('Consolas', 10))
                text_widget.pack(fill=tk.BOTH, expand=True)

                report = "MONTHLY EVENT TRENDS\n" + "="*50 + "\n\n"
                max_count = max(monthly_data.values()) if monthly_data else 1

                for month in sorted(monthly_data.keys()):
                    count = monthly_data[month]
                    bar_len = int((count / max_count) * 40)
                    bar = "*" * bar_len
                    report += f"{month}: {bar} ({count})\n"

                text_widget.insert(tk.END, report)
                text_widget.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_create_trends", error=str(e)), parent=self.dialog)

    def _create_timeline(self):
        """Create timeline visualization"""
        try:
            # Get academic years and semesters
            years = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM academic_years ORDER BY start_date DESC LIMIT 5"
            )

            self._clear_viz_area()

            if self.matplotlib_available and years:
                fig = self.Figure(figsize=(8, 5), dpi=100)
                ax = fig.add_subplot(111)

                for i, year in enumerate(years):
                    try:
                        start = datetime.strptime(year['start_date'], '%Y-%m-%d')
                        end = datetime.strptime(year['end_date'], '%Y-%m-%d')
                        ax.barh(i, (end - start).days, left=start.toordinal(), height=0.5,
                               label=year['id'], color=self.plt.cm.Set2(i/len(years)))
                        ax.text(start.toordinal() + (end - start).days/2, i, year['id'],
                               ha='center', va='center', fontsize=9)
                    except (ValueError, TypeError, KeyError) as e:
                        gui_logger.warning(f"Failed to render academic year timeline entry: {e}")
                        continue

                ax.set_xlabel('Date')
                ax.set_ylabel('Academic Years')
                ax.set_title('Academic Year Timeline')
                ax.set_yticks([])

                fig.tight_layout()

                canvas = self.FigureCanvasTkAgg(fig, master=self.viz_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            else:
                # Text-based visualization
                text_widget = scrolledtext.ScrolledText(self.viz_frame, wrap=tk.WORD, font=('Consolas', 10))
                text_widget.pack(fill=tk.BOTH, expand=True)

                report = "ACADEMIC YEAR TIMELINE\n" + "="*50 + "\n\n"

                for year in years:
                    report += f"{year['id']}\n"
                    report += f"  Start: {year['start_date']}\n"
                    report += f"  End:   {year['end_date']}\n"
                    report += f"  |{'='*40}|\n\n"

                text_widget.insert(tk.END, report)
                text_widget.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_create_timeline", error=str(e)), parent=self.dialog)

    def _create_utilization(self):
        """Resource utilisation across every booking table, plus event locations."""
        try:
            report = self.calendar_manager.advanced_reporting.generate_utilization_report()
            if not report.get('success'):
                raise RuntimeError(report.get('error') or "the utilisation report failed")
            resources = report.get('resources', [])
            locations = self.calendar_manager.db_manager.execute_query(
                "SELECT COALESCE(NULLIF(TRIM(location), ''), 'No location') AS location, "
                f"COUNT(*) AS count FROM {_CALENDAR_EVENTS} GROUP BY 1 ORDER BY 2 DESC"
            )

            self._clear_viz_area()
            surface = _report.scrollable(self.viz_frame)
            total_bookings = sum(r['total_bookings'] for r in resources)
            total_hours = sum(r['total_hours'] for r in resources)
            _report.stat_strip(surface, [
                (len(resources), "Booked resources"),
                (f"{total_bookings:,}", "Confirmed bookings"),
                (f"{total_hours:,.1f}", "Hours booked"),
            ])

            if resources:
                if self.matplotlib_available:
                    ordered = list(reversed(resources))   # busiest at the top
                    names = [f"{r['resource_name']} ({r['resource_type']})" for r in ordered]
                    hours = [r['total_hours'] for r in ordered]
                    fig = self.Figure(figsize=(9, max(3, 0.45 * len(ordered) + 1.4)), dpi=100)
                    ax = fig.add_subplot(111)
                    bars = ax.barh(names, hours, color='#16a34a', height=0.6)
                    span = max(hours) or 1
                    for bar, r in zip(bars, ordered):
                        plural = 's' if r['total_bookings'] != 1 else ''
                        ax.text(bar.get_width() + span * 0.01, bar.get_y() + bar.get_height() / 2,
                                f"{r['total_bookings']} booking{plural} · {r['total_hours']:g} h",
                                va='center', fontsize=9, color='#52514e')
                    ax.set_xlim(0, span * 1.4)
                    ax.set_xlabel('Hours booked (confirmed bookings)')
                    ax.set_title('Resource Utilisation')
                    self._style_axes(ax)
                    fig.tight_layout()
                    self._embed(fig, _report.card(surface, "Hours booked by resource"))
                else:
                    _bar_list(_report.card(surface, "Bookings by resource"),
                              [(r['resource_name'], r['total_bookings']) for r in resources],
                              colour=_report.OK)
                _table_block(surface, "All booked resources",
                             ("Resource", "Type", "Bookings", "Hours", "Avg hours", "Share of a working year"),
                             [(r['resource_name'], r['resource_type'], r['total_bookings'],
                               f"{r['total_hours']:g}", f"{r['avg_duration']:g}",
                               f"{r['utilization_percentage']:.2f}%") for r in resources],
                             {"Resource": 300, "Type": 110, "Bookings": 90, "Hours": 90,
                              "Avg hours": 90, "Share of a working year": 170})
            else:
                body = _report.card(surface, "Bookings", accent=_report.MUTED)
                tk.Label(body, text=("No confirmed bookings in resource_bookings, room_bookings "
                                     "or facility_bookings."),
                         font=(_report.FONT, 9), bg=_report.CARD, fg=_report.MUTED).pack(anchor="w")

            _table_block(surface, "Where calendar events take place", ("Location", "Events"),
                         [(r['location'], f"{r['count']:,}") for r in locations],
                         {"Location": 420, "Events": 120})

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_create_utilization", error=str(e)), parent=self.dialog)

    def _create_attendance(self):
        """Attendance for every course in the database."""
        try:
            report = self.calendar_manager.advanced_reporting.attendance_by_course()
            if not report.get('success'):
                raise RuntimeError(report.get('error') or "the attendance report failed")
            courses = report.get('courses', [])

            self._clear_viz_area()
            surface = _report.scrollable(self.viz_frame)
            marks = sum(c['marks'] for c in courses)
            attended = sum(c['attended'] for c in courses)
            _report.stat_strip(surface, [
                (len(courses), "Courses"),
                (sum(1 for c in courses if c['marks']), "With attendance recorded"),
                (f"{marks:,}", "Attendance marks"),
                (f"{attended / marks * 100:.1f}%" if marks else "—", "Overall attendance"),
            ])

            if courses and self.matplotlib_available:
                ordered = list(reversed(courses))   # first course code at the top
                labels = [c['course_code'] for c in ordered]
                values = [c['marks'] for c in ordered]
                fig = self.Figure(figsize=(9, max(4, 0.32 * len(ordered) + 1.4)), dpi=100)
                ax = fig.add_subplot(111)
                bars = ax.barh(labels, values, color='#9C27B0', height=0.6)
                span = max(values) or 1
                for bar, c in zip(bars, ordered):
                    if c['marks']:
                        text, colour = f"{c['attended']}/{c['marks']} present · {c['attendance_rate']:g}%", '#52514e'
                    else:
                        text, colour = "no attendance recorded", '#9ca3af'
                    ax.text(bar.get_width() + span * 0.01, bar.get_y() + bar.get_height() / 2,
                            text, va='center', fontsize=8, color=colour)
                ax.set_xlim(0, span * 1.6)
                ax.set_xlabel('Attendance marks recorded')
                ax.set_title('Attendance by Course')
                self._style_axes(ax)
                fig.tight_layout()
                self._embed(fig, _report.card(surface, "Attendance marks by course"))
            elif courses:
                _bar_list(_report.card(surface, "Attendance marks by course"),
                          [(f"{c['course_code']} — {c['course_name']}", c['marks']) for c in courses],
                          colour='#9C27B0')

            _table_block(surface, "Every course",
                         ("Course", "Name", "Sessions", "Marks", "Present", "Attendance", "Calendar events"),
                         [(c['course_code'], c['course_name'], c['sessions'], c['marks'], c['attended'],
                           f"{c['attendance_rate']:g}%" if c['attendance_rate'] is not None else "—",
                           c['linked_events']) for c in courses],
                         {"Course": 90, "Name": 300, "Sessions": 90, "Marks": 80, "Present": 80,
                          "Attendance": 100, "Calendar events": 120})

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_create_attendance", error=str(e)), parent=self.dialog)

    def _center_dialog(self):
        """Center dialog on parent"""
        _center(self.dialog)


class ProjectMilestonesDialog:
    """Dialog for managing project milestones"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.milestones.title"))
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_milestones()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.milestones.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(action_frame, text=_("academic_calendar.buttons.add_milestone"),
                  command=self._add_milestone).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_("academic_calendar.buttons.update_progress"),
                  command=self._update_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_("academic_calendar.buttons.refresh"),
                  command=self._load_milestones).pack(side=tk.RIGHT, padx=5)

        # Milestones tree
        self.milestones_tree = ttk.Treeview(main_frame,
                                          columns=('Project', 'Due Date', 'Progress', 'Status'),
                                          show='tree headings')
        self.milestones_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Configure columns
        self.milestones_tree.heading('#0', text=_("academic_calendar.columns.name"))
        self.milestones_tree.heading('Project', text=_("academic_calendar.columns.project"))
        self.milestones_tree.heading('Due Date', text=_("academic_calendar.columns.due_date"))
        self.milestones_tree.heading('Progress', text=_("academic_calendar.columns.progress"))
        self.milestones_tree.heading('Status', text=_("academic_calendar.columns.status"))

        self.milestones_tree.column('#0', width=200)
        self.milestones_tree.column('Project', width=150)
        self.milestones_tree.column('Due Date', width=100)
        self.milestones_tree.column('Progress', width=100)
        self.milestones_tree.column('Status', width=100)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.milestones_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.milestones_tree.xview)

        self.milestones_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(15, 0))

    def _load_milestones(self):
        """Load milestones into tree"""
        try:
            # Clear existing items
            for item in self.milestones_tree.get_children():
                self.milestones_tree.delete(item)

            # Get milestones from database
            milestones = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM project_milestones ORDER BY due_date"
            )

            for milestone in milestones:
                # Convert sqlite3.Row to dict if necessary
                if hasattr(milestone, '__getitem__') and not hasattr(milestone, 'get'):
                    milestone = dict(milestone)

                progress = f"{milestone.get('completion_percentage', 0):.1f}%"

                # Color code by status
                status = milestone.get('status', 'pending')
                tag = status.lower()

                self.milestones_tree.insert('', 'end',
                                          text=milestone['milestone_name'],
                                          values=(milestone['project_name'],
                                                milestone['due_date'],
                                                progress,
                                                status.title()),
                                          tags=(tag,))

            # Configure status colors
            self.milestones_tree.tag_configure('completed', foreground='green')
            self.milestones_tree.tag_configure('in_progress', foreground='blue')
            self.milestones_tree.tag_configure('overdue', foreground='red')
            self.milestones_tree.tag_configure('pending', foreground='orange')

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_load_milestones", error=str(e)))

    def _add_milestone(self):
        """Add new milestone"""
        AddMilestoneDialog(self.dialog, self.calendar_manager, self._load_milestones)

    def _update_progress(self):
        """Update milestone progress"""
        selection = self.milestones_tree.selection()
        if selection:
            milestone_name = self.milestones_tree.item(selection[0], 'text')
            UpdateMilestoneDialog(self.dialog, self.calendar_manager, milestone_name, self._load_milestones)
        else:
            messagebox.showwarning(_("academic_calendar.messages.selection_required"), _("academic_calendar.messages.select_milestone_to_update"))

    def _center_dialog(self):
        """Center dialog on parent"""
        _center(self.dialog)


class AddMilestoneDialog:
    """Simple dialog for adding milestones"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        # Create and show simple input dialog
        project_name = simpledialog.askstring(_("academic_calendar.messages.add_milestone_dialog.title"), _("academic_calendar.messages.add_milestone_dialog.project_name"))
        if not project_name:
            return

        milestone_name = simpledialog.askstring(_("academic_calendar.messages.add_milestone_dialog.title"), _("academic_calendar.messages.add_milestone_dialog.milestone_name"))
        if not milestone_name:
            return

        due_date = simpledialog.askstring(_("academic_calendar.messages.add_milestone_dialog.title"), _("academic_calendar.messages.add_milestone_dialog.due_date"))
        if not due_date:
            return

        description = simpledialog.askstring(_("academic_calendar.messages.add_milestone_dialog.title"), _("academic_calendar.messages.add_milestone_dialog.description")) or ""

        try:
            success, message = calendar_manager.academic_deadlines.create_project_milestone(
                project_name, milestone_name, due_date, description=description
            )

            if success:
                messagebox.showinfo(_("common.success"), message)
                if callback:
                    callback()
            else:
                messagebox.showerror(_("common.error"), message)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_add_milestone", error=str(e)))


class UpdateMilestoneDialog:
    """Simple dialog for updating milestone progress"""

    def __init__(self, parent, calendar_manager, milestone_name, callback=None):
        try:
            # Get milestone ID by name
            milestones = calendar_manager.db_manager.execute_query(
                "SELECT id FROM project_milestones WHERE milestone_name = ?", (milestone_name,)
            )

            if not milestones:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.milestone_not_found"))
                return

            milestone_id = milestones[0]['id']

            # Ask for progress
            progress = simpledialog.askfloat(_("academic_calendar.messages.update_milestone_dialog.title"),
                                           _("academic_calendar.messages.update_milestone_dialog.enter_percentage"),
                                           minvalue=0, maxvalue=100)
            if progress is not None:
                success, message = calendar_manager.academic_deadlines.update_milestone_progress(
                    milestone_id, progress
                )

                if success:
                    messagebox.showinfo(_("common.success"), message)
                    if callback:
                        callback()
                else:
                    messagebox.showerror(_("common.error"), message)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_update_milestone", error=str(e)))


