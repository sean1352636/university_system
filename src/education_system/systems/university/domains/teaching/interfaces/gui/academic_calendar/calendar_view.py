"""Calendar view for the University academic calendar GUI.

Two presentations of the same data:

* **Month** — a proper month grid with colour-coded event chips. The
  default, and what people mean by "the calendar".
* **List** — the semester-grouped tree this view used to be, kept
  because it is the only sensible way to read a whole year at once.

The Treeview is the *selection model* for both. ``events_view`` resolves
edit, delete, details and email-reminder actions from
``self.calendar_tree.selection()``, so the tree is always built and
always populated — in month mode it is simply not packed. Clicking a
chip selects the matching tree row, which means every existing action
keeps working without knowing the grid exists. Do not "optimise away"
the hidden tree; those five call sites in ``events_view`` depend on it.

Styling is deliberately plain ``tk`` rather than ``ttk`` for the grid
cells: per-cell background colour is the whole point here, and ttk
styles are process-global and theme-dependent, so a themed widget would
fight the palette on some platforms and silently ignore it on others.
"""

import calendar as _calendar
import logging
import tkinter as tk
from tkinter import ttk, font as tkfont
from datetime import date, datetime, timedelta
from typing import Any, Optional, List, Dict

from education_system.systems.university.infrastructure.i18n import get_text as _
# Message boxes parented to the window that raised them, not the main
# GUI — see _dialogs.
from education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar._dialogs import messagebox

gui_logger = logging.getLogger(__name__)


# Import dialog - use lazy import to avoid circular dependency
def _get_add_event_dialog():
    from education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar.dialogs_event import AddEventDialog
    return AddEventDialog


# ── Palette ─────────────────────────────────────────────────────────
# Tied to the accent already used in main_gui._configure_styles
# (#2E86C1 accent, #34495E sidebar) so the calendar reads as part of the
# same application rather than a bolted-on widget.

SURFACE = '#FFFFFF'          # day cell
SURFACE_MUTED = '#F7F9FA'    # weekend
SURFACE_OUTSIDE = '#EDF0F2'  # day belonging to the previous/next month
PAGE_BG = '#F0F0F0'          # matches main_gui bg_color
GRIDLINE = '#D8DFE5'
HEADER_BG = '#34495E'        # matches the sidebar
HEADER_FG = '#FFFFFF'
TEXT = '#2C3E50'
TEXT_MUTED = '#95A5A6'
TEXT_OUTSIDE = '#B6BFC6'
ACCENT = '#2E86C1'
TODAY_BG = '#EAF4FB'

#: Chip colour per event type. Keys match the ``event_type`` values the
#: manager returns; anything unrecognised falls back to DEFAULT_TYPE.
TYPE_COLOURS: Dict[str, str] = {
    'Academic':       '#2E86C1',
    'Holiday':        '#27AE60',
    'Administrative': '#7F8C8D',
    'Trip':           '#8E44AD',
    'Deadline':       '#E74C3C',
    'Social':         '#E67E22',
    'Sports':         '#16A085',
}
DEFAULT_TYPE_COLOUR = '#34495E'

TYPE_ICONS: Dict[str, str] = {
    'Academic': '📚',
    'Holiday': '🎉',
    'Administrative': '📋',
    'Trip': '🎒',
    'Deadline': '⏰',
    'Social': '🎊',
    'Sports': '⚽',
}
DEFAULT_ICON = '📅'

#: Chips drawn in a cell before collapsing the rest into "+N more".
#: Four fits the cell height at the default 1400x900 window; beyond that
#: the chips shrink to unreadable slivers.
MAX_CHIPS_PER_DAY = 4


def _type_colour(event_type: Optional[str]) -> str:
    return TYPE_COLOURS.get((event_type or '').strip(), DEFAULT_TYPE_COLOUR)


def _type_icon(event_type: Optional[str]) -> str:
    return TYPE_ICONS.get((event_type or '').strip(), DEFAULT_ICON)


