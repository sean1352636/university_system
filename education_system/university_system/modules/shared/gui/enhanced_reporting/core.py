"""Enhanced reporting GUI — core module.

After modularisation this file contains only:

* shared imports (re-exported from ``standalone.constants``)
* the ``ReportingSystemGUI`` class (inheriting eight mixins and keeping
  only the __init__ / UI-setup methods)
* the ``TemplateDialog`` class
* the ``start_gui`` and ``start_enhanced_reporting_gui`` launcher functions
* backward-compatible re-exports so that every existing wrapper module
  (``misc.py``, ``utils.py``, ``template_dialog.py``, …) keeps working
  unchanged.
"""

from __future__ import annotations

# ── shared imports (also satisfy wrapper-file ``from .core import …``) ──────
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection  # noqa: F401
from education_system.university_system.core import paths  # noqa: F401

import logging
import os
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, filedialog, messagebox, simpledialog  # noqa: F401
from tkinter.scrolledtext import ScrolledText  # noqa: F401

from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,  # noqa: F401
    get_current_language,
    get_current_language_name,
    get_available_languages,  # noqa: F401
    get_available_language_list,  # noqa: F401
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,  # noqa: F401
)

# ── standalone constants & helpers ──────────────────────────────────────────
from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (
    DB_PATH,
    DEFAULT_DB_PATH,
    ENHANCED_AVAILABLE,
    CONFIG,
    get_db_connection,
    get_log_file,
    logger,
    pd,
)

# ── standalone function groups ──────────────────────────────────────────────
from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.data_utils import (
    serialize_dataframe,
    get_template,
    get_section_dataframe,
    get_correlation_data,
    get_trend_data,
    get_benchmark_data,
    get_original_section_data_complete,
)

from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.chart_builders import (
    create_advanced_visualization,
    create_interactive_chart,
    create_standard_chart,
    create_enhanced_pie_chart,
    create_enhanced_bar_chart,
    create_enhanced_line_chart,
    generate_statistical_summary,
    create_enhanced_data_table,
)

from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.report_generators import (
    generate_enhanced_pdf_report,
    generate_enhanced_section,
    generate_quality_section,
    generate_predictions_section,
    generate_enhanced_excel_report,
    generate_interactive_report,
)

from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.settings_functions import (
    show_directory_settings,
    show_theme_settings,
    validate_email_settings,
)

from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.system_ops import (
    run_system_maintenance,
    cleanup_old_reports,
    load_scheduled_reports,
    save_scheduled_reports,
    start_scheduler,
    send_report_email,
)

# Re-export service-layer symbols that the old core.py pulled in and that
# wrapper files may rely on transitively.
from education_system.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (  # noqa: F811
    ENHANCED_AVAILABLE as _EA,
)

if ENHANCED_AVAILABLE:
    from education_system.university_system.modules.shared.services.analytics.enhanced_reporting import (  # noqa: F401
        AdvancedScheduledReport, AdvancedVisualization, CacheManager,
        DataQualityMonitor, PredictiveAnalytics, ReportTemplate, SystemConfig,
        delete_template_from_db as _svc_delete_template_from_db,
        display_enhanced_reporting_menu as _svc_display_enhanced_reporting_menu,
        generate_report as _svc_generate_report,
        load_templates,
        save_template,
        save_template_dict,
        show_performance_monitor as _svc_show_performance_monitor,
    )
else:
    load_templates = lambda: []  # noqa: E731
    save_template = None
    save_template_dict = None
    _svc_delete_template_from_db = None
    _svc_display_enhanced_reporting_menu = None
    _svc_generate_report = None
    _svc_show_performance_monitor = None


# ── mixin imports ───────────────────────────────────────────────────────────
from education_system.university_system.modules.shared.gui.enhanced_reporting.mixins import (
    ApiHandlersMixin,
    TemplatesMixin,
    ReportsMixin,
    AnalyticsMixin,
    SchedulingMixin,
    DialogsMixin,
    MaintenanceMixin,
    ConfigMixin,
)


# ═══════════════════════════════════════════════════════════════════════════
#  ReportingSystemGUI — main GUI class
# ═══════════════════════════════════════════════════════════════════════════

