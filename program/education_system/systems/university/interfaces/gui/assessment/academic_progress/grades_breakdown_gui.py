"""Grades Breakdown by Module GUI (Feature 34).

Per-module assignment view with UK-style classifications, percentage-of-max
scoring, optional weight columns, missing-work policy, late flagging,
pass/fail tagging, exam-weighting, best-N drop, and a long tail of UX
features (items 11-50): all-modules combined view, credit-weighted overall
average, what-if calculator, target calculator, distribution stats, trend
chart, class-average comparison (when grade_statistics is populated),
feedback panel, rubric drill-down, year/term + status filters, search,
filtering, refresh, CSV/PDF export, clipboard copy, email-to-advisor
hook, dark/high-contrast palette toggle, keyboard navigation, threaded DB
load, per-module caching, and resolution of the real student_id from
auth.
"""

from __future__ import annotations

import csv
import logging
import statistics
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)


# ---- Constants ----------------------------------------------------------

DEFAULT_PASS_MARK_PCT = 40.0
MISSING_POLICIES = ("Exclude", "Treat as 0", "Provisional warning")

ASSIGNMENT_TYPES = ("All", "Coursework", "Essay", "Quiz", "Exam", "Lab", "Other")
ASSIGNMENT_STATUSES = ("All", "Returned", "Submitted", "Not submitted", "Late")
MODULE_STATUSES = ("Enrolled", "Completed", "Withdrawn", "All")


# Single-source colour palettes — switching themes flips this dict so the
# tag-configure / widget-bg calls draw from one place rather than scattered
# hex literals (avoids the "SystemButtonFace" footgun).
PALETTES = {
    'light': {
        'pass': '#d4edda', 'fail': '#f8d7da', 'late': '#fff3cd',
        'awaiting': '#e8f4fd', 'not_submitted': '#e2e3e5',
        'dropped': '#cccccc', 'dropped_fg': '#666666',
        'zebra': '#f7f9fc',  'banner_fg': '#2c3e50',
        'warning_fg': '#b35b00', 'subtle_fg': '#7f8c8d',
        'chart_line': '#3498db', 'chart_bg': '#ecf0f1',
        'chart_axis': '#bdc3c7',
    },
    'dark': {
        'pass': '#1e3d2f', 'fail': '#4a1f24', 'late': '#4a3f1a',
        'awaiting': '#1f3a4a', 'not_submitted': '#2c2f33',
        'dropped': '#444444', 'dropped_fg': '#999999',
        'zebra': '#2a2d31', 'banner_fg': '#ecf0f1',
        'warning_fg': '#f39c12', 'subtle_fg': '#95a5a6',
        'chart_line': '#5dade2', 'chart_bg': '#2c2f33',
        'chart_axis': '#7f8c8d',
    },
}


# ---- i18n helper --------------------------------------------------------

def _t(key: str, default: str | None = None) -> str:
    """Translate *key* via the shared i18n module when available, else return
    *default* (or the key itself).  Used so the GUI is i18n-ready without
    breaking when run in environments where i18n isn't initialised."""
    try:
        from education_system.systems.university.infrastructure.i18n import get_text
        return get_text(key, default or key)
    except Exception:
        return default if default is not None else key


# ---- Tooltip helper -----------------------------------------------------

class _Tooltip:
    """Tiny tooltip helper — hover delays a small Toplevel near the cursor."""

    def __init__(self, widget, text_callback):
        self.widget = widget
        self.text_callback = text_callback   # called per-hover, returns str or None
        self._tip: tk.Toplevel | None = None
        self._after_id: str | None = None
        widget.bind('<Motion>', self._schedule, add='+')
        widget.bind('<Leave>', self._hide, add='+')

    def _schedule(self, event):
        self._cancel()
        self._after_id = self.widget.after(500, lambda: self._show(event))

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self, event):
        text = None
        try:
            text = self.text_callback(event)
        except Exception:
            return
        if not text:
            return
        self._hide()
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        tk.Label(
            tip, text=text, justify='left',
            background='#ffffe0', relief='solid', borderwidth=1,
            font=('Arial', 9), wraplength=420,
        ).pack(ipadx=4, ipady=2)
        self._tip = tip

    def _hide(self, *_):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ---- Main GUI -----------------------------------------------------------