def _parse_date(value: Any) -> Optional[date]:
    """Best-effort date out of whatever the manager returned.

    ``view_calendar`` selects ``event_date`` as ``date`` but
    ``start_datetime``/``end_datetime`` as ``date_start``/``date_end``,
    so the same result set mixes plain dates and timestamps, in either
    ``T`` or space-separated form. Returns None for anything unreadable
    rather than raising — one malformed row must not blank the month.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(text[:len(fmt) + 6].strip(), fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        gui_logger.debug("Unparseable calendar date: %r", value)
        return None


def _fmt(key: str, default: str, **kwargs) -> str:
    """Translate *and* substitute, including when the key is missing.

    ``i18n.t`` applies ``str.format`` only to a value it actually found
    in a locale file — the ``default`` fallback is returned verbatim. So
    ``t("missing.key", "+{n} more", n=3)`` yields the literal
    ``"+{n} more"``. This formats whichever string came back, and falls
    back to the raw template if the locale entry uses different
    placeholder names than the call site.
    """
    template = _(key, default)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        gui_logger.debug("Locale key %s has placeholders that do not match "
                         "%r; showing it unsubstituted", key, sorted(kwargs))
        return template


def _ui_font(size: int, weight: str = 'normal') -> tuple:
    """A font tuple that exists on this platform.

    Tk silently substitutes an unknown family, which on some systems
    yields a serif face that looks nothing like the rest of the GUI, so
    pick from what is actually installed.
    """
    try:
        families = set(tkfont.families())
    except Exception:
        families = set()
    for name in ('Segoe UI', 'Helvetica Neue', 'DejaVu Sans', 'Arial',
                 'Helvetica'):
        if name in families:
            return (name, size, weight)
    return ('TkDefaultFont', size, weight)


class CalendarViewMixin:

    # ── Entry point ─────────────────────────────────────────────────

    def _show_calendar_view(self):
        """Show calendar view"""
        self._clear_content_area()
        self.current_view = "calendar"

        if not hasattr(self, '_calendar_mode'):
            self._calendar_mode = 'month'
        if not hasattr(self, '_calendar_cursor'):
            self._calendar_cursor = date.today().replace(day=1)
        # Set once per view build: the first data load may retarget the
        # month at whatever the data actually covers (see _load_calendar_data).
        self._calendar_month_pinned = False

        outer = tk.Frame(self.content_area, bg=PAGE_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        self._build_calendar_toolbar(outer)
        self._build_calendar_legend(outer)

        # Body holds whichever presentation is active. Both are built;
        # only one is packed.
        self._calendar_body = tk.Frame(outer, bg=PAGE_BG)
        self._calendar_body.pack(fill=tk.BOTH, expand=True,
                                 padx=16, pady=(4, 12))

        self._calendar_grid_host = tk.Frame(self._calendar_body, bg=PAGE_BG)
        self._calendar_list_host = tk.Frame(self._calendar_body, bg=PAGE_BG)

        # The tree is the selection model for both modes — always built.
        self._create_calendar_treeview(self._calendar_list_host)

        self._apply_calendar_mode()
        self._load_calendar_data()

    # ── Toolbar ─────────────────────────────────────────────────────

    def _build_calendar_toolbar(self, parent):
        """Title, month navigation, filters and the Month/List toggle."""
        bar = tk.Frame(parent, bg=PAGE_BG)
        bar.pack(fill=tk.X, padx=16, pady=(14, 6))

        left = tk.Frame(bar, bg=PAGE_BG)
        left.pack(side=tk.LEFT)

        tk.Label(left, text=_("academic_calendar.calendar_view.title"),
                 font=_ui_font(17, 'bold'), bg=PAGE_BG, fg=TEXT
                 ).pack(side=tk.LEFT, padx=(0, 16))

        nav = tk.Frame(left, bg=PAGE_BG)
        nav.pack(side=tk.LEFT)

        def nav_button(text, command, width=3):
            b = tk.Button(nav, text=text, command=command, width=width,
                          font=_ui_font(10, 'bold'), bg=SURFACE, fg=TEXT,
                          activebackground=TODAY_BG, relief=tk.FLAT,
                          bd=0, highlightthickness=1,
                          highlightbackground=GRIDLINE, cursor='hand2')
            b.pack(side=tk.LEFT, padx=2)
            return b

        nav_button('‹', lambda: self._shift_calendar_month(-1))
        self._calendar_today_btn = nav_button(
            _("academic_calendar.buttons.today", "Today"),
            self._goto_calendar_today, width=7)
        nav_button('›', lambda: self._shift_calendar_month(1))

        self._calendar_month_label = tk.Label(
            left, text='', font=_ui_font(14, 'bold'), bg=PAGE_BG, fg=ACCENT)
        self._calendar_month_label.pack(side=tk.LEFT, padx=14)

        right = tk.Frame(bar, bg=PAGE_BG)
        right.pack(side=tk.RIGHT)

        # Mode toggle. Kept as two buttons rather than a Combobox so the
        # active mode is visible without opening anything.
        toggle = tk.Frame(right, bg=GRIDLINE)
        toggle.pack(side=tk.RIGHT, padx=(12, 0))
        self._calendar_mode_buttons = {}
        for mode, label in (
            ('month', _("academic_calendar.buttons.month_view", "Month")),
            ('list', _("academic_calendar.buttons.list_view", "List")),
        ):
            b = tk.Button(toggle, text=label, width=7, relief=tk.FLAT, bd=0,
                          font=_ui_font(9, 'bold'), cursor='hand2',
                          command=lambda m=mode: self._set_calendar_mode(m))
            b.pack(side=tk.LEFT, padx=1, pady=1)
            self._calendar_mode_buttons[mode] = b

        filters = tk.Frame(right, bg=PAGE_BG)
        filters.pack(side=tk.RIGHT)

        tk.Label(filters, text=_("academic_calendar.labels.academic_year"),
                 bg=PAGE_BG, fg=TEXT_MUTED, font=_ui_font(9)
                 ).pack(side=tk.LEFT, padx=(0, 5))
        self.year_var = tk.StringVar()
        ttk.Combobox(filters, textvariable=self.year_var, width=13
                     ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(filters, text=_("academic_calendar.labels.semester"),
                 bg=PAGE_BG, fg=TEXT_MUTED, font=_ui_font(9)
                 ).pack(side=tk.LEFT, padx=(0, 5))
        self.semester_var = tk.StringVar()
        ttk.Combobox(filters, textvariable=self.semester_var, width=13
                     ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(filters, text=_("academic_calendar.buttons.view"),
                   command=self._load_calendar_data).pack(side=tk.LEFT)

    def _build_calendar_legend(self, parent):
        """A colour key. Without it the chips are decoration, not data."""
        self._calendar_legend = tk.Frame(parent, bg=PAGE_BG)
        self._calendar_legend.pack(fill=tk.X, padx=16, pady=(0, 2))

    def _refresh_calendar_legend(self, types_present):
        """Show only the types actually on screen, so the key stays short."""
        legend = getattr(self, '_calendar_legend', None)
        if legend is None or not legend.winfo_exists():
            return
        for child in legend.winfo_children():
            child.destroy()
        if not types_present:
            return
        tk.Label(legend, text=_("academic_calendar.labels.key", "Key:"),
                 bg=PAGE_BG, fg=TEXT_MUTED, font=_ui_font(9)
                 ).pack(side=tk.LEFT, padx=(0, 8))
        for event_type in sorted(types_present):
            item = tk.Frame(legend, bg=PAGE_BG)
            item.pack(side=tk.LEFT, padx=(0, 12))
            tk.Frame(item, bg=_type_colour(event_type), width=11, height=11
                     ).pack(side=tk.LEFT, padx=(0, 5))
            tk.Label(item, text=event_type or _("academic_calendar.labels.other", "Other"),
                     bg=PAGE_BG, fg=TEXT_MUTED, font=_ui_font(9)
                     ).pack(side=tk.LEFT)

    # ── Mode switching ──────────────────────────────────────────────

    def _set_calendar_mode(self, mode):
        if mode not in ('month', 'list'):
            return
        self._calendar_mode = mode
        self._apply_calendar_mode()
        if mode == 'month':
            self._render_month_grid()

    def _apply_calendar_mode(self):
        """Pack the active presentation and style the toggle to match."""
        mode = getattr(self, '_calendar_mode', 'month')
        for host in (getattr(self, '_calendar_grid_host', None),
                     getattr(self, '_calendar_list_host', None)):
            if host is not None and host.winfo_exists():
                host.pack_forget()
        host = (self._calendar_grid_host if mode == 'month'
                else self._calendar_list_host)
        if host is not None and host.winfo_exists():
            host.pack(fill=tk.BOTH, expand=True)

        for name, button in getattr(self, '_calendar_mode_buttons', {}).items():
            if not button.winfo_exists():
                continue
            active = (name == mode)
            button.configure(
                bg=ACCENT if active else SURFACE,
                fg='white' if active else TEXT,
                activebackground=ACCENT if active else TODAY_BG,
                activeforeground='white' if active else TEXT,
            )

        for widget in (getattr(self, '_calendar_month_label', None),
                       getattr(self, '_calendar_today_btn', None)):
            if widget is not None and widget.winfo_exists():
                # Month navigation is meaningless in list mode.
                try:
                    widget.configure(
                        state=tk.NORMAL if mode == 'month' else tk.DISABLED)
                except tk.TclError:
                    pass

    def _shift_calendar_month(self, delta):
        cursor = getattr(self, '_calendar_cursor', date.today().replace(day=1))
        month = cursor.month - 1 + delta
        year = cursor.year + month // 12
        self._calendar_cursor = date(year, month % 12 + 1, 1)
        self._calendar_month_pinned = True
        self._render_month_grid()

    def _goto_calendar_today(self):
        self._calendar_cursor = date.today().replace(day=1)
        self._calendar_month_pinned = True
        self._render_month_grid()

    # ── The list presentation (unchanged behaviour) ─────────────────

    def _create_calendar_treeview(self, parent):
        """Create treeview for calendar display"""
        wrapper = tk.Frame(parent, bg=SURFACE, highlightthickness=1,
                           highlightbackground=GRIDLINE)
        wrapper.pack(fill=tk.BOTH, expand=True)

        self.calendar_tree = ttk.Treeview(
            wrapper,
            columns=('Date', 'End Date', 'Type', 'Description'),
            show='tree headings')

        self.calendar_tree.heading('#0', text=_("academic_calendar.columns.event_name"))
        self.calendar_tree.heading('Date', text=_("academic_calendar.columns.start_date"))
        self.calendar_tree.heading('End Date', text=_("academic_calendar.columns.end_date"))
        self.calendar_tree.heading('Type', text=_("academic_calendar.columns.type"))
        self.calendar_tree.heading('Description', text=_("academic_calendar.columns.description"))

        self.calendar_tree.column('#0', width=250)
        self.calendar_tree.column('Date', width=120)
        self.calendar_tree.column('End Date', width=120)
        self.calendar_tree.column('Type', width=120)
        self.calendar_tree.column('Description', width=300)

        v_scrollbar = ttk.Scrollbar(wrapper, orient=tk.VERTICAL,
                                    command=self.calendar_tree.yview)
        h_scrollbar = ttk.Scrollbar(wrapper, orient=tk.HORIZONTAL,
                                    command=self.calendar_tree.xview)
        self.calendar_tree.configure(yscrollcommand=v_scrollbar.set,
                                     xscrollcommand=h_scrollbar.set)

        # Scrollbars before the tree, so the tree does not claim the
        # space they need when the window is small.
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.calendar_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Zebra striping — a flat white tree of thirty rows is exactly
        # the "plain text" this view is trying to stop being.
        self.calendar_tree.tag_configure('semester', font=_ui_font(10, 'bold'))
        self.calendar_tree.tag_configure('odd', background='#F7F9FA')
        self.calendar_tree.tag_configure('even', background=SURFACE)

        self._create_calendar_context_menu()

    def _create_calendar_context_menu(self):
        """Create context menu for calendar items"""
        self.calendar_context_menu = tk.Menu(self.root, tearoff=0)
        self.calendar_context_menu.add_command(label=_("academic_calendar.context_menu.edit_event"), command=self._edit_selected_event)
        self.calendar_context_menu.add_command(label=_("academic_calendar.context_menu.delete_event"), command=self._delete_selected_event)
        self.calendar_context_menu.add_separator()
        self.calendar_context_menu.add_command(label=_("academic_calendar.context_menu.view_details"), command=self._view_event_details)
        self.calendar_context_menu.add_separator()
        self.calendar_context_menu.add_command(label=_("academic_calendar.context_menu.send_email_reminder"), command=self._send_email_reminder)

        def show_context_menu(event):
            try:
                self.calendar_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.calendar_context_menu.grab_release()

        self.calendar_tree.bind("<Button-3>", show_context_menu)  # Right click

    # ── Loading ─────────────────────────────────────────────────────

    def _load_calendar_data(self):
        """Load calendar data into the tree and redraw the month grid."""
        try:
            if not self.calendar_manager:
                return

            tree = getattr(self, 'calendar_tree', None)
            if tree is None or not tree.winfo_exists():
                return
            for item in tree.get_children():
                tree.delete(item)
            self._calendar_events = []

            academic_year = self.year_var.get() if hasattr(self, 'year_var') else None
            semester = self.semester_var.get() if hasattr(self, 'semester_var') else None
            academic_year = academic_year if academic_year and academic_year != '' else None
            semester = semester if semester and semester != '' else None

            success, data = self.calendar_manager.view_calendar(academic_year, semester)

            if success and data:
                semester_groups: Dict[str, list] = {}
                for item in data:
                    semester_name = item.get('semester_name', 'Unknown')
                    if semester_name not in semester_groups:
                        semester_groups[semester_name] = []
                    if item.get('event_name'):  # Only add items with events
                        semester_groups[semester_name].append(item)

                row = 0
                for semester_name, events in semester_groups.items():
                    if not events:
                        continue
                    semester_node = tree.insert(
                        '', 'end', text=f"📖 {semester_name}",
                        values=('', '', _("academic_calendar.labels.semester"), ''),
                        open=True, tags=('semester',))

                    for event in events:
                        event_date = event.get('date') or event.get('date_start', '')
                        end_date = event.get('date_end', '')
                        event_type = event.get('event_type', '')
                        description = (event.get('description') or '')[:100]
                        icon = _type_icon(event_type)

                        row += 1
                        iid = tree.insert(
                            semester_node, 'end',
                            text=f"{icon} {event['event_name']}",
                            values=(event_date, end_date, event_type, description),
                            tags=('odd' if row % 2 else 'even',))

                        start = _parse_date(event_date)
                        end = _parse_date(end_date) or start
                        if start is not None:
                            if end is not None and end < start:
                                # Backwards range: trust the start and
                                # render a single day rather than nothing.
                                end = start
                            self._calendar_events.append({
                                'iid': iid,
                                'name': event.get('event_name', ''),
                                'type': event_type,
                                'start': start,
                                'end': end or start,
                                'description': event.get('description') or '',
                                'semester': semester_name,
                                'raw_start': event_date,
                            })

                self._update_status(
                    _("academic_calendar.messages.loaded_calendar_items").format(count=len(data)),
                    "success")
            else:
                self._update_status(_("academic_calendar.messages.no_calendar_data"), "warning")

            # Land on a month that actually has something in it, unless
            # the user has already navigated somewhere deliberately.
            if self._calendar_events and not getattr(
                    self, '_calendar_month_pinned', False):
                cursor = getattr(self, '_calendar_cursor',
                                 date.today().replace(day=1))
                in_view = any(e['start'].year == cursor.year
                              and e['start'].month == cursor.month
                              for e in self._calendar_events)
                if not in_view:
                    first = min(e['start'] for e in self._calendar_events)
                    self._calendar_cursor = first.replace(day=1)
                self._calendar_month_pinned = True

            self._render_month_grid()

        except Exception as e:
            gui_logger.error(f"Failed to load calendar data: {e}")
            self._show_error(_("academic_calendar.messages.failed_to_load_events").format(error=e))

    # ── The month grid ──────────────────────────────────────────────

    def _render_month_grid(self):
        host = getattr(self, '_calendar_grid_host', None)
        if host is None or not host.winfo_exists():
            return
        for child in host.winfo_children():
            child.destroy()

        cursor = getattr(self, '_calendar_cursor', date.today().replace(day=1))
        events = getattr(self, '_calendar_events', [])

        label = getattr(self, '_calendar_month_label', None)
        if label is not None and label.winfo_exists():
            label.configure(text=f"{_calendar.month_name[cursor.month]} {cursor.year}")

        by_day = self._events_by_day(events, cursor)
        self._refresh_calendar_legend(
            {e['type'] for e in events
             if cursor.replace(day=1) <= e['end']
             and e['start'] <= self._month_end(cursor)})

        frame = tk.Frame(host, bg=GRIDLINE, highlightthickness=1,
                         highlightbackground=GRIDLINE)
        frame.pack(fill=tk.BOTH, expand=True)

        # Monday-first, matching the UK academic week.
        cal = _calendar.Calendar(firstweekday=0)
        weeks = cal.monthdatescalendar(cursor.year, cursor.month)

        for col, day_name in enumerate(_calendar.day_abbr):
            tk.Label(frame, text=day_name, bg=HEADER_BG, fg=HEADER_FG,
                     font=_ui_font(9, 'bold'), pady=6
                     ).grid(row=0, column=col, sticky='nsew', padx=(0, 1),
                            pady=(0, 1))
            frame.grid_columnconfigure(col, weight=1, uniform='day')

        today = date.today()
        for r, week in enumerate(weeks, start=1):
            frame.grid_rowconfigure(r, weight=1, uniform='week')
            for c, day in enumerate(week):
                self._build_day_cell(frame, r, c, day, cursor, today,
                                     by_day.get(day, []))

    @staticmethod
    def _month_end(cursor):
        last = _calendar.monthrange(cursor.year, cursor.month)[1]
        return date(cursor.year, cursor.month, last)

    def _events_by_day(self, events, cursor):
        """Expand each event across the days it covers.

        A multi-day event appears in every cell it spans, so a reading
        week looks like a reading week rather than a single Monday chip.
        The span is clamped to the visible grid, which includes the
        trailing days of the previous month and the leading days of the
        next.
        """
        by_day: Dict[date, list] = {}
        for event in events:
            start, end = event['start'], event['end']
            # Guard against a bad range producing a million iterations.
            span = (end - start).days
            if span < 0:
                span = 0
            elif span > 366:
                span = 366
                end = start + timedelta(days=366)
            day = start
            while day <= end:
                by_day.setdefault(day, []).append(
                    {**event, 'is_continuation': day != start,
                     'is_last': day == end})
                day += timedelta(days=1)
        for day in by_day:
            by_day[day].sort(key=lambda e: (e['is_continuation'],
                                            e['start'], e['name']))
        return by_day

    def _build_day_cell(self, parent, row, col, day, cursor, today, day_events):
        outside = day.month != cursor.month
        is_today = (day == today)
        weekend = day.weekday() >= 5

        if outside:
            bg = SURFACE_OUTSIDE
        elif is_today:
            bg = TODAY_BG
        elif weekend:
            bg = SURFACE_MUTED
        else:
            bg = SURFACE

        cell = tk.Frame(parent, bg=bg,
                        highlightthickness=2 if is_today else 0,
                        highlightbackground=ACCENT,
                        highlightcolor=ACCENT)
        cell.grid(row=row, column=col, sticky='nsew', padx=(0, 1), pady=(0, 1))
        cell.grid_propagate(False)

        head = tk.Frame(cell, bg=bg)
        head.pack(fill=tk.X, padx=4, pady=(3, 0))

        number = tk.Label(
            head, text=str(day.day), bg=ACCENT if is_today else bg,
            fg='white' if is_today else (TEXT_OUTSIDE if outside else TEXT),
            font=_ui_font(9, 'bold' if is_today or not outside else 'normal'),
            padx=5 if is_today else 0)
        number.pack(side=tk.LEFT)

        if day_events:
            tk.Label(head, text=str(len(day_events)), bg=bg, fg=TEXT_MUTED,
                     font=_ui_font(8)).pack(side=tk.RIGHT)

        body = tk.Frame(cell, bg=bg)
        body.pack(fill=tk.BOTH, expand=True, padx=3, pady=(2, 3))

        for event in day_events[:MAX_CHIPS_PER_DAY]:
            self._build_event_chip(body, event, dimmed=outside)

        hidden = len(day_events) - MAX_CHIPS_PER_DAY
        if hidden > 0:
            more = tk.Label(
                body,
                text=_fmt("academic_calendar.labels.more_events",
                          "+{n} more", n=hidden),
                bg=bg, fg=ACCENT, font=_ui_font(8, 'bold'), anchor='w',
                cursor='hand2')
            more.pack(fill=tk.X, padx=1)
            more.bind('<Button-1>', lambda _e, d=day: self._show_day_events(d))

        # The day number opens that day; empty space in the cell is a
        # double-click target for adding. Deliberately NOT both on the
        # same widget: a single-click popup bound to the whole cell
        # fires on the first click of a double-click, so the popup
        # appears every time somebody tries to add an event.
        number.configure(cursor='hand2')
        number.bind('<Button-1>', lambda _e, d=day: self._show_day_events(d))
        for widget in (cell, body, head):
            widget.bind('<Double-Button-1>',
                        lambda _e, d=day: self._add_event_on(d))

    def _build_event_chip(self, parent, event, dimmed=False):
        colour = _type_colour(event['type'])
        label = event['name']
        if event.get('is_continuation'):
            label = f"↳ {label}"
        else:
            label = f"{_type_icon(event['type'])} {label}"

        chip = tk.Label(parent, text=label, bg=colour, fg='white',
                        font=_ui_font(8), anchor='w', padx=4, pady=1,
                        cursor='hand2')
        chip.pack(fill=tk.X, pady=1)
        if dimmed:
            # Outside-month chips stay visible but recede, so the eye
            # lands on the current month first.
            chip.configure(bg=SURFACE_OUTSIDE, fg=colour)

        tip = f"{event['name']} — {event['type'] or ''}".strip(' —')
        if event['start'] != event['end']:
            tip += f"\n{event['start']:%d %b} – {event['end']:%d %b %Y}"
        else:
            tip += f"\n{event['start']:%d %b %Y}"
        if event.get('description'):
            tip += f"\n\n{event['description'][:200]}"
        self._bind_chip_tooltip(chip, tip)

        chip.bind('<Button-1>', lambda _e, ev=event: self._select_calendar_event(ev))
        chip.bind('<Double-Button-1>',
                  lambda _e, ev=event: self._open_calendar_event(ev))
        chip.bind('<Button-3>', lambda e, ev=event: self._chip_context_menu(e, ev))

    def _bind_chip_tooltip(self, widget, text):
        """A hover tooltip — the chip itself only has room for a name."""
        state = {'window': None, 'after': None}

        def show():
            state['after'] = None
            if state['window'] is not None or not widget.winfo_exists():
                return
            try:
                top = tk.Toplevel(widget)
                top.wm_overrideredirect(True)
                top.wm_geometry(
                    f"+{widget.winfo_rootx() + 12}+{widget.winfo_rooty() + 24}")
                tk.Label(top, text=text, justify=tk.LEFT, bg='#2C3E50',
                         fg='white', font=_ui_font(8), padx=8, pady=5,
                         wraplength=320).pack()
                state['window'] = top
            except tk.TclError:
                state['window'] = None

        def enter(_event):
            state['after'] = widget.after(450, show)

        def leave(_event):
            if state['after'] is not None:
                try:
                    widget.after_cancel(state['after'])
                except tk.TclError:
                    pass
                state['after'] = None
            if state['window'] is not None:
                try:
                    state['window'].destroy()
                except tk.TclError:
                    pass
                state['window'] = None

        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)
        # A tooltip outlives its chip if the grid is redrawn mid-hover.
        widget.bind('<Destroy>', leave, add='+')

    # ── Chip -> tree selection, so existing actions keep working ────

    def _select_calendar_event(self, event):
        """Select the tree row behind this chip.

        Everything in ``events_view`` reads the selection off
        ``calendar_tree``, so this is the whole integration: select the
        row and every existing action applies to the clicked event.
        """
        tree = getattr(self, 'calendar_tree', None)
        if tree is None or not tree.winfo_exists():
            return False
        iid = event.get('iid')
        if not iid or not tree.exists(iid):
            return False
        try:
            tree.selection_set(iid)
            tree.focus(iid)
            tree.see(iid)
        except tk.TclError:
            return False
        self._update_status(
            f"{event['name']} — {event['start']:%d %b %Y}", "info")
        return True

    def _open_calendar_event(self, event):
        if self._select_calendar_event(event) and hasattr(self, '_view_event_details'):
            self._view_event_details()

    def _chip_context_menu(self, tk_event, event):
        if not self._select_calendar_event(event):
            return
        menu = getattr(self, 'calendar_context_menu', None)
        if menu is None:
            return
        try:
            menu.tk_popup(tk_event.x_root, tk_event.y_root)
        finally:
            menu.grab_release()

    def _add_event_on(self, day):
        """Double-clicking a day starts a new event on that date."""
        self._show_add_event()

    def _show_day_events(self, day):
        """A popup listing everything on one day.

        The cells cap at four chips; this is where the rest live, and
        where a day with one event is still worth opening because the
        chip cannot show the description.
        """
        events = [e for e in getattr(self, '_calendar_events', [])
                  if e['start'] <= day <= e['end']]

        top = tk.Toplevel(self.root)
        top.title(f"{day:%A %d %B %Y}")
        top.configure(bg=PAGE_BG)
        top.transient(self.root)
        top.geometry('420x360')
        top.minsize(340, 240)

        header = tk.Frame(top, bg=ACCENT)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"{day:%A %d %B %Y}", bg=ACCENT, fg='white',
                 font=_ui_font(12, 'bold'), pady=10).pack(padx=14, anchor='w')

        body = tk.Frame(top, bg=PAGE_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        if not events:
            tk.Label(body, text=_("academic_calendar.messages.no_events_on_day",
                                  "Nothing scheduled."),
                     bg=PAGE_BG, fg=TEXT_MUTED, font=_ui_font(10)).pack(pady=20)
        else:
            for event in events:
                card = tk.Frame(body, bg=SURFACE, highlightthickness=1,
                                highlightbackground=GRIDLINE)
                card.pack(fill=tk.X, pady=(0, 8))
                tk.Frame(card, bg=_type_colour(event['type']), width=4
                         ).pack(side=tk.LEFT, fill=tk.Y)
                inner = tk.Frame(card, bg=SURFACE)
                inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                           padx=10, pady=8)
                tk.Label(inner, text=f"{_type_icon(event['type'])} {event['name']}",
                         bg=SURFACE, fg=TEXT, font=_ui_font(10, 'bold'),
                         anchor='w', justify=tk.LEFT, wraplength=330
                         ).pack(fill=tk.X)
                span = (f"{event['start']:%d %b} – {event['end']:%d %b %Y}"
                        if event['start'] != event['end']
                        else f"{event['start']:%d %b %Y}")
                meta = " · ".join(x for x in (event['type'], span,
                                              event.get('semester')) if x)
                tk.Label(inner, text=meta, bg=SURFACE, fg=TEXT_MUTED,
                         font=_ui_font(8), anchor='w').pack(fill=tk.X)
                if event.get('description'):
                    tk.Label(inner, text=event['description'][:300],
                             bg=SURFACE, fg=TEXT_MUTED, font=_ui_font(9),
                             anchor='w', justify=tk.LEFT, wraplength=330
                             ).pack(fill=tk.X, pady=(4, 0))
                for widget in (card, inner):
                    widget.bind('<Double-Button-1>',
                                lambda _e, ev=event: (top.destroy(),
                                                      self._open_calendar_event(ev)))

        footer = tk.Frame(top, bg=PAGE_BG)
        footer.pack(fill=tk.X, padx=14, pady=(0, 12))
        ttk.Button(footer, text=_("academic_calendar.buttons.close", "Close"),
                   command=top.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text=_("academic_calendar.buttons.add_event", "Add event"),
                   command=lambda: (top.destroy(), self._add_event_on(day))
                   ).pack(side=tk.RIGHT, padx=(0, 8))

    # ── Unchanged ───────────────────────────────────────────────────

    def _show_add_event(self):
        """Show add event dialog"""
        _get_add_event_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _search_events(self):
        """Search events based on search term"""
        search_term = self.search_var.get().lower()

        # Show/hide items based on search
        for item in self.events_tree.get_children():
            event_name = self.events_tree.item(item, 'text').lower()
            values = [str(v).lower() for v in self.events_tree.item(item, 'values')]

            if (search_term in event_name or
                any(search_term in v for v in values)):
                # Show item
                self.events_tree.item(item, tags=())
            else:
                # Hide item (by moving it out of view)
                self.events_tree.item(item, tags=('hidden',))

        # Configure hidden tag
        self.events_tree.tag_configure('hidden', foreground='gray')
