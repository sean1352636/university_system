"""
Business Intelligence Reports GUI

Full-featured Tkinter interface for creating, managing, and exporting BI reports
with visualizations, scheduled reports, and custom metrics.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime
from typing import Optional
import csv
import json

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.services.business_intelligence.bi_reports_core import (
    ReportDefinitionManager,
    ReportExportManager,
    ReportScheduleManager,
    VisualizationManager,
    CustomMetricManager
)
from education_system.university_system.modules.shared.utils.i18n import get_text as _t, _


class BusinessIntelligenceGUI:
    """Business Intelligence Reports GUI Application"""

    def __init__(self, root, auth):
        """Initialize the BI Reports GUI"""
        self.root = root
        self.auth = auth

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.messages.login_required"))
            return

        self.window = tk.Toplevel(root)
        self.window.title(_t("business_intelligence.window_title"))
        self.window.geometry("1200x800")
        self.window.minsize(1000, 600)

        # Initialize database tables
        self._init_database()

        # Setup UI
        self._create_widgets()

        # Log activity
        log_activity('Accessed Business Intelligence Reports Dashboard', user=self.auth.current_user.get('username'))
        print(_t("business_intelligence.messages.gui_opened_success"))

        try:
            self.window.after_idle(self._apply_eqa_context)
        except Exception:
            pass

    def _apply_eqa_context(self):
        """#5 — Honour an EQA drill-through. When ``kpi_category`` is
        present, scope the dashboard to that category by stashing the
        request on ``self.bi_category_filter`` so report queries can
        read it; emit a banner so the user sees it took effect."""
        ctx = getattr(self, "eqa_context", None)
        if not ctx:
            return
        try:
            cat = ctx.get("kpi_category")
            if cat:
                self.bi_category_filter = cat
                import tkinter as _tk
                _tk.Label(
                    self.window,
                    text=f"Filtered to KPI category: {cat} (from EQA)",
                    bg="#fff7d6", fg="#5a4500",
                    font=("Helvetica", 9, "italic"), pady=3,
                ).pack(fill="x", side="top", before=None)
        except Exception:
            pass

    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            from education_system.university_system.infrastructure.database.schemas.analytics_bi_schemas import init_business_intelligence_system_db
            init_business_intelligence_system_db()
        except ImportError as e:
            print(_t("business_intelligence.messages.schema_import_warning", error=e))
        except Exception as e:
            print(_t("business_intelligence.messages.database_init_error", error=e))
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.messages.database_init_warning", error=e))

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text=_t("business_intelligence.window_title"),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        user_label = ttk.Label(
            header_frame,
            text=f"{_t('common.user')}: {self.auth.current_user.get('username', 'Unknown')}",
            font=('Arial', 10)
        )
        user_label.pack(side=tk.RIGHT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self._create_reports_tab()
        self._create_exports_tab()
        self._create_schedules_tab()
        self._create_visualizations_tab()
        self._create_metrics_tab()

        # Close button
        ttk.Button(
            main_frame,
            text=_t("common.close"),
            command=self.window.destroy
        ).pack(pady=(10, 0))

    def _create_reports_tab(self):
        """Create Report Definitions tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("business_intelligence.tabs.report_definitions"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.create_new_report"), command=self._create_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_reports).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("business_intelligence.btn.run_report"), command=self._run_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("business_intelligence.btn.delete_report"), command=self._delete_report).pack(side=tk.LEFT, padx=5)

        # Reports list
        list_frame = ttk.LabelFrame(tab, text=_t("business_intelligence.labels.available_reports"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview
        columns = ('ID', 'Name', 'Category', 'Created By', 'Created At')
        column_keys = ('id', 'name', 'category', 'created_by', 'created_at')
        self.reports_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.reports_tree.heading('#0', text='')
        self.reports_tree.column('#0', width=0, stretch=False)

        for col, key in zip(columns, column_keys):
            self.reports_tree.heading(col, text=_t(f"business_intelligence.columns.{key}"))
            if col == 'ID':
                self.reports_tree.column(col, width=50)
            elif col == 'Name':
                self.reports_tree.column(col, width=250)
            else:
                self.reports_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.reports_tree.yview)
        self.reports_tree.configure(yscrollcommand=scrollbar.set)

        self.reports_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial data
        self._load_reports()

    def _create_exports_tab(self):
        """Create Report Exports tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("business_intelligence.tabs.exports"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.export_report"), command=self._export_report_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_exports).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("business_intelligence.btn.open_export"), command=self._open_export).pack(side=tk.LEFT, padx=5)

        # Exports list
        list_frame = ttk.LabelFrame(tab, text=_t("business_intelligence.labels.export_history"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('Export ID', 'Report ID', 'Format', 'Generated By', 'Date', 'Rows')
        column_keys = ('export_id', 'report_id', 'format', 'generated_by', 'date', 'rows')
        self.exports_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.exports_tree.heading('#0', text='')
        self.exports_tree.column('#0', width=0, stretch=False)

        for col, key in zip(columns, column_keys):
            self.exports_tree.heading(col, text=_t(f"business_intelligence.columns.{key}"))
            if col in ['Export ID', 'Report ID', 'Rows']:
                self.exports_tree.column(col, width=80)
            elif col == 'Format':
                self.exports_tree.column(col, width=100)
            else:
                self.exports_tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.exports_tree.yview)
        self.exports_tree.configure(yscrollcommand=scrollbar.set)

        self.exports_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_exports()

    def _create_schedules_tab(self):
        """Create Scheduled Reports tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("business_intelligence.tabs.scheduled_reports"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.create_schedule"), command=self._create_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_schedules).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("business_intelligence.btn.toggle_active"), command=self._toggle_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("business_intelligence.btn.delete_schedule"), command=self._delete_schedule).pack(side=tk.LEFT, padx=5)

        # Schedules list
        list_frame = ttk.LabelFrame(tab, text=_t("business_intelligence.labels.report_schedules"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Name', 'Report ID', 'Frequency', 'Recipients', 'Active', 'Next Run')
        column_keys = ('id', 'name', 'report_id', 'frequency', 'recipients', 'active', 'next_run')
        self.schedules_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.schedules_tree.heading('#0', text='')
        self.schedules_tree.column('#0', width=0, stretch=False)

        for col, key in zip(columns, column_keys):
            self.schedules_tree.heading(col, text=_t(f"business_intelligence.columns.{key}"))
            if col in ['ID', 'Report ID', 'Active']:
                self.schedules_tree.column(col, width=70)
            elif col == 'Frequency':
                self.schedules_tree.column(col, width=100)
            else:
                self.schedules_tree.column(col, width=180)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.schedules_tree.yview)
        self.schedules_tree.configure(yscrollcommand=scrollbar.set)

        self.schedules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_schedules()

    def _create_visualizations_tab(self):
        """Create Visualizations tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("business_intelligence.tabs.visualizations"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.create_visualization"), command=self._create_visualization).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_visualizations).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("business_intelligence.btn.delete_visualization"), command=self._delete_visualization).pack(side=tk.LEFT, padx=5)

        # Visualizations list
        list_frame = ttk.LabelFrame(tab, text=_t("business_intelligence.labels.available_visualizations"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Name', 'Chart Type', 'Data Source', 'Created By', 'Created At')
        column_keys = ('id', 'name', 'chart_type', 'data_source', 'created_by', 'created_at')
        self.viz_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.viz_tree.heading('#0', text='')
        self.viz_tree.column('#0', width=0, stretch=False)

        for col, key in zip(columns, column_keys):
            self.viz_tree.heading(col, text=_t(f"business_intelligence.columns.{key}"))
            if col == 'ID':
                self.viz_tree.column(col, width=50)
            elif col in ['Chart Type', 'Created By']:
                self.viz_tree.column(col, width=120)
            else:
                self.viz_tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.viz_tree.yview)
        self.viz_tree.configure(yscrollcommand=scrollbar.set)

        self.viz_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_visualizations()

    def _create_metrics_tab(self):
        """Create Custom Metrics tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("business_intelligence.tabs.custom_metrics"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.define_metric"), command=self._define_metric).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_metrics).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("business_intelligence.btn.delete_metric"), command=self._delete_metric).pack(side=tk.LEFT, padx=5)

        # Metrics list
        list_frame = ttk.LabelFrame(tab, text=_t("business_intelligence.labels.defined_metrics"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Name', 'Category', 'Target Value', 'Created By', 'Created At')
        column_keys = ('id', 'name', 'category', 'target_value', 'created_by', 'created_at')
        self.metrics_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.metrics_tree.heading('#0', text='')
        self.metrics_tree.column('#0', width=0, stretch=False)

        for col, key in zip(columns, column_keys):
            self.metrics_tree.heading(col, text=_t(f"business_intelligence.columns.{key}"))
            if col == 'ID':
                self.metrics_tree.column(col, width=50)
            elif col in ['Target Value']:
                self.metrics_tree.column(col, width=100)
            else:
                self.metrics_tree.column(col, width=180)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.metrics_tree.yview)
        self.metrics_tree.configure(yscrollcommand=scrollbar.set)

        self.metrics_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_metrics()

    # Load Methods
    def _load_reports(self):
        """Load all report definitions"""
        try:
            self.reports_tree.delete(*self.reports_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT report_id, report_name, report_category, created_by, created_at
                    FROM bi_report_definitions
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                ''')

                for row in cursor.fetchall():
                    self.reports_tree.insert('', tk.END, values=tuple(row))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.reports.load_failed", error=e))

    def _load_exports(self):
        """Load export history"""
        try:
            self.exports_tree.delete(*self.exports_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT export_id, report_id, export_format, generated_by,
                           generated_at, row_count
                    FROM bi_report_exports
                    ORDER BY generated_at DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    self.exports_tree.insert('', tk.END, values=tuple(row))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.exports.load_failed", error=e))

    def _load_schedules(self):
        """Load report schedules"""
        try:
            self.schedules_tree.delete(*self.schedules_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT schedule_id, schedule_name, report_id, frequency,
                           recipients, is_active, next_run_date
                    FROM bi_report_schedules
                    ORDER BY created_at DESC
                ''')

                for row in cursor.fetchall():
                    values = list(row)
                    values[5] = '✓' if values[5] else '✗'  # Active status
                    self.schedules_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.schedules.load_failed", error=e))

    def _load_visualizations(self):
        """Load visualizations"""
        try:
            self.viz_tree.delete(*self.viz_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT visualization_id, visualization_name, chart_type,
                           data_source, created_by, created_at
                    FROM bi_visualizations
                    ORDER BY created_at DESC
                ''')

                for row in cursor.fetchall():
                    self.viz_tree.insert('', tk.END, values=tuple(row))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.visualizations.load_failed", error=e))

    def _load_metrics(self):
        """Load custom metrics"""
        try:
            self.metrics_tree.delete(*self.metrics_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT metric_id, metric_name, metric_category,
                           target_value, created_by, created_at
                    FROM bi_custom_metrics
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                ''')

                for row in cursor.fetchall():
                    self.metrics_tree.insert('', tk.END, values=tuple(row))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.metrics.load_failed", error=e))

    # Action Methods
    def _create_report(self):
        """Create a new report definition"""
        CreateReportDialog(self.window, self.auth, self._load_reports)

    def _run_report(self):
        """Run the selected report"""
        selection = self.reports_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.reports.select_to_run"))
            return

        item = self.reports_tree.item(selection[0])
        report_id = item['values'][0]
        report_name = item['values'][1]

        RunReportDialog(self.window, self.auth, report_id, report_name)

    def _delete_report(self):
        """Delete the selected report"""
        selection = self.reports_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.reports.select_to_delete"))
            return

        item = self.reports_tree.item(selection[0])
        report_id = item['values'][0]
        report_name = item['values'][1]

        if not messagebox.askyesno(_t("business_intelligence.dialogs.confirm_delete_title"), _t("business_intelligence.reports.confirm_delete", name=report_name)):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE bi_report_definitions SET is_active = 0 WHERE report_id = ?', (report_id,))

            log_activity(f'Deleted BI report: {report_id}', user=self.auth.current_user.get('username'))
            messagebox.showinfo(_t("common.success"), _t("business_intelligence.reports.deleted_success"))
            self._load_reports()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.reports.delete_failed", error=e))

    def _export_report_dialog(self):
        """Open export report dialog"""
        ExportReportDialog(self.window, self.auth, self._load_exports)

    def _open_export(self):
        """Open the selected export file"""
        selection = self.exports_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.exports.select_to_open"))
            return

        try:
            item = self.exports_tree.item(selection[0])
            export_id = item['values'][0]

            # Get file path from database
            with get_connection() as conn:
                result = conn.execute(
                    'SELECT file_path FROM bi_report_exports WHERE export_id = ?',
                    (export_id,)
                ).fetchone()

            if result and result[0]:
                file_path = result[0]
                import os
                import platform
                import subprocess

                if os.path.exists(file_path):
                    # Open file with default application based on OS
                    if platform.system() == 'Windows':
                        os.startfile(file_path)
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.run(['open', file_path])
                    else:  # Linux
                        subprocess.run(['xdg-open', file_path])
                    messagebox.showinfo(_t("common.success"), _t("business_intelligence.exports.opened", filename=os.path.basename(file_path)))
                else:
                    # File doesn't exist, show the directory
                    directory = os.path.dirname(file_path)
                    if os.path.exists(directory):
                        if platform.system() == 'Windows':
                            os.startfile(directory)
                        elif platform.system() == 'Darwin':
                            subprocess.run(['open', directory])
                        else:
                            subprocess.run(['xdg-open', directory])
                        messagebox.showwarning(_t("common.warning"),
                            _t("business_intelligence.exports.file_not_found", path=file_path))
                    else:
                        messagebox.showerror(_t("common.error"), _t("business_intelligence.exports.path_not_found", path=file_path))
            else:
                messagebox.showerror(_t("common.error"), _t("business_intelligence.exports.path_missing_db"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.exports.open_failed", error=e))

    def _create_schedule(self):
        """Create a new report schedule"""
        CreateScheduleDialog(self.window, self.auth, self._load_schedules)

    def _toggle_schedule(self):
        """Toggle schedule active status"""
        selection = self.schedules_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.schedules.select_to_toggle"))
            return

        item = self.schedules_tree.item(selection[0])
        schedule_id = item['values'][0]
        is_active = item['values'][5] == '✓'

        try:
            with transaction() as conn:
                conn.execute('UPDATE bi_report_schedules SET is_active = ? WHERE schedule_id = ?',
                           (not is_active, schedule_id))

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.schedules.status_updated"))
            self._load_schedules()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.schedules.update_failed", error=e))

    def _delete_schedule(self):
        """Delete the selected schedule"""
        selection = self.schedules_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.schedules.select_to_delete"))
            return

        item = self.schedules_tree.item(selection[0])
        schedule_id = item['values'][0]

        if not messagebox.askyesno(_t("business_intelligence.dialogs.confirm_delete_title"), _t("business_intelligence.schedules.confirm_delete")):
            return

        try:
            with transaction() as conn:
                conn.execute('DELETE FROM bi_report_schedules WHERE schedule_id = ?', (schedule_id,))

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.schedules.deleted_success"))
            self._load_schedules()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.schedules.delete_failed", error=e))

    def _create_visualization(self):
        """Create a new visualization"""
        CreateVisualizationDialog(self.window, self.auth, self._load_visualizations)

    def _delete_visualization(self):
        """Delete the selected visualization"""
        selection = self.viz_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.visualizations.select_to_delete"))
            return

        item = self.viz_tree.item(selection[0])
        viz_id = item['values'][0]

        if not messagebox.askyesno(_t("business_intelligence.dialogs.confirm_delete_title"), _t("business_intelligence.visualizations.confirm_delete")):
            return

        try:
            with transaction() as conn:
                conn.execute('DELETE FROM bi_visualizations WHERE visualization_id = ?', (viz_id,))

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.visualizations.deleted_success"))
            self._load_visualizations()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.visualizations.delete_failed", error=e))

    def _define_metric(self):
        """Define a new custom metric"""
        DefineMetricDialog(self.window, self.auth, self._load_metrics)

    def _delete_metric(self):
        """Delete the selected metric"""
        selection = self.metrics_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.metrics.select_to_delete"))
            return

        item = self.metrics_tree.item(selection[0])
        metric_id = item['values'][0]

        if not messagebox.askyesno(_t("business_intelligence.dialogs.confirm_delete_title"), _t("business_intelligence.metrics.confirm_delete")):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE bi_custom_metrics SET is_active = 0 WHERE metric_id = ?', (metric_id,))

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.metrics.deleted_success"))
            self._load_metrics()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.metrics.delete_failed", error=e))


# Dialog Classes

class CreateReportDialog:
    """Dialog for creating a new report definition"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("business_intelligence.dialogs.create_report_title"))
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("business_intelligence.dialogs.create_report_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Report Name
        ttk.Label(form_frame, text=_t("business_intelligence.labels.report_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=40)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Category
        ttk.Label(form_frame, text=_t("business_intelligence.labels.category")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.category_combo = ttk.Combobox(form_frame, width=37, values=[
            _t("business_intelligence.categories.academic"),
            _t("business_intelligence.categories.financial"),
            _t("business_intelligence.categories.student_affairs"),
            _t("business_intelligence.categories.administrative"),
            _t("business_intelligence.categories.custom")
        ])
        self.category_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.category_combo.set(_t("business_intelligence.categories.academic"))

        # Description
        ttk.Label(form_frame, text=_t("business_intelligence.labels.description")).grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=30, height=4)
        self.desc_text.grid(row=2, column=1, pady=5, padx=(10, 0))

        # SQL Query
        ttk.Label(form_frame, text=_t("business_intelligence.labels.sql_query")).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.query_text = scrolledtext.ScrolledText(form_frame, width=30, height=8)
        self.query_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            category = self.category_combo.get().strip()
            description = self.desc_text.get('1.0', tk.END).strip()
            sql_query = self.query_text.get('1.0', tk.END).strip()

            if not name:
                messagebox.showerror(_t("common.error"), _t("business_intelligence.reports.name_required"))
                return

            report_id = ReportDefinitionManager.create_report(
                report_name=name,
                report_category=category,
                description=description,
                sql_query=sql_query,
                created_by=self.auth.current_user.get('username', '')
            )

            log_activity(f'Created BI report: {report_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.reports.created_success", id=report_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.reports.create_failed", error=e))


class RunReportDialog:
    """Dialog for running a report and displaying results"""

    def __init__(self, parent, auth, report_id, report_name):
        self.auth = auth
        self.report_id = report_id
        self.report_name = report_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("business_intelligence.dialogs.run_report_title", name=report_name))
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)

        self._create_widgets()
        self._run_report()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("business_intelligence.dialogs.report_label", name=self.report_name),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Results display
        result_frame = ttk.LabelFrame(main_frame, text=_t("business_intelligence.labels.results"), padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.result_text = scrolledtext.ScrolledText(result_frame, width=80, height=25)
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.export_csv"), command=self._export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.close"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _run_report(self):
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT sql_query FROM bi_report_definitions WHERE report_id = ?
                ''', (self.report_id,))
                row = cursor.fetchone()

                if not row or not row['sql_query']:
                    self.result_text.insert('1.0', _t("business_intelligence.reports.no_query"))
                    return

                sql_query = row['sql_query']

                # Execute the query
                cursor = conn.execute(sql_query)
                results = cursor.fetchall()

                if not results:
                    self.result_text.insert('1.0', _t("business_intelligence.reports.no_results"))
                    return

                # Format results
                output = _t("business_intelligence.reports.query_success", count=len(results))

                # Column headers
                headers = [desc[0] for desc in cursor.description]
                output += " | ".join(headers) + "\n"
                output += "-" * 80 + "\n"

                # Data rows
                for row in results[:100]:  # Limit to first 100 rows for display
                    output += " | ".join(str(val) for val in row) + "\n"

                if len(results) > 100:
                    output += _t("business_intelligence.reports.more_rows", count=len(results) - 100)

                self.result_text.insert('1.0', output)
                self.results = results
                self.headers = headers

        except Exception as e:
            self.result_text.insert('1.0', _t("business_intelligence.reports.run_error", error=e))

    def _export_csv(self):
        if not hasattr(self, 'results'):
            messagebox.showwarning(_t("common.warning"), _t("business_intelligence.reports.no_results_export"))
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)
                writer.writerows(self.results)

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.reports.exported_to", path=filepath))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.reports.export_failed", error=e))


class ExportReportDialog:
    """Dialog for exporting a report"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("business_intelligence.dialogs.export_report_title"))
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()
        self._load_reports()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("business_intelligence.dialogs.export_report_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("business_intelligence.labels.select_report")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.report_combo = ttk.Combobox(form_frame, width=30, state='readonly')
        self.report_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.export_format")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.format_combo = ttk.Combobox(form_frame, width=30, values=[
            _t("business_intelligence.export_formats.csv"),
            _t("business_intelligence.export_formats.json"),
            _t("business_intelligence.export_formats.excel"),
            _t("business_intelligence.export_formats.pdf")
        ])
        self.format_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.format_combo.set(_t("business_intelligence.export_formats.csv"))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.export"), command=self._export).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_reports(self):
        try:
            with get_connection() as conn:
                cursor = conn.execute('SELECT report_id, report_name FROM bi_report_definitions WHERE is_active = 1')
                self.reports = {row['report_name']: row['report_id'] for row in cursor.fetchall()}
                self.report_combo['values'] = list(self.reports.keys())

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.reports.load_failed", error=e))

    def _export(self):
        report_name = self.report_combo.get()
        export_format = self.format_combo.get()

        if not report_name:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.exports.select_report"))
            return

        report_id = self.reports[report_name]

        try:
            export_id = ReportExportManager.export_report(
                report_id=report_id,
                export_format=export_format,
                file_path=str(paths.TEMP_DIR / f"report_{report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format.lower()}"),
                generated_by=self.auth.current_user.get('username', ''),
                row_count=0
            )

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.exports.created_success", id=export_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.reports.export_failed", error=e))


class CreateScheduleDialog:
    """Dialog for creating a report schedule"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("business_intelligence.dialogs.create_schedule_title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()
        self._load_reports()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("business_intelligence.dialogs.create_schedule_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("business_intelligence.labels.schedule_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.report")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.report_combo = ttk.Combobox(form_frame, width=27, state='readonly')
        self.report_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.frequency")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.freq_combo = ttk.Combobox(form_frame, width=27, values=[
            _t("business_intelligence.frequencies.daily"),
            _t("business_intelligence.frequencies.weekly"),
            _t("business_intelligence.frequencies.monthly"),
            _t("business_intelligence.frequencies.quarterly")
        ])
        self.freq_combo.grid(row=2, column=1, pady=5, padx=(10, 0))
        self.freq_combo.set(_t("business_intelligence.frequencies.weekly"))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.delivery_method")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.delivery_combo = ttk.Combobox(form_frame, width=27, values=[
            _t("business_intelligence.delivery_methods.email"),
            _t("business_intelligence.delivery_methods.download"),
            _t("business_intelligence.delivery_methods.ftp")
        ])
        self.delivery_combo.grid(row=3, column=1, pady=5, padx=(10, 0))
        self.delivery_combo.set(_t("business_intelligence.delivery_methods.email"))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.recipients")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.recipients_entry = ttk.Entry(form_frame, width=30)
        self.recipients_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.export_format")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.format_combo = ttk.Combobox(form_frame, width=27, values=[
            _t("business_intelligence.export_formats.csv"),
            _t("business_intelligence.export_formats.pdf"),
            _t("business_intelligence.export_formats.excel")
        ])
        self.format_combo.grid(row=5, column=1, pady=5, padx=(10, 0))
        self.format_combo.set(_t("business_intelligence.export_formats.csv"))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_reports(self):
        try:
            with get_connection() as conn:
                cursor = conn.execute('SELECT report_id, report_name FROM bi_report_definitions WHERE is_active = 1')
                self.reports = {row['report_name']: row['report_id'] for row in cursor.fetchall()}
                self.report_combo['values'] = list(self.reports.keys())

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.reports.load_failed", error=e))

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            report_name = self.report_combo.get()

            if not name or not report_name:
                messagebox.showerror(_t("common.error"), _t("business_intelligence.schedules.name_report_required"))
                return

            report_id = self.reports[report_name]

            schedule_id = ReportScheduleManager.create_schedule(
                report_id=report_id,
                schedule_name=name,
                frequency=self.freq_combo.get(),
                delivery_method=self.delivery_combo.get(),
                recipients=self.recipients_entry.get(),
                export_format=self.format_combo.get()
            )

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.schedules.created_success", id=schedule_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.schedules.create_failed", error=e))


class CreateVisualizationDialog:
    """Dialog for creating a visualization"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("business_intelligence.dialogs.create_visualization_title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("business_intelligence.dialogs.create_visualization_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("business_intelligence.labels.visualization_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.chart_type")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.chart_combo = ttk.Combobox(form_frame, width=27, values=[
            _t("business_intelligence.chart_types.bar_chart"),
            _t("business_intelligence.chart_types.line_chart"),
            _t("business_intelligence.chart_types.pie_chart"),
            _t("business_intelligence.chart_types.scatter_plot"),
            _t("business_intelligence.chart_types.heatmap"),
            _t("business_intelligence.chart_types.table")
        ])
        self.chart_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.chart_combo.set(_t("business_intelligence.chart_types.bar_chart"))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.data_source")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.source_entry = ttk.Entry(form_frame, width=30)
        self.source_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.x_axis")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.x_entry = ttk.Entry(form_frame, width=30)
        self.x_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.y_axis")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.y_entry = ttk.Entry(form_frame, width=30)
        self.y_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            chart_type = self.chart_combo.get()
            data_source = self.source_entry.get().strip()

            if not name or not data_source:
                messagebox.showerror(_t("common.error"), _t("business_intelligence.visualizations.name_source_required"))
                return

            viz_id = VisualizationManager.create_visualization(
                visualization_name=name,
                chart_type=chart_type,
                data_source=data_source,
                x_axis=self.x_entry.get(),
                y_axis=self.y_entry.get(),
                created_by=self.auth.current_user.get('username', '')
            )

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.visualizations.created_success", id=viz_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.visualizations.create_failed", error=e))


class DefineMetricDialog:
    """Dialog for defining a custom metric"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("business_intelligence.dialogs.define_metric_title"))
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("business_intelligence.dialogs.define_metric_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("business_intelligence.labels.metric_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.category")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.category_combo = ttk.Combobox(form_frame, width=27, values=[
            _t("business_intelligence.categories.academic"),
            _t("business_intelligence.categories.financial"),
            _t("business_intelligence.categories.enrollment"),
            _t("business_intelligence.categories.retention"),
            _t("business_intelligence.categories.custom")
        ])
        self.category_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.category_combo.set(_t("business_intelligence.categories.custom"))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.calculation_formula")).grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.formula_text = scrolledtext.ScrolledText(form_frame, width=30, height=6)
        self.formula_text.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.description")).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=30, height=4)
        self.desc_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("business_intelligence.labels.target_value")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.target_entry = ttk.Entry(form_frame, width=30)
        self.target_entry.grid(row=4, column=1, pady=5, padx=(10, 0))
        self.target_entry.insert(0, '0')

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("business_intelligence.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            category = self.category_combo.get()
            formula = self.formula_text.get('1.0', tk.END).strip()
            description = self.desc_text.get('1.0', tk.END).strip()
            target = float(self.target_entry.get())

            if not name or not formula:
                messagebox.showerror(_t("common.error"), _t("business_intelligence.metrics.name_formula_required"))
                return

            metric_id = CustomMetricManager.define_metric(
                metric_name=name,
                metric_category=category,
                calculation_formula=formula,
                description=description,
                target_value=target,
                created_by=self.auth.current_user.get('username', '')
            )

            messagebox.showinfo(_t("common.success"), _t("business_intelligence.metrics.created_success", id=metric_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.metrics.target_must_be_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("business_intelligence.metrics.create_failed", error=e))


# Launcher function
def launch_business_intelligence_gui(root, auth):
    """Launch the Business Intelligence Reports GUI"""
    try:
        BusinessIntelligenceGUI(root, auth)
    except Exception as e:
        from tkinter import messagebox
        messagebox.showerror(_t("common.error"), str(e))
        print(_t("business_intelligence.messages.gui_launch_error", error=e))


__all__ = ['BusinessIntelligenceGUI', 'launch_business_intelligence_gui']
