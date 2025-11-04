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

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.modules.shared.services.business_intelligence.bi_reports_core import (
    ReportDefinitionManager,
    ReportExportManager,
    ReportScheduleManager,
    VisualizationManager,
    CustomMetricManager
)


class BusinessIntelligenceGUI:
    """Business Intelligence Reports GUI Application"""

    def __init__(self, root, auth):
        """Initialize the BI Reports GUI"""
        self.root = root
        self.auth = auth

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access Business Intelligence Reports.")
            return

        self.window = tk.Toplevel(root)
        self.window.title("Business Intelligence Reports")
        self.window.geometry("1200x800")
        self.window.minsize(1000, 600)

        # Initialize database tables
        self._init_database()

        # Setup UI
        self._create_widgets()

        # Log activity
        log_activity('Accessed Business Intelligence Reports Dashboard', user=self.auth.current_user.get('username'))
        print("✅ Business Intelligence Reports GUI opened successfully")

    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            from university_system.infrastructure.database.schemas import init_business_intelligence_system_db
            init_business_intelligence_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning("Warning", f"Database initialization issue: {e}")

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
            text="Business Intelligence Reports",
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        user_label = ttk.Label(
            header_frame,
            text=f"User: {self.auth.current_user.get('username', 'Unknown')}",
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
            text="Close",
            command=self.window.destroy
        ).pack(pady=(10, 0))

    def _create_reports_tab(self):
        """Create Report Definitions tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Report Definitions")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Create New Report", command=self._create_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_reports).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Run Report", command=self._run_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Report", command=self._delete_report).pack(side=tk.LEFT, padx=5)

        # Reports list
        list_frame = ttk.LabelFrame(tab, text="Available Reports", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview
        columns = ('ID', 'Name', 'Category', 'Created By', 'Created At')
        self.reports_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.reports_tree.heading('#0', text='')
        self.reports_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.reports_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Exports")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Export Report", command=self._export_report_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_exports).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Export", command=self._open_export).pack(side=tk.LEFT, padx=5)

        # Exports list
        list_frame = ttk.LabelFrame(tab, text="Export History", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('Export ID', 'Report ID', 'Format', 'Generated By', 'Date', 'Rows')
        self.exports_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.exports_tree.heading('#0', text='')
        self.exports_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.exports_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Scheduled Reports")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Create Schedule", command=self._create_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_schedules).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Toggle Active", command=self._toggle_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Schedule", command=self._delete_schedule).pack(side=tk.LEFT, padx=5)

        # Schedules list
        list_frame = ttk.LabelFrame(tab, text="Report Schedules", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Name', 'Report ID', 'Frequency', 'Recipients', 'Active', 'Next Run')
        self.schedules_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.schedules_tree.heading('#0', text='')
        self.schedules_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.schedules_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Visualizations")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Create Visualization", command=self._create_visualization).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_visualizations).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Visualization", command=self._delete_visualization).pack(side=tk.LEFT, padx=5)

        # Visualizations list
        list_frame = ttk.LabelFrame(tab, text="Available Visualizations", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Name', 'Chart Type', 'Data Source', 'Created By', 'Created At')
        self.viz_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.viz_tree.heading('#0', text='')
        self.viz_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.viz_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Custom Metrics")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Define Metric", command=self._define_metric).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_metrics).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Metric", command=self._delete_metric).pack(side=tk.LEFT, padx=5)

        # Metrics list
        list_frame = ttk.LabelFrame(tab, text="Defined Metrics", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Name', 'Category', 'Target Value', 'Created By', 'Created At')
        self.metrics_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.metrics_tree.heading('#0', text='')
        self.metrics_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.metrics_tree.heading(col, text=col)
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
                    self.reports_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load reports: {e}")

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
                    self.exports_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load exports: {e}")

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
            messagebox.showerror("Error", f"Failed to load schedules: {e}")

    def _load_visualizations(self):
        """Load visualizations"""
        try:
            self.viz_tree.delete(*self.viz_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT visualization_id, visualization_name, chart_type,
                           data_source, created_by, created_at
                    FROM bi_visualizations
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                ''')

                for row in cursor.fetchall():
                    self.viz_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load visualizations: {e}")

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
                    self.metrics_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load metrics: {e}")

    # Action Methods
    def _create_report(self):
        """Create a new report definition"""
        CreateReportDialog(self.window, self.auth, self._load_reports)

    def _run_report(self):
        """Run the selected report"""
        selection = self.reports_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a report to run")
            return

        item = self.reports_tree.item(selection[0])
        report_id = item['values'][0]
        report_name = item['values'][1]

        RunReportDialog(self.window, self.auth, report_id, report_name)

    def _delete_report(self):
        """Delete the selected report"""
        selection = self.reports_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a report to delete")
            return

        item = self.reports_tree.item(selection[0])
        report_id = item['values'][0]
        report_name = item['values'][1]

        if not messagebox.askyesno("Confirm Delete", f"Delete report '{report_name}'?"):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE bi_report_definitions SET is_active = 0 WHERE report_id = ?', (report_id,))

            log_activity(f'Deleted BI report: {report_id}', user=self.auth.current_user.get('username'))
            messagebox.showinfo("Success", "Report deleted successfully")
            self._load_reports()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete report: {e}")

    def _export_report_dialog(self):
        """Open export report dialog"""
        ExportReportDialog(self.window, self.auth, self._load_exports)

    def _open_export(self):
        """Open the selected export file"""
        selection = self.exports_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an export to open")
            return

        messagebox.showinfo("Info", "Export file location feature coming soon")

    def _create_schedule(self):
        """Create a new report schedule"""
        CreateScheduleDialog(self.window, self.auth, self._load_schedules)

    def _toggle_schedule(self):
        """Toggle schedule active status"""
        selection = self.schedules_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a schedule to toggle")
            return

        item = self.schedules_tree.item(selection[0])
        schedule_id = item['values'][0]
        is_active = item['values'][5] == '✓'

        try:
            with transaction() as conn:
                conn.execute('UPDATE bi_report_schedules SET is_active = ? WHERE schedule_id = ?',
                           (not is_active, schedule_id))

            messagebox.showinfo("Success", "Schedule status updated")
            self._load_schedules()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update schedule: {e}")

    def _delete_schedule(self):
        """Delete the selected schedule"""
        selection = self.schedules_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a schedule to delete")
            return

        item = self.schedules_tree.item(selection[0])
        schedule_id = item['values'][0]

        if not messagebox.askyesno("Confirm Delete", "Delete this schedule?"):
            return

        try:
            with transaction() as conn:
                conn.execute('DELETE FROM bi_report_schedules WHERE schedule_id = ?', (schedule_id,))

            messagebox.showinfo("Success", "Schedule deleted successfully")
            self._load_schedules()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete schedule: {e}")

    def _create_visualization(self):
        """Create a new visualization"""
        CreateVisualizationDialog(self.window, self.auth, self._load_visualizations)

    def _delete_visualization(self):
        """Delete the selected visualization"""
        selection = self.viz_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a visualization to delete")
            return

        item = self.viz_tree.item(selection[0])
        viz_id = item['values'][0]

        if not messagebox.askyesno("Confirm Delete", "Delete this visualization?"):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE bi_visualizations SET is_active = 0 WHERE visualization_id = ?', (viz_id,))

            messagebox.showinfo("Success", "Visualization deleted successfully")
            self._load_visualizations()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete visualization: {e}")

    def _define_metric(self):
        """Define a new custom metric"""
        DefineMetricDialog(self.window, self.auth, self._load_metrics)

    def _delete_metric(self):
        """Delete the selected metric"""
        selection = self.metrics_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a metric to delete")
            return

        item = self.metrics_tree.item(selection[0])
        metric_id = item['values'][0]

        if not messagebox.askyesno("Confirm Delete", "Delete this metric?"):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE bi_custom_metrics SET is_active = 0 WHERE metric_id = ?', (metric_id,))

            messagebox.showinfo("Success", "Metric deleted successfully")
            self._load_metrics()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete metric: {e}")


# Dialog Classes

class CreateReportDialog:
    """Dialog for creating a new report definition"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create New Report")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create New Report", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Report Name
        ttk.Label(form_frame, text="Report Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=40)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Category
        ttk.Label(form_frame, text="Category:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.category_combo = ttk.Combobox(form_frame, width=37, values=[
            'Academic', 'Financial', 'Student Affairs', 'Administrative', 'Custom'
        ])
        self.category_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.category_combo.set('Academic')

        # Description
        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=30, height=4)
        self.desc_text.grid(row=2, column=1, pady=5, padx=(10, 0))

        # SQL Query
        ttk.Label(form_frame, text="SQL Query:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.query_text = scrolledtext.ScrolledText(form_frame, width=30, height=8)
        self.query_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            category = self.category_combo.get().strip()
            description = self.desc_text.get('1.0', tk.END).strip()
            sql_query = self.query_text.get('1.0', tk.END).strip()

            if not name:
                messagebox.showerror("Error", "Report name is required")
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

            messagebox.showinfo("Success", f"Report created successfully (ID: {report_id})")
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create report: {e}")


class RunReportDialog:
    """Dialog for running a report and displaying results"""

    def __init__(self, parent, auth, report_id, report_name):
        self.auth = auth
        self.report_id = report_id
        self.report_name = report_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Run Report: {report_name}")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)

        self._create_widgets()
        self._run_report()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Report: {self.report_name}",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Results display
        result_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.result_text = scrolledtext.ScrolledText(result_frame, width=80, height=25)
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))

        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _run_report(self):
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT sql_query FROM bi_report_definitions WHERE report_id = ?
                ''', (self.report_id,))
                row = cursor.fetchone()

                if not row or not row['sql_query']:
                    self.result_text.insert('1.0', "No SQL query defined for this report")
                    return

                sql_query = row['sql_query']

                # Execute the query
                cursor = conn.execute(sql_query)
                results = cursor.fetchall()

                if not results:
                    self.result_text.insert('1.0', "Query returned no results")
                    return

                # Format results
                output = f"Query executed successfully. {len(results)} rows returned.\n\n"

                # Column headers
                headers = [desc[0] for desc in cursor.description]
                output += " | ".join(headers) + "\n"
                output += "-" * 80 + "\n"

                # Data rows
                for row in results[:100]:  # Limit to first 100 rows for display
                    output += " | ".join(str(val) for val in row) + "\n"

                if len(results) > 100:
                    output += f"\n... and {len(results) - 100} more rows"

                self.result_text.insert('1.0', output)
                self.results = results
                self.headers = headers

        except Exception as e:
            self.result_text.insert('1.0', f"Error running report: {e}")

    def _export_csv(self):
        if not hasattr(self, 'results'):
            messagebox.showwarning("Warning", "No results to export")
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

            messagebox.showinfo("Success", f"Report exported to {filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")


class ExportReportDialog:
    """Dialog for exporting a report"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Report")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()
        self._load_reports()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Export Report", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Select Report:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.report_combo = ttk.Combobox(form_frame, width=30, state='readonly')
        self.report_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Export Format:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.format_combo = ttk.Combobox(form_frame, width=30, values=['CSV', 'JSON', 'Excel', 'PDF'])
        self.format_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.format_combo.set('CSV')

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Export", command=self._export).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_reports(self):
        try:
            with get_connection() as conn:
                cursor = conn.execute('SELECT report_id, report_name FROM bi_report_definitions WHERE is_active = 1')
                self.reports = {row['report_name']: row['report_id'] for row in cursor.fetchall()}
                self.report_combo['values'] = list(self.reports.keys())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load reports: {e}")

    def _export(self):
        report_name = self.report_combo.get()
        export_format = self.format_combo.get()

        if not report_name:
            messagebox.showerror("Error", "Please select a report")
            return

        report_id = self.reports[report_name]

        try:
            export_id = ReportExportManager.export_report(
                report_id=report_id,
                export_format=export_format,
                file_path=f"/tmp/report_{report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format.lower()}",
                generated_by=self.auth.current_user.get('username', ''),
                row_count=0
            )

            messagebox.showinfo("Success", f"Report export created (ID: {export_id})")
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")


class CreateScheduleDialog:
    """Dialog for creating a report schedule"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Report Schedule")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()
        self._load_reports()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create Report Schedule", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Schedule Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Report:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.report_combo = ttk.Combobox(form_frame, width=27, state='readonly')
        self.report_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Frequency:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.freq_combo = ttk.Combobox(form_frame, width=27, values=['Daily', 'Weekly', 'Monthly', 'Quarterly'])
        self.freq_combo.grid(row=2, column=1, pady=5, padx=(10, 0))
        self.freq_combo.set('Weekly')

        ttk.Label(form_frame, text="Delivery Method:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.delivery_combo = ttk.Combobox(form_frame, width=27, values=['Email', 'Download', 'FTP'])
        self.delivery_combo.grid(row=3, column=1, pady=5, padx=(10, 0))
        self.delivery_combo.set('Email')

        ttk.Label(form_frame, text="Recipients:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.recipients_entry = ttk.Entry(form_frame, width=30)
        self.recipients_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Export Format:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.format_combo = ttk.Combobox(form_frame, width=27, values=['CSV', 'PDF', 'Excel'])
        self.format_combo.grid(row=5, column=1, pady=5, padx=(10, 0))
        self.format_combo.set('CSV')

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_reports(self):
        try:
            with get_connection() as conn:
                cursor = conn.execute('SELECT report_id, report_name FROM bi_report_definitions WHERE is_active = 1')
                self.reports = {row['report_name']: row['report_id'] for row in cursor.fetchall()}
                self.report_combo['values'] = list(self.reports.keys())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load reports: {e}")

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            report_name = self.report_combo.get()

            if not name or not report_name:
                messagebox.showerror("Error", "Schedule name and report are required")
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

            messagebox.showinfo("Success", f"Schedule created successfully (ID: {schedule_id})")
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create schedule: {e}")


class CreateVisualizationDialog:
    """Dialog for creating a visualization"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Visualization")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create Visualization", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Visualization Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Chart Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.chart_combo = ttk.Combobox(form_frame, width=27, values=[
            'Bar Chart', 'Line Chart', 'Pie Chart', 'Scatter Plot', 'Heatmap', 'Table'
        ])
        self.chart_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.chart_combo.set('Bar Chart')

        ttk.Label(form_frame, text="Data Source:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.source_entry = ttk.Entry(form_frame, width=30)
        self.source_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="X-Axis:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.x_entry = ttk.Entry(form_frame, width=30)
        self.x_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Y-Axis:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.y_entry = ttk.Entry(form_frame, width=30)
        self.y_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            chart_type = self.chart_combo.get()
            data_source = self.source_entry.get().strip()

            if not name or not data_source:
                messagebox.showerror("Error", "Name and data source are required")
                return

            viz_id = VisualizationManager.create_visualization(
                visualization_name=name,
                chart_type=chart_type,
                data_source=data_source,
                x_axis=self.x_entry.get(),
                y_axis=self.y_entry.get(),
                created_by=self.auth.current_user.get('username', '')
            )

            messagebox.showinfo("Success", f"Visualization created successfully (ID: {viz_id})")
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create visualization: {e}")


class DefineMetricDialog:
    """Dialog for defining a custom metric"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Define Custom Metric")
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Define Custom Metric", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Metric Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Category:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.category_combo = ttk.Combobox(form_frame, width=27, values=[
            'Academic', 'Financial', 'Enrollment', 'Retention', 'Custom'
        ])
        self.category_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.category_combo.set('Custom')

        ttk.Label(form_frame, text="Calculation Formula:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.formula_text = scrolledtext.ScrolledText(form_frame, width=30, height=6)
        self.formula_text.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Description:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=30, height=4)
        self.desc_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Target Value:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.target_entry = ttk.Entry(form_frame, width=30)
        self.target_entry.grid(row=4, column=1, pady=5, padx=(10, 0))
        self.target_entry.insert(0, '0')

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            category = self.category_combo.get()
            formula = self.formula_text.get('1.0', tk.END).strip()
            description = self.desc_text.get('1.0', tk.END).strip()
            target = float(self.target_entry.get())

            if not name or not formula:
                messagebox.showerror("Error", "Name and formula are required")
                return

            metric_id = CustomMetricManager.define_metric(
                metric_name=name,
                metric_category=category,
                calculation_formula=formula,
                description=description,
                target_value=target,
                created_by=self.auth.current_user.get('username', '')
            )

            messagebox.showinfo("Success", f"Metric defined successfully (ID: {metric_id})")
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror("Error", "Target value must be a number")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to define metric: {e}")


# Launcher function
def launch_business_intelligence_gui(root, auth):
    """Launch the Business Intelligence Reports GUI"""
    try:
        BusinessIntelligenceGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Business Intelligence GUI: {e}")
        print(f"❌ Business Intelligence GUI error: {e}")


__all__ = ['BusinessIntelligenceGUI', 'launch_business_intelligence_gui']