class ReportingSystemGUI(
    ApiHandlersMixin,
    TemplatesMixin,
    ReportsMixin,
    AnalyticsMixin,
    SchedulingMixin,
    DialogsMixin,
    MaintenanceMixin,
    ConfigMixin,
):
    """Main GUI application for the Enhanced Reporting System"""

    def __init__(self, parent=None):
        # Initialize i18n system
        init_i18n()

        # If parent is provided, use it; otherwise create new root
        if parent is not None:
            self.root = parent
            self.is_embedded = True
        else:
            self.root = tk.Tk()
            self.root.title(_t("reporting.window_title"))
            self.root.geometry("1200x800")
            self.root.minsize(1000, 700)
            self.is_embedded = False

        # Configure style
        self.setup_styles()

        # Create main interface
        self.create_widgets()

        # Initialize data
        self.refresh_data()

        # Status for background operations
        self.background_tasks = []

    # ── thread-safe UI helper ───────────────────────────────────────────

    def _schedule_on_ui_thread(self, callback, delay=0):
        """Safely execute callbacks on the Tk main loop from worker threads."""
        if not callable(callback):
            return

        root = getattr(self, 'root', None)
        if root is None:
            return

        try:
            tk_app = getattr(root, 'tk', None)
            if tk_app is None:
                return
            try:
                if not root.winfo_exists():
                    return
            except tk.TclError:
                return

            root.after(delay, callback)
        except RuntimeError as exc:
            if 'main thread is not in main loop' in str(exc):
                return
            logging.error(f"Failed to schedule UI callback: {exc}")
        except tk.TclError:
            return

    # ── styling ─────────────────────────────────────────────────────────

    def setup_styles(self):
        """Configure the application styling"""
        style = ttk.Style()

        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground='#2E4E7E')
        style.configure('Subtitle.TLabel', font=('Arial', 12, 'bold'), foreground='#4A6FA5')
        style.configure('Info.TLabel', font=('Arial', 10), foreground='#666666')
        style.configure('Success.TLabel', font=('Arial', 10), foreground='#28A745')
        style.configure('Warning.TLabel', font=('Arial', 10), foreground='#FFC107')
        style.configure('Error.TLabel', font=('Arial', 10), foreground='#DC3545')

        style.configure('Primary.TButton', font=('Arial', 10, 'bold'))
        style.configure('Success.TButton', font=('Arial', 10, 'bold'))
        style.configure('Warning.TButton', font=('Arial', 10, 'bold'))

    # ── main widget creation ────────────────────────────────────────────

    def create_widgets(self):
        """Create the main GUI widgets"""
        top_bar = ttk.Frame(self.root)
        top_bar.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        self.lang_btn = ttk.Button(
            top_bar,
            text=f"🌐 {get_current_language_name()}",
            command=self._on_language_change
        )
        self.lang_btn.pack(side=tk.LEFT, padx=(0, 5))

        return_btn = ttk.Button(
            top_bar,
            text=f"🏠 {_t('reporting.return_to_menu')}",
            command=self.return_to_main_menu
        )
        return_btn.pack(side=tk.LEFT)

        if self.is_embedded:
            main_frame = self.root
        else:
            main_frame = ttk.Frame(self.root, padding="10")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        self.init_status_widgets(main_frame)
        if not self.is_embedded:
            self.layout_status_bar(main_frame)

        self.notebook = ttk.Notebook(main_frame)
        if self.is_embedded:
            self.notebook.pack(fill=tk.BOTH, expand=True)
        else:
            self.notebook.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))

        self.create_templates_tab()
        self.create_reports_tab()
        self.create_analytics_tab()
        self.create_schedule_tab()
        self.create_system_tab()

        if not self.is_embedded:
            self.create_status_bar(main_frame)

    # ── header ──────────────────────────────────────────────────────────

    def create_header(self, parent):
        """Create the application header"""
        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)

        title_label = ttk.Label(header_frame, text=_t("reporting.header_title", default="📊 Advanced Student Reporting System"),
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky=tk.W)

        if hasattr(self, 'auth'):
            return_button = ttk.Button(header_frame, text=_t("common.return_to_main_menu", default="🏠 Return to Main Menu"),
                                      command=self.return_to_main_menu)
            return_button.grid(row=0, column=2, sticky=tk.E, padx=10)

        subtitle_label = ttk.Label(header_frame,
                                  text=_t("reporting.header_subtitle", default="Generate comprehensive reports, analytics, and insights"),
                                  style='Subtitle.TLabel')
        subtitle_label.grid(row=1, column=0, sticky=tk.W)

        ttk.Button(header_frame, text=_t("common.return_to_main_menu", default="🏠 Return to Main Menu"),
                  command=self.return_to_main_menu).grid(row=0, column=1, sticky=tk.E)

        if not hasattr(self, 'status_indicator'):
            self.status_indicator = ttk.Label(header_frame, text=_t("reporting.system_ready", default="● System Ready"),
                                             style='Success.TLabel')
        self.status_indicator.grid(row=0, column=1, sticky=tk.E)

        actions_frame = ttk.Frame(header_frame)
        actions_frame.grid(row=1, column=1, sticky=tk.E)

        ttk.Button(actions_frame, text=_t("common.refresh", default="🔄 Refresh"),
                  command=self.refresh_data).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(actions_frame, text=_t("common.settings", default="⚙️ Settings"),
                  command=self.show_settings).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(actions_frame, text=_t("reporting.start_api", default="🌐 Start API"),
                  command=self.start_api_server).pack(side=tk.LEFT, padx=(5, 0))

    # ── tab: templates ──────────────────────────────────────────────────

    def create_templates_tab(self):
        """Create the templates management tab"""
        template_frame = ttk.Frame(self.notebook)
        self.notebook.add(template_frame, text=f"📋 {_t('reporting.tabs.templates')}")

        template_frame.columnconfigure(1, weight=1)
        template_frame.rowconfigure(1, weight=1)

        left_panel = ttk.LabelFrame(template_frame, text=_t("reporting.templates.available"), padding="10")
        left_panel.grid(row=0, column=0, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)

        listbox_frame = ttk.Frame(left_panel)
        listbox_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        listbox_frame.columnconfigure(0, weight=1)
        listbox_frame.rowconfigure(0, weight=1)

        self.template_listbox = tk.Listbox(listbox_frame, height=15)
        self.template_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.template_listbox.bind('<<ListboxSelect>>', self.on_template_select)

        template_scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL,
                                          command=self.template_listbox.yview)
        template_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.template_listbox.config(yscrollcommand=template_scrollbar.set)

        template_actions = ttk.Frame(left_panel)
        template_actions.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(template_actions, text=f"➕ {_t('reporting.templates.new')}", command=self.create_template_dialog, style='Primary.TButton').pack(fill=tk.X, pady=(0, 5))
        ttk.Button(template_actions, text=f"🔄 {_t('reporting.templates.refresh')}", command=self.refresh_templates).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(template_actions, text=f"📝 {_t('reporting.templates.edit')}", command=self.edit_template_dialog).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(template_actions, text=f"🗑️ {_t('reporting.templates.delete')}", command=self.delete_template).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(template_actions, text=f"📥 {_t('reporting.templates.import')}", command=self.import_template_dialog).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(template_actions, text=f"📤 {_t('reporting.templates.export')}",
                  command=self.export_template).pack(fill=tk.X)

        right_panel = ttk.LabelFrame(template_frame, text=_t("reporting.templates.details"), padding="10")
        right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)

        self.template_details = ScrolledText(right_panel, height=20, wrap=tk.WORD)
        self.template_details.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        preview_actions = ttk.Frame(template_frame)
        preview_actions.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(preview_actions, text=f"👁️ {_t('reporting.templates.preview')}",
                  command=self.preview_template).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(preview_actions, text=f"📊 {_t('reporting.templates.generate_report')}",
                  command=self.generate_from_template,
                  style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(preview_actions, text=f"🔄 {_t('reporting.templates.duplicate')}",
                  command=self.duplicate_template).pack(side=tk.LEFT)
        ttk.Button(template_actions, text=f"🏠 {_t('reporting.return_to_menu')}",
                   command=self.return_to_main_menu).pack(fill=tk.X, pady=(0, 5))

    # ── tab: reports ────────────────────────────────────────────────────

    def create_reports_tab(self):
        """Create the reports generation tab"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text=f"📊 {_t('reporting.tabs.reports')}")

        reports_frame.columnconfigure(0, weight=1)
        reports_frame.rowconfigure(1, weight=1)

        gen_frame = ttk.LabelFrame(reports_frame, text=_t("reporting.reports.generate"), padding="10")
        gen_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        gen_frame.columnconfigure(1, weight=1)

        ttk.Label(gen_frame, text=f"{_t('reporting.reports.template')}:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.template_combo = ttk.Combobox(gen_frame, state="readonly")
        self.template_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        ttk.Label(gen_frame, text=f"{_t('reporting.reports.start_date')}:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        date_frame = ttk.Frame(gen_frame)
        date_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        self.start_date = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.start_date, width=12).pack(side=tk.LEFT)

        ttk.Label(date_frame, text=f"{_t('reporting.reports.end_date')}:").pack(side=tk.LEFT, padx=(20, 5))
        self.end_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.end_date, width=12).pack(side=tk.LEFT)

        ttk.Label(gen_frame, text=f"{_t('reporting.reports.format')}:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        self.format_combo = ttk.Combobox(gen_frame, values=["PDF", "Excel", "Interactive HTML"],
                                        state="readonly")
        self.format_combo.set("PDF")
        self.format_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        generate_btn = ttk.Button(gen_frame, text=f"🚀 {_t('reporting.reports.generate_btn')}",
                                 command=self.generate_report,
                                 style='Success.TButton')
        generate_btn.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        history_frame = ttk.LabelFrame(reports_frame, text=_t("reporting.reports.recent"), padding="10")
        history_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)

        columns = ('Name', 'Generated', 'Format', 'Size', 'Status')
        col_texts = [
            _t('reporting.reports.col_name'),
            _t('reporting.reports.col_generated'),
            _t('reporting.reports.col_format'),
            _t('reporting.reports.col_size'),
            _t('reporting.reports.col_status')
        ]
        self.reports_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=15)

        for col, text in zip(columns, col_texts):
            self.reports_tree.heading(col, text=text)
            self.reports_tree.column(col, width=150)

        self.reports_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        reports_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL,
                                         command=self.reports_tree.yview)
        reports_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.reports_tree.config(yscrollcommand=reports_scrollbar.set)

        reports_actions = ttk.Frame(history_frame)
        reports_actions.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(reports_actions, text=f"📁 {_t('reporting.reports.open')}",
                  command=self.open_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(reports_actions, text=f"📤 {_t('reporting.reports.share')}",
                  command=self.share_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(reports_actions, text=f"🗑️ {_t('reporting.reports.delete')}",
                  command=self.delete_report).pack(side=tk.LEFT)

        ttk.Button(reports_actions, text=f"🔄 {_t('reporting.reports.refresh')}",
                  command=self.refresh_reports).pack(side=tk.RIGHT)

    # ── tab: analytics ──────────────────────────────────────────────────

    def create_analytics_tab(self):
        """Create the analytics dashboard tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text=f"📈 {_t('reporting.tabs.analytics')}")

        analytics_frame.columnconfigure(0, weight=1)
        analytics_frame.columnconfigure(1, weight=1)
        analytics_frame.rowconfigure(1, weight=1)

        overview_frame = ttk.LabelFrame(analytics_frame, text=_t("reporting.analytics.system_overview"), padding="10")
        overview_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        overview_frame.columnconfigure(0, weight=1)
        overview_frame.columnconfigure(1, weight=1)
        overview_frame.columnconfigure(2, weight=1)
        overview_frame.columnconfigure(3, weight=1)

        self.create_overview_card(overview_frame, f"👥 {_t('reporting.analytics.total_students')}", "0", 0, 0)
        self.create_overview_card(overview_frame, f"📚 {_t('reporting.analytics.total_courses')}", "0", 0, 1)
        self.create_overview_card(overview_frame, f"📋 {_t('reporting.analytics.templates_count')}", "0", 0, 2)
        self.create_overview_card(overview_frame, f"📊 {_t('reporting.analytics.reports_generated')}", "0", 0, 3)

        self.root.after(100, self.update_overview_cards)

        quality_frame = ttk.LabelFrame(analytics_frame, text=_t("reporting.analytics.data_quality"), padding="10")
        quality_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        quality_frame.columnconfigure(0, weight=1)
        quality_frame.rowconfigure(1, weight=1)

        self.quality_display = ScrolledText(quality_frame, height=15, wrap=tk.WORD)
        self.quality_display.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        quality_actions = ttk.Frame(quality_frame)
        quality_actions.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(quality_actions, text=f"🔄 {_t('reporting.analytics.run_quality_check')}",
                  command=self.run_quality_check).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quality_actions, text=f"📊 {_t('reporting.analytics.export_quality_report')}",
                  command=self.export_quality_report).pack(side=tk.LEFT)

        predictions_frame = ttk.LabelFrame(analytics_frame, text=_t("reporting.analytics.predictive"), padding="10")
        predictions_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        predictions_frame.columnconfigure(0, weight=1)
        predictions_frame.rowconfigure(1, weight=1)

        self.predictions_display = ScrolledText(predictions_frame, height=15, wrap=tk.WORD)
        self.predictions_display.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        predictions_actions = ttk.Frame(predictions_frame)
        predictions_actions.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(predictions_actions, text=f"🎯 {_t('reporting.analytics.run_predictions')}",
                  command=self.run_predictions).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(predictions_actions, text=f"🔍 {_t('reporting.analytics.anomaly_detection')}",
                  command=self.run_anomaly_detection).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(predictions_actions, text=f"📈 {_t('reporting.analytics.correlation_analysis')}",
                  command=self.run_correlation_analysis).pack(side=tk.LEFT)

    # ── tab: scheduling ─────────────────────────────────────────────────

    def create_schedule_tab(self):
        """Create the scheduling tab"""
        schedule_frame = ttk.Frame(self.notebook)
        self.notebook.add(schedule_frame, text=f"⏰ {_t('reporting.tabs.scheduling')}")

        schedule_frame.columnconfigure(0, weight=1)
        schedule_frame.rowconfigure(1, weight=1)

        create_frame = ttk.LabelFrame(schedule_frame, text=_t("reporting.scheduling.create"), padding="10")
        create_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        create_frame.columnconfigure(1, weight=1)

        ttk.Label(create_frame, text=f"{_t('reporting.scheduling.template')}:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.schedule_template_combo = ttk.Combobox(create_frame, state="readonly")
        self.schedule_template_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        ttk.Label(create_frame, text=f"{_t('reporting.scheduling.frequency')}:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.frequency_combo = ttk.Combobox(create_frame,
                                           values=[_t("reporting.scheduling.daily"), _t("reporting.scheduling.weekly"), _t("reporting.scheduling.monthly")],
                                           state="readonly")
        self.frequency_combo.set(_t("reporting.scheduling.weekly"))
        self.frequency_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        ttk.Label(create_frame, text=f"{_t('reporting.scheduling.time')}:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        time_frame = ttk.Frame(create_frame)
        time_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        self.hour_var = tk.StringVar(value="09")
        hour_spin = ttk.Spinbox(time_frame, from_=0, to=23, width=3,
                               textvariable=self.hour_var, format="%02.0f")
        hour_spin.pack(side=tk.LEFT)
        ttk.Label(time_frame, text=":00").pack(side=tk.LEFT)

        ttk.Label(create_frame, text=f"{_t('reporting.scheduling.email_recipients')}:").grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        self.recipients_entry = tk.Text(create_frame, height=3, width=40)
        self.recipients_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        ttk.Button(create_frame, text=f"📅 {_t('reporting.scheduling.create_btn')}",
                  command=self.create_schedule,
                  style='Primary.TButton').grid(row=4, column=0, columnspan=2, pady=(10, 0))

        scheduled_frame = ttk.LabelFrame(schedule_frame, text=_t("reporting.scheduling.scheduled_reports"), padding="10")
        scheduled_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scheduled_frame.columnconfigure(0, weight=1)
        scheduled_frame.rowconfigure(0, weight=1)

        schedule_columns = ('Template', 'Frequency', 'Time', 'Recipients', 'Last Run', 'Status')
        schedule_col_texts = [
            _t('reporting.scheduling.col_template'),
            _t('reporting.scheduling.col_frequency'),
            _t('reporting.scheduling.col_time'),
            _t('reporting.scheduling.col_recipients'),
            _t('reporting.scheduling.col_last_run'),
            _t('reporting.scheduling.col_status')
        ]
        self.schedule_tree = ttk.Treeview(scheduled_frame, columns=schedule_columns,
                                         show='headings', height=15)

        for col, text in zip(schedule_columns, schedule_col_texts):
            self.schedule_tree.heading(col, text=text)
            self.schedule_tree.column(col, width=120)

        self.schedule_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        schedule_scrollbar = ttk.Scrollbar(scheduled_frame, orient=tk.VERTICAL,
                                          command=self.schedule_tree.yview)
        schedule_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.schedule_tree.config(yscrollcommand=schedule_scrollbar.set)

        schedule_actions = ttk.Frame(scheduled_frame)
        schedule_actions.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(schedule_actions, text=f"▶️ {_t('reporting.scheduling.enable_disable')}",
                  command=self.toggle_schedule).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(schedule_actions, text=f"✏️ {_t('reporting.scheduling.edit')}",
                  command=self.edit_schedule).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(schedule_actions, text=f"🚀 {_t('reporting.scheduling.run_now')}",
                  command=self.run_schedule_now).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(schedule_actions, text=f"🗑️ {_t('reporting.scheduling.delete')}",
                  command=self.delete_schedule).pack(side=tk.LEFT)

    # ── tab: system ─────────────────────────────────────────────────────

    def create_system_tab(self):
        """Create the system management tab"""
        system_frame = ttk.Frame(self.notebook)
        self.notebook.add(system_frame, text=f"⚙️ {_t('reporting.tabs.system')}")

        system_frame.columnconfigure(0, weight=1)
        system_frame.columnconfigure(1, weight=1)
        system_frame.rowconfigure(1, weight=1)

        status_frame = ttk.LabelFrame(system_frame, text=_t("reporting.system.status"), padding="10")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)

        self.system_status = ttk.Label(
            status_frame,
            text=_t("reporting.system.checking_status"),
            style='Info.TLabel'
        )
        self.system_status.grid(row=0, column=0, sticky=tk.W)

        maintenance_frame = ttk.LabelFrame(system_frame, text=_t("reporting.system.maintenance"), padding="10")
        maintenance_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        maintenance_frame.columnconfigure(0, weight=1)

        maintenance_actions = [
            (f"🧹 {_t('reporting.system.clean_old_reports')}", self.clean_old_reports),
            (f"🗄️ {_t('reporting.system.clear_cache')}", self.clear_cache),
            (f"🔍 {_t('reporting.system.run_quality_check')}", self.run_maintenance_quality_check),
            (f"🗃️ {_t('reporting.system.optimize_database')}", self.optimize_database),
            (f"🔧 {_t('reporting.system.run_all_maintenance')}", self.run_all_maintenance),
            (f"📊 {_t('reporting.system.performance_monitor')}", self.show_performance_monitor),
            (f"📄 {_t('reporting.system.export_logs')}", self.export_system_logs),
        ]
        for i, (text, command) in enumerate(maintenance_actions):
            ttk.Button(maintenance_frame, text=text, command=command).grid(
                row=i, column=0, sticky=(tk.W, tk.E), pady=(0, 5)
            )

        config_frame = ttk.LabelFrame(system_frame, text=_t("reporting.system.configuration"), padding="10")
        config_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        config_frame.columnconfigure(0, weight=1)
        config_frame.rowconfigure(0, weight=1)

        self.config_display = ScrolledText(config_frame, height=20, wrap=tk.WORD)
        self.config_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        config_actions = ttk.Frame(config_frame)
        config_actions.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(config_actions, text=f"🔄 {_t('reporting.system.reload_config')}", command=self.reload_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(config_actions, text=f"💾 {_t('reporting.system.save_config')}", command=self.save_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(config_actions, text=f"🔧 {_t('reporting.system.advanced_settings')}", command=self.show_advanced_settings).pack(side=tk.LEFT)

    # ── status bar helpers ──────────────────────────────────────────────

    def layout_status_bar(self, parent):
        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)

        title_label = ttk.Label(header_frame, text=f"📊 {_t('reporting.title')}",
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky=tk.W)

        if hasattr(self, 'auth'):
            return_button = ttk.Button(header_frame, text=f"🏠 {_t('reporting.return_to_menu')}",
                                      command=self.return_to_main_menu)
            return_button.grid(row=0, column=1, sticky=tk.E)

        self._status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        self._status_frame.columnconfigure(1, weight=1)
        self.status_text.grid(row=0, column=0, sticky=tk.W)
        self.progress.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 10))
        ttk.Label(self._status_frame, text=_t("reporting.version"), style='Info.TLabel').grid(row=0, column=2, sticky=tk.E)

    def create_overview_card(self, parent, title, value, row, col):
        """Create an overview card widget"""
        card_frame = ttk.Frame(parent, relief='solid', borderwidth=1)
        card_frame.grid(row=row, column=col, sticky=(tk.W, tk.E), padx=5, pady=5)
        card_frame.columnconfigure(0, weight=1)

        title_label = ttk.Label(card_frame, text=title, style='Subtitle.TLabel')
        title_label.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=(10, 5))

        value_label = ttk.Label(card_frame, text=value, font=('Arial', 20, 'bold'))
        value_label.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=(0, 10))

        if "Students" in title:
            self.overview_students = value_label
        elif "Courses" in title:
            self.overview_courses = value_label
        elif "Templates" in title:
            self.overview_templates = value_label
        elif "Reports" in title:
            self.overview_reports = value_label

    def init_status_widgets(self, parent):
        self._status_frame = ttk.Frame(parent)
        self.status_text = ttk.Label(self._status_frame, text=_t("reporting.ready"), style='Info.TLabel')
        self.progress = ttk.Progressbar(self._status_frame, mode='indeterminate')
        self.status_indicator = ttk.Label(self._status_frame, text=f"● {_t('reporting.system_ready')}", style='Success.TLabel')

    # ── navigation ──────────────────────────────────────────────────────

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            from education_system.university_system.modules.shared.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            logging.error(f"Error returning to main menu: {e}")
            import traceback
            logging.debug(traceback.format_exc())

    # ── language change ─────────────────────────────────────────────────

    def _on_language_change(self):
        """Handle language change request"""
        old_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()

        if old_lang != new_lang:
            self.lang_btn.config(text=f"🌐 {get_current_language_name()}")
            messagebox.showinfo(
                _t("reporting.language.changed"),
                _t("reporting.language.restart_required")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh all UI text elements with current language translations"""
        try:
            if not self.is_embedded:
                self.root.title(_t("reporting.window_title"))

            self.notebook.tab(0, text=f"📋 {_t('reporting.tabs.templates')}")
            self.notebook.tab(1, text=f"📊 {_t('reporting.tabs.reports')}")
            self.notebook.tab(2, text=f"📈 {_t('reporting.tabs.analytics')}")
            self.notebook.tab(3, text=f"⏰ {_t('reporting.tabs.scheduling')}")
            self.notebook.tab(4, text=f"⚙️ {_t('reporting.tabs.system')}")

            if hasattr(self, 'status_text'):
                self.status_text.config(text=_t("reporting.ready"))
            if hasattr(self, 'status_indicator'):
                self.status_indicator.config(text=f"● {_t('reporting.system_ready')}")

            logging.info("UI language refreshed successfully")
        except Exception as e:
            logging.error(f"Error refreshing UI language: {e}")

    # ── data refresh ────────────────────────────────────────────────────

    def refresh_data(self):
        """Refresh all data in the GUI"""
        self.update_status("Refreshing data...")
        self.start_progress()

        def refresh_task():
            try:
                self.load_templates()
                self.load_scheduled_reports()
                self.load_recent_reports()
                self.update_overview_cards()
                self.check_system_status()

                self._schedule_on_ui_thread(lambda: [
                    self.stop_progress(),
                    self.update_status("Data refreshed successfully")
                ])

            except Exception as e:
                err_msg = str(e)
                self._schedule_on_ui_thread(lambda: [
                    self.update_status(f"Error refreshing data: {err_msg}", "error")
                ])

        threading.Thread(target=refresh_task, daemon=True).start()

    def create_status_bar(self, parent):
        """Create status bar with all system information"""
        if not self.is_embedded:
            self._status_frame = ttk.Frame(parent)
            self._status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
            self._status_frame.columnconfigure(1, weight=1)

            self.status_text = ttk.Label(self._status_frame, text="Ready", style='Info.TLabel')
            self.status_text.grid(row=0, column=0, sticky=tk.W)

            self.progress = ttk.Progressbar(self._status_frame, mode='indeterminate')
            self.progress.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 10))

            system_info = f"v2.0 | Enhanced: {'Yes' if ENHANCED_AVAILABLE else 'No'}"
            ttk.Label(self._status_frame, text=system_info, style='Info.TLabel').grid(row=0, column=2, sticky=tk.E)

    def complete_system_tab_config_display(self):
        """Complete the configuration display area in system tab"""
        self.config_display = ScrolledText(config_display_frame, height=10, wrap=tk.WORD)
        self.config_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        config_actions_bottom = ttk.Frame(config_display_frame)
        config_actions_bottom.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(config_actions_bottom, text="Reload Config",
                  command=self.reload_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(config_actions_bottom, text="Save Config",
                  command=self.save_config).pack(side=tk.LEFT, padx=(0, 5))


# ═══════════════════════════════════════════════════════════════════════════
#  TemplateDialog
# ═══════════════════════════════════════════════════════════════════════════

class TemplateDialog:
    """Dialog for creating and editing templates"""

    def __init__(self, parent, title="Template Dialog", template_data=None):
        self.result = None
        self.template_data = template_data

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"700x600+{x}+{y}")

        self.create_widgets()

        if template_data:
            self.populate_fields()

        self.dialog.wait_window()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=1)

        basic_frame = ttk.LabelFrame(main_frame, text=_t("enhanced_reporting.template_dialog.basic_information"), padding="10")
        basic_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        basic_frame.columnconfigure(1, weight=1)

        ttk.Label(basic_frame, text=_t("enhanced_reporting.template_dialog.name_required")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.name_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.name_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        ttk.Label(basic_frame, text=_t("enhanced_reporting.template_dialog.description")).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.description_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.description_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        ttk.Label(basic_frame, text=_t("enhanced_reporting.template_dialog.security_level")).grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        self.security_var = tk.StringVar(value="normal")
        security_combo = ttk.Combobox(basic_frame, textvariable=self.security_var,
                                     values=["normal", "confidential", "restricted"], state="readonly")
        security_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        ttk.Label(basic_frame, text=_t("enhanced_reporting.template_dialog.visualization")).grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        self.viz_var = tk.StringVar(value="standard")
        viz_combo = ttk.Combobox(basic_frame, textvariable=self.viz_var,
                                values=["standard", "advanced", "interactive"], state="readonly")
        viz_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        sections_frame = ttk.LabelFrame(main_frame, text=_t("enhanced_reporting.template_dialog.report_sections"), padding="10")
        sections_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        sections_frame.columnconfigure(0, weight=1)
        sections_frame.rowconfigure(1, weight=1)

        sections_canvas_frame = ttk.Frame(sections_frame)
        sections_canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        sections_canvas_frame.columnconfigure(0, weight=1)
        sections_canvas_frame.rowconfigure(0, weight=1)

        sections_canvas = tk.Canvas(sections_canvas_frame, height=200)
        sections_scrollbar = ttk.Scrollbar(sections_canvas_frame, orient="vertical", command=sections_canvas.yview)
        scrollable_frame = ttk.Frame(sections_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: sections_canvas.configure(scrollregion=sections_canvas.bbox("all"))
        )

        sections_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        sections_canvas.configure(yscrollcommand=sections_scrollbar.set)

        sections_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        sections_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.section_vars = {}
        available_sections = [
            "student_overview", "course_distribution", "gender_distribution",
            "age_distribution", "registration_trends", "module_popularity",
            "grade_distribution", "attendance_summary", "data_quality_report",
            "predictive_analytics", "correlation_analysis", "anomaly_detection",
            "performance_benchmarks", "trend_analysis"
        ]

        for i, section in enumerate(available_sections):
            var = tk.BooleanVar()
            self.section_vars[section] = var
            section_name = section.replace('_', ' ').title()
            ttk.Checkbutton(scrollable_frame, text=section_name, variable=var).grid(
                row=i // 2, column=i % 2, sticky=tk.W, padx=10, pady=2)

        select_frame = ttk.Frame(sections_frame)
        select_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(select_frame, text=_t("enhanced_reporting.buttons.select_all"), command=self.select_all_sections).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(select_frame, text=_t("enhanced_reporting.buttons.deselect_all"), command=self.deselect_all_sections).pack(side=tk.LEFT)

        filters_frame = ttk.LabelFrame(main_frame, text=_t("enhanced_reporting.template_dialog.filters_optional"), padding="10")
        filters_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        filters_frame.columnconfigure(1, weight=1)

        ttk.Label(filters_frame, text=_t("enhanced_reporting.template_dialog.course")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.course_var = tk.StringVar()
        course_combo = ttk.Combobox(filters_frame, textvariable=self.course_var,
                                   values=["", "CS", "DS"], state="readonly")
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))

        ttk.Label(filters_frame, text=_t("enhanced_reporting.template_dialog.date_range_days")).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.date_range_var = tk.StringVar(value="30")
        ttk.Entry(filters_frame, textvariable=self.date_range_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(0, 5))

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(button_frame, text=_t("enhanced_reporting.buttons.cancel"), command=self.cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text=_t("enhanced_reporting.buttons.save_template"), command=self.save_template,
                  style='Primary.TButton').pack(side=tk.RIGHT)

    def populate_fields(self):
        """Populate fields with existing template data"""
        if not self.template_data:
            return

        self.name_var.set(self.template_data.get('name', ''))
        self.description_var.set(self.template_data.get('description', ''))
        self.security_var.set(self.template_data.get('security_level', 'normal'))
        self.viz_var.set(self.template_data.get('visualization_type', 'standard'))

        template_sections = self.template_data.get('sections', [])
        for section, var in self.section_vars.items():
            var.set(section in template_sections)

        filters = self.template_data.get('filters', {})
        self.course_var.set(filters.get('course', ''))
        self.date_range_var.set(str(filters.get('date_range_days', 30)))

    def select_all_sections(self):
        """Select all sections"""
        for var in self.section_vars.values():
            var.set(True)

    def deselect_all_sections(self):
        """Deselect all sections"""
        for var in self.section_vars.values():
            var.set(False)

    def save_template(self):
        """Save the template"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror(_t("enhanced_reporting.messages.validation_error"), _t("enhanced_reporting.messages.template_name_required"))
            return

        selected_sections = [section for section, var in self.section_vars.items() if var.get()]
        if not selected_sections:
            messagebox.showerror(_t("enhanced_reporting.messages.validation_error"), _t("enhanced_reporting.messages.section_required"))
            return

        filters = {}
        if self.course_var.get():
            filters['course'] = self.course_var.get()

        try:
            date_range = int(self.date_range_var.get())
            if date_range > 0:
                filters['date_range_days'] = date_range
        except ValueError:
            pass

        template_data = {
            'name': name,
            'description': self.description_var.get().strip(),
            'sections': selected_sections,
            'filters': filters,
            'security_level': self.security_var.get(),
            'visualization_type': self.viz_var.get(),
            'created_at': datetime.now().isoformat(),
            'version': '1.0'
        }

        if self.template_data:
            template_data['created_at'] = self.template_data.get('created_at', datetime.now().isoformat())
            old_version = self.template_data.get('version', '1.0')
            try:
                major, minor = old_version.split('.')
                template_data['version'] = f"{major}.{int(minor) + 1}"
            except Exception:
                template_data['version'] = '1.1'

        try:
            if ENHANCED_AVAILABLE:
                save_template_dict(template_data)

            self.result = template_data
            messagebox.showinfo("Success", f"Template '{name}' saved successfully!")
            self.dialog.destroy()

        except Exception as e:
            logging.error(f"Failed to save template: {e}")
            import traceback
            logging.error(traceback.format_exc())
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")

    def cancel(self):
        """Cancel dialog"""
        self.dialog.destroy()


# ═══════════════════════════════════════════════════════════════════════════
#  Launcher functions
# ═══════════════════════════════════════════════════════════════════════════

def start_gui():
    """Start the GUI application"""
    init_i18n()

    root = tk.Tk()

    try:
        pass
    except Exception:
        pass

    app = ReportingSystemGUI(root)

    def on_closing():
        if messagebox.askokcancel(_t("reporting.dialogs.quit"), _t("reporting.dialogs.quit_confirm")):
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


def start_enhanced_reporting_gui():
    """
    Start the enhanced reporting system with GUI
    Maintains backward compatibility with existing CLI system
    """
    print("🖥️  Starting Enhanced Reporting System GUI...")

    if ENHANCED_AVAILABLE:
        print("✅ Enhanced features loaded successfully")

        try:
            conn = get_db_connection()
            conn.close()
            print("✅ Database connection verified")

            for dir_path in [CONFIG['reports_dir'], CONFIG['templates_dir'], CONFIG['cache_dir']]:
                os.makedirs(dir_path, exist_ok=True)
            print("✅ Directories initialized")

            try:
                start_scheduler()
                print("✅ Background scheduler started")
            except Exception as e:
                print(f"⚠️  Background scheduler failed: {str(e)}")

        except Exception as e:
            print(f"⚠️  System initialization warning: {str(e)}")
    else:
        print("⚠️  Enhanced features not available - running in basic mode")

    print("🚀 Launching GUI...")

    try:
        import tkinter.messagebox as mb
        choice = mb.askyesnocancel(
            "Enhanced Reporting System",
            "Choose interface:\n\nYes - Start GUI\nNo - Start CLI\nCancel - Exit",
            icon='question'
        )

        if choice is True:
            start_gui()
        elif choice is False:
            if ENHANCED_AVAILABLE:
                _svc_display_enhanced_reporting_menu()
            else:
                print("CLI mode requires enhanced features")

    except ImportError:
        print("GUI not available, starting CLI...")
        if ENHANCED_AVAILABLE:
            _svc_display_enhanced_reporting_menu()
        else:
            print("Enhanced features not available")


# Main execution
if __name__ == "__main__":
    start_enhanced_reporting_gui()