class GradesBreakdownGUI:
    """Toplevel window showing grades broken down by enrolled module."""

    # Treeview columns. Same set whether we're in per-module or all-modules
    # mode; the Module column is hidden in per-module mode via displaycolumns.
    _ASSIGNMENT_COLS = (
        'module', 'title', 'score', 'max_score', 'pct',
        'weight', 'type', 'due_date', 'status', 'late', 'pass_fail',
        'vs_class',
    )

    _ASSIGNMENT_HEADINGS = {
        'module':    ('Module',      90,  'center'),
        'title':     ('Assignment',  220, 'w'),
        'score':     ('Score',       60,  'center'),
        'max_score': ('Max',         60,  'center'),
        'pct':       ('%',           60,  'center'),
        'weight':    ('Weight %',    75,  'center'),
        'type':      ('Type',        90,  'center'),
        'due_date':  ('Due',         100, 'center'),
        'status':    ('Status',      110, 'center'),
        'late':      ('Late?',       70,  'center'),
        'pass_fail': ('P/F',         50,  'center'),
        'vs_class':  ('vs Class',    75,  'center'),
    }

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth

        # Item 48 — resolve the real student_id, not just the username.
        self.username = ''
        if auth and getattr(auth, 'current_user', None):
            self.username = auth.current_user.get('username', '')
        self.student_id = self._resolve_student_id(auth, self.username)
        self.display_name = self._resolve_display_name(auth)

        self.window = tk.Toplevel(parent)
        # Item 39 — student name in the title
        title_who = f" — {self.display_name} ({self.student_id})" if self.student_id else ""
        self.window.title(f"Grades Breakdown{title_who}")
        self.window.geometry("1280x780")
        self.window.minsize(1100, 640)
        self.window.transient(parent)

        # ---- Computation settings (apply to every render) ----
        self.pass_mark_var = tk.DoubleVar(value=DEFAULT_PASS_MARK_PCT)
        self.missing_policy_var = tk.StringVar(value=MISSING_POLICIES[0])
        self.drop_worst_var = tk.IntVar(value=0)
        self.exam_weight_var = tk.IntVar(value=0)

        # ---- Filter / view state ----
        self.year_filter_var = tk.StringVar(value="All")
        self.term_filter_var = tk.StringVar(value="All")
        self.module_status_var = tk.StringVar(value="Enrolled")
        self.module_search_var = tk.StringVar(value="")
        self.assign_type_filter_var = tk.StringVar(value="All")
        self.assign_status_filter_var = tk.StringVar(value="All")
        self.view_mode_var = tk.StringVar(value="Per module")
        self.theme_var = tk.StringVar(value="light")

        # Recompute on settings/filter change.
        for var in (self.pass_mark_var, self.missing_policy_var,
                    self.drop_worst_var, self.exam_weight_var):
            var.trace_add('write', lambda *_: self._recompute_summary())
        for var in (self.assign_type_filter_var, self.assign_status_filter_var):
            var.trace_add('write', lambda *_: self._render_rows())
        self.module_search_var.trace_add('write', lambda *_: self._apply_module_search())

        # ---- Schema introspection ----
        self._weight_col = self._detect_weight_column()

        # ---- Caches ----
        self._modules: list[dict] = []        # full list from DB
        self._visible_modules: list[dict] = []  # after search filter
        self._current_module: str | None = None
        self._rows: list[dict] = []           # rows for the open module
        self._all_rows: list[dict] = []       # rows for ALL modules (combined view)
        self._assignments_cache: dict[str, list[dict]] = {}
        self._stats_cache: dict[int, dict] = {}     # assessment_id -> stats row
        # Item 13 — what-if overrides (assignment row index → hypothetical pct).
        self._what_if: dict[tuple[str, str], float] = {}

        self._setup_ui()
        self._bind_keyboard()
        self._load_modules()

    # ------------------------------------------------------------------
    # Identity / schema introspection
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_student_id(auth, username: str) -> str:
        """Look up the real student_id for *username* in the canonical users
        table.  Falls back to username when no row found, matching the
        previous behaviour for installations seeded with username==student_id.
        """
        if not username:
            return ''
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT student_id FROM users WHERE username = ?", (username,)
                ).fetchone()
                if row and row['student_id']:
                    return row['student_id']
        except Exception:
            pass
        return username

    @staticmethod
    def _resolve_display_name(auth) -> str:
        if not auth or not getattr(auth, 'current_user', None):
            return ''
        cu = auth.current_user
        return (cu.get('display_name') or cu.get('username') or '').strip()

    @staticmethod
    def _detect_weight_column() -> str | None:
        """Return ``'weight'`` / ``'weighting'`` if present on assignments."""
        try:
            with get_connection() as conn:
                cols = {r[1] for r in conn.execute(
                    "PRAGMA table_info(assignments)").fetchall()}
            for cand in ('weight', 'weighting'):
                if cand in cols:
                    return cand
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.style = ttk.Style(self.window)

        # ---- Header bar ----
        header = ttk.Frame(self.window)
        header.pack(fill=tk.X, padx=12, pady=(8, 4))
        ttk.Label(
            header, text=_t('grades.title', 'Grades Breakdown by Module'),
            font=('Arial', 16, 'bold'),
        ).pack(side=tk.LEFT)

        ttk.Button(header, text=_t('grades.refresh', 'Refresh (F5)'),
                   command=self._refresh).pack(side=tk.RIGHT, padx=4)
        ttk.Button(header, text=_t('grades.what_if', 'What-If…'),
                   command=self._open_what_if).pack(side=tk.RIGHT, padx=4)
        ttk.Button(header, text=_t('grades.target', 'Target…'),
                   command=self._open_target).pack(side=tk.RIGHT, padx=4)

        # ---- Settings bar ----
        settings = ttk.Frame(self.window)
        settings.pack(fill=tk.X, padx=12, pady=(0, 4))

        ttk.Label(settings, text=_t('grades.pass_mark', 'Pass mark (%):')).pack(side=tk.LEFT)
        ttk.Spinbox(settings, from_=0, to=100, increment=1, width=5,
                    textvariable=self.pass_mark_var).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(settings, text=_t('grades.missing', 'Missing:')).pack(side=tk.LEFT)
        ttk.Combobox(settings, textvariable=self.missing_policy_var,
                     values=list(MISSING_POLICIES), state='readonly',
                     width=20).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(settings, text=_t('grades.drop_worst', 'Drop worst N:')).pack(side=tk.LEFT)
        ttk.Spinbox(settings, from_=0, to=5, increment=1, width=4,
                    textvariable=self.drop_worst_var).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(settings, text=_t('grades.exam_weight', 'Exam weight % (0=off):')).pack(side=tk.LEFT)
        ttk.Spinbox(settings, from_=0, to=100, increment=5, width=5,
                    textvariable=self.exam_weight_var).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(settings, text=_t('grades.view', 'View:')).pack(side=tk.LEFT)
        view_combo = ttk.Combobox(
            settings, textvariable=self.view_mode_var,
            values=("Per module", "All modules"), state='readonly', width=14,
        )
        view_combo.pack(side=tk.LEFT, padx=(4, 12))
        view_combo.bind('<<ComboboxSelected>>', lambda _e: self._on_view_mode_change())

        ttk.Label(settings, text=_t('grades.theme', 'Theme:')).pack(side=tk.LEFT)
        theme_combo = ttk.Combobox(
            settings, textvariable=self.theme_var,
            values=('light', 'dark'), state='readonly', width=8,
        )
        theme_combo.pack(side=tk.LEFT, padx=(4, 12))
        theme_combo.bind('<<ComboboxSelected>>', lambda _e: self._apply_palette())

        # Export menu
        export_btn = ttk.Menubutton(settings, text=_t('grades.export', 'Export…'))
        export_menu = tk.Menu(export_btn, tearoff=0)
        export_menu.add_command(label='CSV (current view)…', command=self._export_csv)
        export_menu.add_command(label='PDF transcript…', command=self._export_pdf)
        export_menu.add_separator()
        export_menu.add_command(label='Email to advisor…', command=self._email_advisor)
        export_btn.configure(menu=export_menu)
        export_btn.pack(side=tk.RIGHT)

        # ---- Filter bar ----
        filters = ttk.Frame(self.window)
        filters.pack(fill=tk.X, padx=12, pady=(0, 4))

        ttk.Label(filters, text=_t('grades.year', 'Year:')).pack(side=tk.LEFT)
        self.year_combo = ttk.Combobox(
            filters, textvariable=self.year_filter_var,
            values=("All",), state='readonly', width=12,
        )
        self.year_combo.pack(side=tk.LEFT, padx=(4, 12))
        self.year_combo.bind('<<ComboboxSelected>>', lambda _e: self._refresh_modules_only())

        ttk.Label(filters, text=_t('grades.term', 'Term:')).pack(side=tk.LEFT)
        self.term_combo = ttk.Combobox(
            filters, textvariable=self.term_filter_var,
            values=("All",), state='readonly', width=14,
        )
        self.term_combo.pack(side=tk.LEFT, padx=(4, 12))
        self.term_combo.bind('<<ComboboxSelected>>', lambda _e: self._refresh_modules_only())

        ttk.Label(filters, text=_t('grades.module_status', 'Modules:')).pack(side=tk.LEFT)
        ttk.Combobox(
            filters, textvariable=self.module_status_var,
            values=list(MODULE_STATUSES), state='readonly', width=12,
        ).pack(side=tk.LEFT, padx=(4, 12))
        self.module_status_var.trace_add(
            'write', lambda *_: self._refresh_modules_only())

        ttk.Label(filters, text=_t('grades.search', 'Search:')).pack(side=tk.LEFT)
        ttk.Entry(filters, textvariable=self.module_search_var, width=24).pack(
            side=tk.LEFT, padx=(4, 12))

        ttk.Label(filters, text=_t('grades.type_filter', 'Type:')).pack(side=tk.LEFT)
        ttk.Combobox(
            filters, textvariable=self.assign_type_filter_var,
            values=list(ASSIGNMENT_TYPES), state='readonly', width=12,
        ).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(filters, text=_t('grades.assign_status_filter', 'Status:')).pack(side=tk.LEFT)
        ttk.Combobox(
            filters, textvariable=self.assign_status_filter_var,
            values=list(ASSIGNMENT_STATUSES), state='readonly', width=14,
        ).pack(side=tk.LEFT, padx=(4, 12))

        # ---- Main split: modules / assignments ----
        main = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        left_frame = ttk.LabelFrame(main, text=_t('grades.modules', 'Modules'), padding=4)
        right_frame = ttk.LabelFrame(main, text=_t('grades.assignments', 'Assignments'), padding=4)
        main.add(left_frame, weight=1)
        main.add(right_frame, weight=4)

        # Module Treeview (item 31, 33, 38)
        self.module_tree = ttk.Treeview(
            left_frame, columns=('count',), show='tree headings', height=24,
        )
        self.module_tree.heading('#0', text='Module',
                                 command=lambda: self._sort_module_tree('#0'))
        self.module_tree.heading('count', text='Graded',
                                 command=lambda: self._sort_module_tree('count'))
        self.module_tree.column('#0', width=240)
        self.module_tree.column('count', width=70, anchor='center')
        self.module_tree.bind('<<TreeviewSelect>>', self._on_module_select)
        self.module_tree.bind('<Return>', self._on_module_select)
        self.module_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        mtree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL,
                                     command=self.module_tree.yview)
        self.module_tree.configure(yscrollcommand=mtree_scroll.set)
        mtree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Right pane is split vertically: top assignments, bottom feedback +
        # stats + trend.
        right_split = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_split.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(right_split)
        bottom = ttk.Frame(right_split)
        right_split.add(top, weight=3)
        right_split.add(bottom, weight=2)

        # Assignment Treeview
        self.tree = ttk.Treeview(
            top, columns=self._ASSIGNMENT_COLS, show='headings', height=14,
        )
        for c, (label, width, anchor) in self._ASSIGNMENT_HEADINGS.items():
            self.tree.heading(c, text=label,
                              command=lambda col=c: self._sort_tree(col))
            self.tree.column(c, width=width, anchor=anchor)
        # Hide Module column when in per-module mode (default).
        self.tree.configure(displaycolumns=tuple(
            c for c in self._ASSIGNMENT_COLS if c != 'module'))

        self.tree.bind('<<TreeviewSelect>>', self._on_assignment_select)
        self.tree.bind('<Double-Button-1>', self._open_what_if_for_selected)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        atree_scroll = ttk.Scrollbar(top, orient=tk.VERTICAL,
                                     command=self.tree.yview)
        self.tree.configure(yscrollcommand=atree_scroll.set)
        atree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tooltip for truncated cells (item 35)
        _Tooltip(self.tree, self._tooltip_for_event)

        # Bottom: feedback + stats + trend in a 3-pane horizontal split.
        bottom_paned = ttk.PanedWindow(bottom, orient=tk.HORIZONTAL)
        bottom_paned.pack(fill=tk.BOTH, expand=True)

        # Feedback (item 18) + rubric button (item 19)
        fb_frame = ttk.LabelFrame(bottom_paned,
                                  text=_t('grades.feedback', 'Feedback'),
                                  padding=4)
        self.feedback_text = tk.Text(fb_frame, wrap='word', height=8,
                                     state='disabled', font=('Arial', 10))
        self.feedback_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        fb_scroll = ttk.Scrollbar(fb_frame, orient=tk.VERTICAL,
                                  command=self.feedback_text.yview)
        self.feedback_text.configure(yscrollcommand=fb_scroll.set)
        fb_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.rubric_btn = ttk.Button(
            fb_frame, text=_t('grades.view_rubric', 'View Rubric'),
            command=self._show_rubric, state='disabled',
        )
        self.rubric_btn.pack(side=tk.BOTTOM, pady=4)
        bottom_paned.add(fb_frame, weight=2)

        # Stats panel (item 15)
        stats_frame = ttk.LabelFrame(
            bottom_paned, text=_t('grades.stats', 'Distribution'), padding=4,
        )
        self.stats_var = tk.StringVar(value='—')
        ttk.Label(stats_frame, textvariable=self.stats_var, justify='left',
                  font=('TkDefaultFont', 10)).pack(anchor='nw')
        bottom_paned.add(stats_frame, weight=1)

        # Trend chart (item 16)
        trend_frame = ttk.LabelFrame(
            bottom_paned, text=_t('grades.trend', 'Trend'), padding=4,
        )
        self.trend_canvas = tk.Canvas(
            trend_frame, height=160, bg='#ecf0f1', highlightthickness=0,
        )
        self.trend_canvas.pack(fill=tk.BOTH, expand=True)
        self.trend_canvas.bind('<Configure>', lambda _e: self._render_trend())
        bottom_paned.add(trend_frame, weight=2)

        # ---- Status bar (items 12, 25, 36, 37) ----
        statusbar = ttk.Frame(self.window)
        statusbar.pack(fill=tk.X, padx=12, pady=(2, 8))

        self.summary_var = tk.StringVar(value='—')
        self.warning_var = tk.StringVar(value='')
        self.refresh_var = tk.StringVar(value='')
        self.overall_var = tk.StringVar(value='')

        ttk.Label(statusbar, textvariable=self.summary_var,
                  font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        ttk.Label(statusbar, textvariable=self.warning_var,
                  font=('Arial', 9, 'italic')).pack(side=tk.LEFT, padx=14)
        ttk.Label(statusbar, textvariable=self.overall_var,
                  font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=20)
        ttk.Label(statusbar, textvariable=self.refresh_var,
                  font=('Arial', 9)).pack(side=tk.RIGHT)

        # Loading indicator overlaid in the assignments frame.
        self._loading_label = ttk.Label(top, text=_t('grades.loading', 'Loading…'),
                                        foreground='#7f8c8d', font=('Arial', 11, 'italic'))
        # not packed — packed/unpacked by _set_loading.

        self._apply_palette()

    # ------------------------------------------------------------------
    # Keyboard / accessibility
    # ------------------------------------------------------------------

    def _bind_keyboard(self):
        # Item 24
        self.window.bind('<F5>', lambda _e: self._refresh())
        self.window.bind('<Control-r>', lambda _e: self._refresh())
        # Item 28 — copy selected rows to clipboard as TSV.
        self.window.bind('<Control-c>', lambda _e: self._copy_selection())
        # Item 30 — Ctrl+P shortcut into the PDF export.
        self.window.bind('<Control-p>', lambda _e: self._export_pdf())
        # Item 44 — font scaling.
        self.window.bind('<Control-equal>', lambda _e: self._scale_font(+1))
        self.window.bind('<Control-plus>',  lambda _e: self._scale_font(+1))
        self.window.bind('<Control-minus>', lambda _e: self._scale_font(-1))

    def _scale_font(self, delta):
        try:
            current = int(self.style.lookup('TLabel', 'font').split()[-1] or 10)
        except Exception:
            current = 10
        new = max(8, min(20, current + delta))
        for s in ('TLabel', 'TButton', 'TCombobox', 'TEntry', 'Treeview'):
            try:
                self.style.configure(s, font=('Arial', new))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Theme / palette
    # ------------------------------------------------------------------

    def _apply_palette(self):
        p = PALETTES.get(self.theme_var.get(), PALETTES['light'])
        for tag in ('pass', 'fail', 'late', 'awaiting', 'not_submitted'):
            self.tree.tag_configure(tag, background=p[tag])
            self.module_tree.tag_configure(tag, background=p[tag])
        self.tree.tag_configure('dropped', background=p['dropped'],
                                foreground=p['dropped_fg'])
        # Zebra-stripe alternate rows (item 34 reinforced)
        self.tree.tag_configure('zebra', background=p['zebra'])
        # Trend chart background follows the theme.
        self.trend_canvas.configure(bg=p['chart_bg'])
        self._render_trend()

    # ------------------------------------------------------------------
    # Module loading
    # ------------------------------------------------------------------

    def _load_modules(self):
        self.module_tree.delete(*self.module_tree.get_children())
        self._modules = []
        self._visible_modules = []

        if not self.student_id:
            self._set_empty_state(_t('grades.no_student', 'Not signed in.'))
            return

        # Build SQL conditional on the year/term/status filters.
        status = self.module_status_var.get()
        year = self.year_filter_var.get()
        term = self.term_filter_var.get()
        params: list = [self.student_id]
        clauses = ["sm.student_id = ?"]

        if status != 'All':
            clauses.append("LOWER(sm.status) = LOWER(?)")
            params.append(status)
        if year != 'All':
            clauses.append("(sm.year = ? OR m.academic_year = ?)")
            params.extend([year, year])
        if term != 'All':
            clauses.append("(LOWER(sm.semester) = LOWER(?) OR LOWER(m.semester) = LOWER(?))")
            params.extend([term, term])

        sql = (
            "SELECT m.module_code, m.module_name, m.credits, "
            "       sm.status AS sm_status, sm.semester AS sm_semester, "
            "       sm.year AS sm_year, m.academic_year, m.semester AS m_semester "
            "FROM student_modules sm "
            "INNER JOIN modules m ON sm.module_code = m.module_code "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY m.module_code"
        )

        try:
            with get_connection() as conn:
                rows = conn.execute(sql, tuple(params)).fetchall()
        except Exception as e:
            logger.error(f"Error loading modules: {e}")
            messagebox.showerror(
                _t('common.error', 'Error'),
                f"Failed to load modules: {e}", parent=self.window,
            )
            return

        # Populate the year/term combos from observed values (first run only).
        self._populate_filter_combos()

        for row in rows or []:
            self._modules.append({
                'module_code': row['module_code'],
                'module_name': row['module_name'],
                'credits': row['credits'] or 0,
                'status': row['sm_status'],
            })

        self._apply_module_search()
        self._set_loading(False)
        if not self._modules:
            self._set_empty_state(_t(
                'grades.no_modules',
                'No modules match the current filters.',
            ))

        # Refresh time stamp (item 25)
        self.refresh_var.set(_t('grades.last_refresh', 'Last refreshed: ') + datetime.now().strftime('%H:%M:%S'))

        try:
            log_activity(self.student_id, 'grades_breakdown_open',
                         f"Opened grades breakdown ({len(self._modules)} modules)")
        except Exception:
            pass

        # In all-modules mode, kick off background load of every module's data.
        if self.view_mode_var.get() == 'All modules':
            self._load_all_modules_async()

    def _populate_filter_combos(self):
        """Best-effort: fill the year/term combos from observed data."""
        try:
            with get_connection() as conn:
                years = conn.execute(
                    "SELECT DISTINCT COALESCE(sm.year, m.academic_year) AS y "
                    "FROM student_modules sm "
                    "INNER JOIN modules m ON sm.module_code = m.module_code "
                    "WHERE sm.student_id = ? AND y IS NOT NULL "
                    "ORDER BY y DESC", (self.student_id,),
                ).fetchall()
                terms = conn.execute(
                    "SELECT DISTINCT COALESCE(sm.semester, m.semester) AS t "
                    "FROM student_modules sm "
                    "INNER JOIN modules m ON sm.module_code = m.module_code "
                    "WHERE sm.student_id = ? AND t IS NOT NULL "
                    "ORDER BY t", (self.student_id,),
                ).fetchall()
        except Exception:
            return
        year_vals = ('All',) + tuple(r['y'] for r in years if r['y'])
        term_vals = ('All',) + tuple(r['t'] for r in terms if r['t'])
        self.year_combo['values'] = year_vals
        self.term_combo['values'] = term_vals

    def _apply_module_search(self):
        """Item 22 — instant-filter the module tree on key release."""
        needle = self.module_search_var.get().strip().lower()
        self.module_tree.delete(*self.module_tree.get_children())
        self._visible_modules = []
        for m in self._modules:
            blob = f"{m['module_code']} {m['module_name']}".lower()
            if needle and needle not in blob:
                continue
            self._visible_modules.append(m)
            count = self._graded_count_label(m['module_code'])
            label = f"{m['module_code']} — {m['module_name']}"
            self.module_tree.insert('', tk.END,
                                    iid=m['module_code'],
                                    text=label, values=(count,))

    def _graded_count_label(self, module_code: str) -> str:
        """Item 38 — '3/5 graded' badge.  Uses the cache when populated."""
        rows = self._assignments_cache.get(module_code)
        if rows is None:
            return '—'
        graded = sum(1 for r in rows if r.get('grade') is not None)
        return f"{graded}/{len(rows)}"

    # ------------------------------------------------------------------
    # Per-module load (threaded — item 46 + cache item 47)
    # ------------------------------------------------------------------

    def _on_module_select(self, _event):
        sel = self.module_tree.selection()
        if not sel:
            return
        code = sel[0]
        self._current_module = code
        self._load_assignments(code)

    def _load_assignments(self, module_code: str, force: bool = False):
        # Per-module cache hit
        if not force and module_code in self._assignments_cache:
            self._rows = self._assignments_cache[module_code]
            self._render_rows()
            return

        self._set_loading(True)

        def worker():
            try:
                rows = self._fetch_assignments_sql(module_code)
                stats = self._fetch_class_stats([r.get('assessment_id') for r in rows])
            except Exception as e:
                logger.exception("Worker failed")
                self.window.after(0, lambda err=e: self._on_load_error(err))
                return
            self.window.after(0, lambda: self._on_load_complete(module_code, rows, stats))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_assignments_sql(self, module_code: str) -> list[dict]:
        weight_col = (
            f", a.{self._weight_col} AS weight" if self._weight_col else ", NULL AS weight"
        )
        sql = f"""
            SELECT a.id AS assessment_id, a.title, a.max_marks,
                   a.assignment_type, a.due_date, a.rubric_id,
                   s.grade, s.status AS submission_status,
                   s.late_submission, s.late_days, s.submission_date,
                   s.feedback {weight_col}
            FROM assignments a
            LEFT JOIN assignment_submissions s
              ON a.id = s.assignment_id AND s.student_id = ?
            WHERE a.module_code = ?
            ORDER BY a.due_date
        """
        with get_connection() as conn:
            cur = conn.execute(sql, (self.student_id, module_code))
            return [dict(r) for r in cur.fetchall()]

    def _fetch_class_stats(self, assessment_ids: list[int]) -> dict[int, dict]:
        ids = [i for i in assessment_ids if i]
        if not ids:
            return {}
        try:
            with get_connection() as conn:
                placeholders = ','.join('?' * len(ids))
                rows = conn.execute(
                    "SELECT assessment_id, mean, median, std_dev, min_score, "
                    "       max_score, q1, q3 "
                    "FROM grade_statistics "
                    f"WHERE assessment_id IN ({placeholders})",
                    tuple(ids),
                ).fetchall()
                return {r['assessment_id']: dict(r) for r in rows}
        except Exception:
            return {}

    def _on_load_error(self, exc):
        self._set_loading(False)
        messagebox.showerror(_t('common.error', 'Error'),
                             f"Failed to load assignments: {exc}",
                             parent=self.window)

    def _on_load_complete(self, module_code: str, rows: list[dict],
                          stats: dict[int, dict]):
        self._set_loading(False)
        self._assignments_cache[module_code] = rows
        self._stats_cache.update(stats)
        # Refresh module-tree badges so '3/5' appears beside the now-loaded module.
        self._apply_module_search()
        if self._current_module == module_code:
            self._rows = rows
            self._render_rows()

    # ------------------------------------------------------------------
    # All-modules combined (item 11)
    # ------------------------------------------------------------------

    def _on_view_mode_change(self):
        if self.view_mode_var.get() == 'All modules':
            cols = self._ASSIGNMENT_COLS
        else:
            cols = tuple(c for c in self._ASSIGNMENT_COLS if c != 'module')
        self.tree.configure(displaycolumns=cols)
        if self.view_mode_var.get() == 'All modules':
            self._load_all_modules_async()
        else:
            if self._current_module:
                self._load_assignments(self._current_module)

    def _load_all_modules_async(self):
        """Kick off a worker that fetches assignments for every visible module
        and then renders them in a single combined treeview."""
        self._set_loading(True)

        def worker():
            try:
                aggregated: list[dict] = []
                ids: list[int] = []
                for m in list(self._modules):
                    code = m['module_code']
                    if code not in self._assignments_cache:
                        self._assignments_cache[code] = self._fetch_assignments_sql(code)
                    for r in self._assignments_cache[code]:
                        rr = dict(r)
                        rr.setdefault('module_code', code)
                        aggregated.append(rr)
                        if rr.get('assessment_id'):
                            ids.append(rr['assessment_id'])
                stats = self._fetch_class_stats(ids)
            except Exception as e:
                logger.exception("All-modules worker failed")
                self.window.after(0, lambda err=e: self._on_load_error(err))
                return
            self.window.after(0, lambda: self._on_all_modules_complete(aggregated, stats))

        threading.Thread(target=worker, daemon=True).start()

    def _on_all_modules_complete(self, rows: list[dict], stats: dict[int, dict]):
        self._set_loading(False)
        self._all_rows = rows
        self._stats_cache.update(stats)
        self._rows = rows
        self._apply_module_search()  # update graded counts after caching
        self._render_rows()

    # ------------------------------------------------------------------
    # Rendering / computation
    # ------------------------------------------------------------------

    def _render_rows(self):
        self.tree.delete(*self.tree.get_children())

        pass_mark = self._safe_float(self.pass_mark_var.get(), DEFAULT_PASS_MARK_PCT)
        policy = self.missing_policy_var.get()
        drop_n = max(0, self._safe_int(self.drop_worst_var.get(), 0))
        exam_weight = max(0, min(100, self._safe_int(self.exam_weight_var.get(), 0)))
        type_filter = self.assign_type_filter_var.get()
        status_filter = self.assign_status_filter_var.get()

        rows = list(self._rows)
        if not rows:
            self.summary_var.set(_t('grades.empty', 'No assignments to show.'))
            self.warning_var.set('')
            self._render_stats([])
            self._render_trend()
            return

        # Pass 1: filter + insert + classify.
        scored: list[tuple[int, float, float, bool]] = []  # (idx, pct, weight, is_exam)
        unsubmitted: list[tuple[int, float, bool]] = []
        iids: list[str] = []
        zebra = False

        for idx, r in enumerate(rows):
            # Type filter
            if type_filter != 'All':
                rt = (r.get('assignment_type') or '').lower()
                if type_filter.lower() not in rt:
                    iids.append('')  # placeholder so indexes stay aligned
                    continue
            # Status filter (post-status mapping)
            display_status, _tag, _late, _pf = self._row_status(r, self._row_percentage(r), pass_mark)
            if status_filter != 'All' and status_filter.lower() not in display_status.lower():
                iids.append('')
                continue

            iid = self._insert_assignment_row(r, pass_mark, zebra=zebra)
            iids.append(iid)
            zebra = not zebra

            # Apply what-if override if present.
            override_key = ((r.get('module_code') or self._current_module or ''),
                            r.get('title') or '')
            if override_key in self._what_if and r.get('grade') is None:
                pct = self._what_if[override_key]
            else:
                pct = self._row_percentage(r)

            weight = float(r.get('weight') or 0.0) or 1.0
            is_exam = self._is_exam(r.get('assignment_type'))
            if pct is not None:
                scored.append((idx, pct, weight, is_exam))
            else:
                unsubmitted.append((idx, weight, is_exam))

        # Best-N drop
        dropped_iids: set[int] = set()
        if drop_n and len(scored) > drop_n:
            ranked = sorted(scored, key=lambda t: t[1])
            dropped_iids = {ix for ix, *_ in ranked[:drop_n]}
            scored = [s for s in scored if s[0] not in dropped_iids]
            for ix in dropped_iids:
                if ix < len(iids) and iids[ix]:
                    self.tree.item(iids[ix], tags=('dropped',))

        # Missing-work policy
        treat_missing_as_zero = (policy == "Treat as 0")
        provisional_warning = (policy == "Provisional warning") and bool(unsubmitted)
        if treat_missing_as_zero:
            for ix, w, is_exam in unsubmitted:
                if ix in dropped_iids:
                    continue
                scored.append((ix, 0.0, w, is_exam))

        # --- Module average ---
        if scored:
            if exam_weight > 0:
                avg = self._average_with_exam_split(scored, exam_weight)
            else:
                total_w = sum(w for _, _, w, _ in scored) or 1.0
                avg = sum(p * w for _, p, w, _ in scored) / total_w
            bits = [
                f"Module Avg: {avg:.1f}%",
                f"Class: {self._uk_classification(avg)}",
                f"Counted: {len(scored)}",
            ]
            if dropped_iids:
                bits.append(f"Dropped: {len(dropped_iids)}")
            if exam_weight > 0:
                bits.append(f"Exam {exam_weight}/{100 - exam_weight}")
            if self._what_if:
                bits.append("(what-if)")
            self.summary_var.set("   |   ".join(bits))
        else:
            self.summary_var.set(_t('grades.no_marks', 'Module Avg: No graded assignments yet'))

        # --- Provisional / zero-substitution warning ---
        if provisional_warning:
            self.warning_var.set(
                f"Provisional — {len(unsubmitted)} unsubmitted/unmarked.")
        elif treat_missing_as_zero and unsubmitted:
            self.warning_var.set(
                f"{len(unsubmitted)} unsubmitted counted as 0.")
        else:
            self.warning_var.set('')

        # --- Item 12 — credit-weighted overall average banner ---
        self._render_overall_average(pass_mark, exam_weight)

        # --- Distribution stats + trend (items 15, 16) ---
        self._render_stats([p for _, p, _, _ in scored])
        self._render_trend()

    def _render_overall_average(self, pass_mark: float, exam_weight: int):
        """Item 12 — compute a credit-weighted overall across all cached
        modules.  Falls back to a simple unweighted mean if credits are
        missing.  Updates the right-hand side of the status bar.
        """
        per_module_avgs: list[tuple[float, int]] = []
        for code, mod in {m['module_code']: m for m in self._modules}.items():
            cached = self._assignments_cache.get(code)
            if not cached:
                continue
            avg = self._compute_module_average(cached, pass_mark, exam_weight)
            if avg is None:
                continue
            credits = mod.get('credits') or 0
            per_module_avgs.append((avg, credits))
        if not per_module_avgs:
            self.overall_var.set('')
            return
        if any(c for _, c in per_module_avgs):
            tot_c = sum(c for _, c in per_module_avgs) or 1
            overall = sum(a * c for a, c in per_module_avgs) / tot_c
            label = "Credit-weighted overall"
        else:
            overall = sum(a for a, _ in per_module_avgs) / len(per_module_avgs)
            label = "Overall (equal-weight)"
        self.overall_var.set(
            f"{label}: {overall:.1f}%  →  {self._uk_classification(overall)}"
        )

    def _compute_module_average(self, rows, pass_mark, exam_weight):
        """Same algorithm as the live render but without UI side-effects."""
        scored = []
        for r in rows:
            pct = self._row_percentage(r)
            weight = float(r.get('weight') or 0.0) or 1.0
            is_exam = self._is_exam(r.get('assignment_type'))
            if pct is not None:
                scored.append((0, pct, weight, is_exam))
        if not scored:
            return None
        if exam_weight > 0:
            return self._average_with_exam_split(scored, exam_weight)
        total_w = sum(w for _, _, w, _ in scored) or 1.0
        return sum(p * w for _, p, w, _ in scored) / total_w

    def _insert_assignment_row(self, r: dict, pass_mark: float,
                               zebra: bool = False) -> str:
        title = r.get('title') or ''
        grade = r.get('grade')
        max_marks = r.get('max_marks') or 0
        atype = r.get('assignment_type') or ''
        due_date = r.get('due_date') or ''
        weight = r.get('weight')
        module_code = r.get('module_code') or self._current_module or ''

        pct = self._row_percentage(r)
        score_disp = f"{grade:g}" if isinstance(grade, (int, float)) else "--"
        max_disp = f"{max_marks:g}" if isinstance(max_marks, (int, float)) else (
            str(max_marks) if max_marks else "--"
        )
        pct_disp = f"{pct:.1f}" if pct is not None else "--"
        weight_disp = (
            f"{float(weight):g}" if isinstance(weight, (int, float)) and weight else "—"
        )
        status, tag, late_disp, pf_disp = self._row_status(r, pct, pass_mark)

        # Item 17 — vs class mean (when grade_statistics has the row).
        vs_disp = "—"
        stats = self._stats_cache.get(r.get('assessment_id'))
        if stats and isinstance(grade, (int, float)) and stats.get('mean') is not None:
            try:
                diff = float(grade) - float(stats['mean'])
                vs_disp = f"{diff:+.1f}"
            except Exception:
                pass

        tags: list[str] = [tag] if tag else []
        if zebra and tag not in ('pass', 'fail', 'late', 'dropped'):
            tags.append('zebra')

        return self.tree.insert('', tk.END, values=(
            module_code, title, score_disp, max_disp, pct_disp,
            weight_disp, atype, due_date, status, late_disp, pf_disp, vs_disp,
        ), tags=tuple(tags))

    @staticmethod
    def _row_percentage(r: dict):
        grade = r.get('grade')
        max_marks = r.get('max_marks') or 0
        if grade is None or not max_marks:
            return None
        try:
            return (float(grade) / float(max_marks)) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _row_status(r: dict, pct, pass_mark: float):
        grade = r.get('grade')
        sub_status = (r.get('submission_status') or '').strip().lower()
        late_flag = bool(r.get('late_submission'))
        late_days = r.get('late_days') or 0

        if grade is not None:
            status = "Returned"
            passed = pct is not None and pct >= pass_mark
            tag = 'pass' if passed else 'fail'
            pf = "Pass" if passed else "Fail"
        elif sub_status:
            status = sub_status.capitalize()
            tag = 'awaiting' if sub_status in (
                'submitted', 'awaiting', 'awaiting marking', 'pending',
            ) else 'not_submitted'
            pf = "—"
        elif r.get('submission_date'):
            status, tag, pf = "Awaiting marking", 'awaiting', "—"
        else:
            status, tag, pf = "Not submitted", 'not_submitted', "—"

        if late_flag and late_days:
            late_text = f"+{int(late_days)}d"
        elif late_flag:
            late_text = "Late"
        else:
            late_text = "—"

        if late_flag and tag == 'pass':
            tag = 'late'
        return status, tag, late_text, pf

    @staticmethod
    def _is_exam(atype) -> bool:
        return 'exam' in (atype or '').lower()

    @staticmethod
    def _average_with_exam_split(scored, exam_weight_pct):
        exam_pcts = [p for _, p, _, is_exam in scored if is_exam]
        other_pcts = [p for _, p, _, is_exam in scored if not is_exam]
        ew = exam_weight_pct / 100.0
        if not exam_pcts:
            return sum(other_pcts) / len(other_pcts)
        if not other_pcts:
            return sum(exam_pcts) / len(exam_pcts)
        return ew * (sum(exam_pcts) / len(exam_pcts)) + \
               (1 - ew) * (sum(other_pcts) / len(other_pcts))

    # ------------------------------------------------------------------
    # Distribution stats + trend chart
    # ------------------------------------------------------------------

    def _render_stats(self, percentages: list[float]):
        if not percentages:
            self.stats_var.set('—')
            return
        try:
            mean = statistics.mean(percentages)
            median = statistics.median(percentages)
            std = statistics.pstdev(percentages) if len(percentages) > 1 else 0.0
        except Exception:
            mean = median = std = 0.0
        self.stats_var.set(
            f"Count graded: {len(percentages)}\n"
            f"Mean:   {mean:6.1f}%\n"
            f"Median: {median:6.1f}%\n"
            f"Std:    {std:6.1f}\n"
            f"Best:   {max(percentages):6.1f}%\n"
            f"Worst:  {min(percentages):6.1f}%"
        )

    def _render_trend(self):
        c = self.trend_canvas
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or h < 30:
            return
        p = PALETTES.get(self.theme_var.get(), PALETTES['light'])

        # Collect (due_date, pct) pairs, in due-date order.
        points: list[tuple[str, float]] = []
        for r in self._rows:
            pct = self._row_percentage(r)
            if pct is None:
                continue
            d = r.get('due_date') or ''
            points.append((d, pct))
        points.sort()

        if len(points) < 2:
            c.create_text(w / 2, h / 2,
                          text='Not enough graded work to chart',
                          fill=p['subtle_fg'], font=('Arial', 10, 'italic'))
            return

        # Axes (% on Y, point index on X — index keeps spacing simple).
        margin = 30
        x0, y0 = margin, h - margin
        x1, y1 = w - 8, 8
        c.create_line(x0, y0, x1, y0, fill=p['chart_axis'])
        c.create_line(x0, y0, x0, y1, fill=p['chart_axis'])
        # Y-axis ticks
        for tick in (0, 25, 50, 75, 100):
            ty = y0 - (tick / 100.0) * (y0 - y1)
            c.create_line(x0 - 3, ty, x0, ty, fill=p['chart_axis'])
            c.create_text(x0 - 6, ty, text=str(tick),
                          fill=p['subtle_fg'], font=('Arial', 8), anchor='e')

        # Pass-mark reference line
        try:
            pass_mark = float(self.pass_mark_var.get())
        except Exception:
            pass_mark = DEFAULT_PASS_MARK_PCT
        py = y0 - (pass_mark / 100.0) * (y0 - y1)
        c.create_line(x0, py, x1, py, fill='#e74c3c', dash=(3, 3))

        # Plot
        n = len(points)
        coords: list[float] = []
        for i, (_d, pct) in enumerate(points):
            x = x0 + (i / max(n - 1, 1)) * (x1 - x0)
            y = y0 - (pct / 100.0) * (y0 - y1)
            coords.extend([x, y])
        c.create_line(*coords, fill=p['chart_line'], width=2, smooth=False)
        for i in range(0, len(coords), 2):
            c.create_oval(coords[i] - 3, coords[i + 1] - 3,
                          coords[i] + 3, coords[i + 1] + 3,
                          fill=p['chart_line'], outline=p['chart_line'])

    # ------------------------------------------------------------------
    # Selection-driven panels (feedback / rubric / class stats tooltip)
    # ------------------------------------------------------------------

    def _on_assignment_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            self._set_feedback('')
            self.rubric_btn.configure(state='disabled')
            return
        # Map iid back to row data via position.
        children = self.tree.get_children()
        try:
            idx = children.index(sel[0])
        except ValueError:
            return

        # Filtered rendering means iids may not 1:1 with self._rows.  Look
        # up by displayed values (module + title) to be safe.
        vals = self.tree.item(sel[0], 'values')
        module = vals[0] if vals else ''
        title = vals[1] if len(vals) > 1 else ''
        row = next(
            (r for r in self._rows
             if (r.get('module_code') or self._current_module) == module
             and (r.get('title') or '') == title),
            None,
        )
        if row is None and idx < len(self._rows):
            row = self._rows[idx]
        if row is None:
            return

        feedback = row.get('feedback') or ''
        # Append class-stats summary when available.
        stats = self._stats_cache.get(row.get('assessment_id'))
        if stats:
            feedback = (feedback + ('\n\n' if feedback else '')
                        + f"Class mean: {stats.get('mean'):.1f}, "
                          f"median: {stats.get('median'):.1f}, "
                          f"min/max: {stats.get('min_score'):.1f}/{stats.get('max_score'):.1f}")
        self._set_feedback(feedback)

        # Enable rubric button if the assignment has a rubric.
        self.rubric_btn.configure(
            state='normal' if row.get('rubric_id') else 'disabled')
        self._selected_row = row

    def _set_feedback(self, text: str):
        self.feedback_text.configure(state='normal')
        self.feedback_text.delete('1.0', 'end')
        self.feedback_text.insert('1.0', text or _t(
            'grades.no_feedback', '(no feedback)'))
        self.feedback_text.configure(state='disabled')

    # ------------------------------------------------------------------
    # Rubric drill-down (item 19)
    # ------------------------------------------------------------------

    def _show_rubric(self):
        row = getattr(self, '_selected_row', None)
        if not row or not row.get('rubric_id'):
            return
        try:
            with get_connection() as conn:
                criteria = conn.execute(
                    "SELECT criteria_name, description, max_points, weight "
                    "FROM rubric_criteria WHERE rubric_id = ? "
                    "ORDER BY display_order", (row['rubric_id'],),
                ).fetchall()
        except Exception as e:
            messagebox.showerror(_t('common.error', 'Error'),
                                 f"Failed to load rubric: {e}", parent=self.window)
            return
        if not criteria:
            messagebox.showinfo(_t('grades.rubric', 'Rubric'),
                                'No criteria found for this rubric.',
                                parent=self.window)
            return
        win = tk.Toplevel(self.window)
        win.title(f"Rubric — {row.get('title')}")
        win.geometry('640x400')
        cols = ('criterion', 'max', 'weight', 'description')
        tree = ttk.Treeview(win, columns=cols, show='headings')
        tree.heading('criterion', text='Criterion')
        tree.heading('max', text='Max')
        tree.heading('weight', text='Weight')
        tree.heading('description', text='Description')
        tree.column('criterion', width=160)
        tree.column('max', width=70, anchor='center')
        tree.column('weight', width=70, anchor='center')
        tree.column('description', width=320)
        for c in criteria:
            tree.insert('', tk.END, values=(
                c['criteria_name'], c['max_points'], c['weight'], c['description'] or '',
            ))
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Button(win, text='Close', command=win.destroy).pack(pady=(0, 8))

    # ------------------------------------------------------------------
    # What-if + target calculators (items 13, 14)
    # ------------------------------------------------------------------

    def _open_what_if(self):
        sel = self.tree.selection()
        if sel:
            self._open_what_if_for_selected()
            return
        messagebox.showinfo(
            _t('grades.what_if', 'What-If'),
            'Select an unmarked assignment first, then click What-If.',
            parent=self.window,
        )

    def _open_what_if_for_selected(self, *_):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], 'values')
        if not vals:
            return
        module, title = vals[0], vals[1]
        row = next(
            (r for r in self._rows
             if (r.get('module_code') or self._current_module) == module
             and (r.get('title') or '') == title),
            None,
        )
        if row is None or row.get('grade') is not None:
            return  # Don't override real grades.
        win = tk.Toplevel(self.window)
        win.title(f"What-If — {title}")
        win.geometry('340x140')
        win.transient(self.window)
        ttk.Label(win, text=f"Hypothetical % for '{title}':").pack(pady=(12, 4))
        var = tk.DoubleVar(value=self._what_if.get((module, title), 60.0))
        ttk.Spinbox(win, from_=0, to=100, increment=1, textvariable=var,
                    width=8).pack()

        def apply():
            self._what_if[(module, title)] = float(var.get())
            win.destroy()
            self._render_rows()

        def clear():
            self._what_if.pop((module, title), None)
            win.destroy()
            self._render_rows()

        bf = ttk.Frame(win); bf.pack(pady=10)
        ttk.Button(bf, text='Apply', command=apply).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text='Clear', command=clear).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text='Cancel', command=win.destroy).pack(side=tk.LEFT, padx=4)

    def _open_target(self):
        win = tk.Toplevel(self.window)
        win.title(_t('grades.target', 'Target Calculator'))
        win.geometry('420x220')
        win.transient(self.window)
        ttk.Label(win, text='What overall % do you want to hit?').pack(pady=(12, 4))
        target_var = tk.DoubleVar(value=70.0)
        ttk.Spinbox(win, from_=0, to=100, increment=1,
                    textvariable=target_var, width=8).pack()

        result_var = tk.StringVar(value='')
        ttk.Label(win, textvariable=result_var, wraplength=380,
                  justify='left', font=('Arial', 10)).pack(pady=12, padx=12)

        def compute():
            target = float(target_var.get())
            scored, unscored = [], []
            for r in self._rows:
                pct = self._row_percentage(r)
                w = float(r.get('weight') or 0.0) or 1.0
                if pct is not None:
                    scored.append((pct, w))
                else:
                    unscored.append(w)
            if not unscored:
                result_var.set('No remaining assignments — nothing to plan.')
                return
            current_w = sum(w for _, w in scored)
            current_score = sum(p * w for p, w in scored)
            remaining_w = sum(unscored) or 1.0
            # required_avg = (target * (current_w + remaining_w) - current_score) / remaining_w
            need = (target * (current_w + remaining_w) - current_score) / remaining_w
            line = (
                f"You currently have {current_score / current_w:.1f}% "
                f"across {len(scored)} graded assignment(s)."
                if current_w else
                "You have no graded marks yet."
            )
            verdict = (f"To reach {target:.0f}% you need to average "
                       f"{need:.1f}% on the remaining {len(unscored)} "
                       f"assignment(s).")
            if need > 100:
                verdict += "  ❌ Mathematically impossible at full marks."
            elif need <= 0:
                verdict += "  ✅ Already guaranteed."
            result_var.set(line + '\n\n' + verdict)
        ttk.Button(win, text='Compute', command=compute).pack()
        ttk.Button(win, text='Close', command=win.destroy).pack(pady=4)

    # ------------------------------------------------------------------
    # Export / share
    # ------------------------------------------------------------------

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self.window,
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            initialfile=f"grades_{self.student_id or 'student'}.csv",
            title='Export current view to CSV',
        )
        if not path:
            return
        try:
            cols = list(self._ASSIGNMENT_COLS)
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow([self._ASSIGNMENT_HEADINGS[c][0] for c in cols])
                for iid in self.tree.get_children():
                    w.writerow(self.tree.item(iid, 'values'))
            self.refresh_var.set(f'Exported {path}')
            try:
                log_activity(self.student_id, 'grades_breakdown_csv',
                             f'Exported CSV to {path}')
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror(_t('common.error', 'Error'),
                                 f'Failed to write CSV: {e}', parent=self.window)

    def _export_pdf(self):
        path = filedialog.asksaveasfilename(
            parent=self.window,
            defaultextension='.pdf',
            filetypes=[('PDF files', '*.pdf'), ('All files', '*.*')],
            initialfile=f"transcript_{self.student_id or 'student'}.pdf",
            title='Export grade transcript to PDF',
        )
        if not path:
            return
        try:
            # Best-effort: use the shared pdf_export ExportManager when present.
            from education_system.systems.university.services.pdf_export.export_manager import (
                ExportManager,
            )
            mgr = ExportManager()
            data = self._build_transcript_data()
            mgr.export_to_pdf(data, path, title='Grade Transcript')
        except ImportError:
            # Fallback: write a plain-text version with .pdf extension warning.
            messagebox.showinfo(
                'PDF export unavailable',
                'PDF export module not installed. Saving as plain text alongside.',
                parent=self.window,
            )
            try:
                with open(path + '.txt', 'w', encoding='utf-8') as f:
                    f.write(self._format_transcript_text())
                self.refresh_var.set(f'Saved {path}.txt')
            except Exception as e:
                messagebox.showerror(_t('common.error', 'Error'),
                                     f'Failed to write transcript: {e}',
                                     parent=self.window)
            return
        except Exception as e:
            messagebox.showerror(_t('common.error', 'Error'),
                                 f'Failed to export PDF: {e}',
                                 parent=self.window)
            return
        self.refresh_var.set(f'Exported {path}')
        try:
            log_activity(self.student_id, 'grades_breakdown_pdf',
                         f'Exported PDF transcript to {path}')
        except Exception:
            pass

    def _build_transcript_data(self) -> dict:
        return {
            'student_id': self.student_id,
            'name': self.display_name,
            'modules': [
                {
                    'code': m['module_code'],
                    'name': m['module_name'],
                    'credits': m.get('credits'),
                    'rows': self._assignments_cache.get(m['module_code'], []),
                }
                for m in self._modules
            ],
        }

    def _format_transcript_text(self) -> str:
        lines = [f"Grade Transcript for {self.display_name} ({self.student_id})"]
        for m in self._modules:
            lines.append(f"\n{m['module_code']} — {m['module_name']} "
                         f"({m.get('credits') or 0} credits)")
            for r in self._assignments_cache.get(m['module_code'], []):
                pct = self._row_percentage(r)
                pct_s = f"{pct:.1f}%" if pct is not None else "—"
                lines.append(f"  • {r.get('title')}  {pct_s}")
        return '\n'.join(lines)

    def _email_advisor(self):
        try:
            # Prefer the shared communications hub.
            from education_system.platform.integrations.email.email_service import send_email
        except Exception:
            messagebox.showinfo(
                _t('grades.email', 'Email advisor'),
                'Communications hub is not configured in this environment.',
                parent=self.window,
            )
            return
        # Stub: gather advisor address from the user record if present.
        advisor = None
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT advisor_email FROM users WHERE student_id = ?",
                    (self.student_id,),
                ).fetchone()
                advisor = row['advisor_email'] if row and 'advisor_email' in row.keys() else None
        except Exception:
            pass
        if not advisor:
            advisor = None  # let the user pick in the dialog below
        win = tk.Toplevel(self.window)
        win.title(_t('grades.email', 'Email advisor'))
        win.geometry('500x320')
        win.transient(self.window)
        ttk.Label(win, text='Advisor email:').pack(anchor='w', padx=8, pady=(8, 2))
        email_var = tk.StringVar(value=advisor or '')
        ttk.Entry(win, textvariable=email_var).pack(fill=tk.X, padx=8)
        ttk.Label(win, text='Message:').pack(anchor='w', padx=8, pady=(8, 2))
        body = tk.Text(win, height=8)
        body.insert('1.0', self._format_transcript_text())
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        def go():
            try:
                send_email(to=email_var.get(),
                           subject=f'Grades — {self.display_name}',
                           body=body.get('1.0', 'end'))
                self.refresh_var.set(f'Emailed {email_var.get()}')
                win.destroy()
            except Exception as e:
                messagebox.showerror(_t('common.error', 'Error'),
                                     f'Failed to send: {e}', parent=win)
        ttk.Button(win, text='Send', command=go).pack(pady=6)

    def _copy_selection(self):
        rows = self.tree.selection()
        if not rows:
            return
        cols = list(self._ASSIGNMENT_COLS)
        lines = ['\t'.join(self._ASSIGNMENT_HEADINGS[c][0] for c in cols)]
        for iid in rows:
            lines.append('\t'.join(str(v) for v in self.tree.item(iid, 'values')))
        text = '\n'.join(lines)
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(text)
            self.refresh_var.set(f'Copied {len(rows)} row(s) to clipboard')
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Sorting / tooltips / state
    # ------------------------------------------------------------------

    def _sort_tree(self, col):
        """Item 33 — click column header to sort ascending/descending."""
        items = [(self.tree.set(iid, col), iid) for iid in self.tree.get_children('')]
        # Try numeric sort first; fall back to string.
        try:
            items.sort(key=lambda t: float(t[0]) if t[0] not in ('--', '—', '') else float('inf'))
        except ValueError:
            items.sort()
        # Toggle direction by tracking last sort.
        if getattr(self, '_last_sort', None) == (col, 'asc'):
            items.reverse()
            self._last_sort = (col, 'desc')
        else:
            self._last_sort = (col, 'asc')
        for idx, (_v, iid) in enumerate(items):
            self.tree.move(iid, '', idx)

    def _sort_module_tree(self, col):
        items = []
        for iid in self.module_tree.get_children(''):
            if col == '#0':
                items.append((self.module_tree.item(iid, 'text'), iid))
            else:
                items.append((self.module_tree.set(iid, col), iid))
        items.sort()
        if getattr(self, '_last_msort', None) == (col, 'asc'):
            items.reverse()
            self._last_msort = (col, 'desc')
        else:
            self._last_msort = (col, 'asc')
        for idx, (_v, iid) in enumerate(items):
            self.module_tree.move(iid, '', idx)

    def _tooltip_for_event(self, event):
        """Return a tooltip string for the cell under the cursor, or None."""
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return None
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not iid or not col:
            return None
        col_idx = int(col.replace('#', '')) - 1
        try:
            value = self.tree.item(iid, 'values')[col_idx]
        except (IndexError, ValueError):
            return None
        # Only show when the text is plausibly truncated.
        return str(value) if value and len(str(value)) > 18 else None

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _set_loading(self, on: bool):
        if on:
            try:
                self._loading_label.place(relx=0.5, rely=0.5, anchor='center')
            except Exception:
                pass
        else:
            try:
                self._loading_label.place_forget()
            except Exception:
                pass

    def _set_empty_state(self, message: str):
        # Reuse the loading label as a generic placeholder.
        self._loading_label.configure(text=message)
        self._set_loading(True)

    def _refresh(self):
        """Item 24 — drop caches and re-load everything."""
        self._assignments_cache.clear()
        self._stats_cache.clear()
        self._all_rows = []
        self._load_modules()
        if self._current_module:
            self._load_assignments(self._current_module, force=True)

    def _refresh_modules_only(self):
        self._load_modules()

    def _recompute_summary(self):
        if self._rows or self._all_rows:
            self._render_rows()

    @staticmethod
    def _safe_float(val, default):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(val, default):
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _uk_classification(pct: float) -> str:
        if pct >= 70:
            return "First Class (1st)"
        if pct >= 60:
            return "Upper Second (2:1)"
        if pct >= 50:
            return "Lower Second (2:2)"
        if pct >= 40:
            return "Third Class (3rd)"
        return "Fail"
