"""Analytics and reporting methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, timedelta
import logging

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.i18n import get_text as _t

logger = logging.getLogger(__name__)


class AnalyticsMixin:
    """Mixin providing analytics and reporting methods."""

    def view_analytics_summary(self):
        """View analytics summary"""
        try:
            days = int(self.analytics_days_var.get())
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT COUNT(*) FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                ''', (cutoff_date,))
                total_metrics = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT AVG(metric_value) FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                ''', (cutoff_date,))
                avg_value = cursor.fetchone()[0] or 0

                cursor.execute('''
                    SELECT metric_name, COUNT(*) as count
                    FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                    GROUP BY metric_name
                    ORDER BY count DESC
                    LIMIT 1
                ''', (cutoff_date,))
                top_metric = cursor.fetchone()

            summary = f"Analytics Summary (Last {days} Days)\n\n"
            summary += f"Total Metrics Recorded: {total_metrics}\n"
            summary += f"Average Metric Value: {avg_value:.2f}\n"
            if top_metric:
                summary += f"Most Tracked Metric: {top_metric[0]} ({top_metric[1]} times)"

            messagebox.showinfo("Analytics Summary", summary)

        except Exception as e:
            logger.error(f"Error viewing analytics summary: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to view analytics summary: {e}")

    def export_analytics(self):
        """Export analytics to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            days = int(self.analytics_days_var.get())
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT analytics_id, install_id, metric_name, metric_value, measurement_date
                    FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                    ORDER BY measurement_date DESC
                ''', (cutoff_date,))

                analytics = cursor.fetchall()

            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Analytics ID', 'Install ID', 'Metric Name',
                               'Metric Value', 'Measurement Date'])
                writer.writerows(analytics)

            messagebox.showinfo(_t("common.success"), f"Analytics exported to {filename}")
            log_activity('export', 'integration_usage_analytics', None,
                        details={'filename': filename, 'record_count': len(analytics)})

        except Exception as e:
            logger.error(f"Error exporting analytics: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to export analytics: {e}")

    def show_dashboard_overview(self):
        """Real-time dashboard with KPIs, charts, and status widgets"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Integration Dashboard")
            dialog.geometry("900x700")
            dialog.transient(self.root)

            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM integration_catalog WHERE is_active = 1')
                total_catalog = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM installed_integrations WHERE status = 'active'")
                total_installed = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM installed_integrations WHERE is_enabled = 1")
                total_enabled = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT sync_status, COUNT(*) FROM integration_sync_logs
                    WHERE sync_start_time >= date('now', '-7 days')
                    GROUP BY sync_status
                ''')
                sync_stats = dict(cursor.fetchall())

                cursor.execute('''
                    SELECT
                        SUM(CASE WHEN sync_status = 'failed' THEN 1 ELSE 0 END) * 100.0 /
                        NULLIF(COUNT(*), 0)
                    FROM integration_sync_logs
                    WHERE sync_start_time >= date('now', '-7 days')
                ''')
                error_rate = cursor.fetchone()[0] or 0

                cursor.execute('''
                    SELECT ic.integration_name, COUNT(isl.log_id) as sync_count
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    LEFT JOIN integration_sync_logs isl ON ii.install_id = isl.install_id
                    GROUP BY ic.integration_name
                    ORDER BY sync_count DESC
                    LIMIT 5
                ''')
                top_integrations = cursor.fetchall()

            # KPI Frame
            kpi_frame = ttk.LabelFrame(dialog, text="Key Performance Indicators", padding=10)
            kpi_frame.pack(fill='x', padx=10, pady=5)

            kpi_grid = ttk.Frame(kpi_frame)
            kpi_grid.pack(fill='x')

            kpis = [
                ("Catalog Size", total_catalog),
                ("Installed", total_installed),
                (_t("common.enabled"), total_enabled),
                ("Success (7d)", sync_stats.get('success', 0)),
                ("Failed (7d)", sync_stats.get('failed', 0)),
                ("Error Rate", f"{error_rate:.1f}%")
            ]

            for i, (label, value) in enumerate(kpis):
                frame = ttk.Frame(kpi_grid, relief='ridge', borderwidth=2, padding=10)
                frame.grid(row=0, column=i, padx=5, pady=5, sticky='nsew')
                ttk.Label(frame, text=label, font=('Arial', 10)).pack()
                ttk.Label(frame, text=str(value), font=('Arial', 16, 'bold')).pack()
                kpi_grid.columnconfigure(i, weight=1)

            # Status Frame
            status_frame = ttk.LabelFrame(dialog, text="Integration Status", padding=10)
            status_frame.pack(fill='both', expand=True, padx=10, pady=5)

            ttk.Label(status_frame, text="Top Integrations by Activity:",
                     style='Section.TLabel').pack(anchor='w', pady=5)

            for name, count in top_integrations:
                ttk.Label(status_frame, text=f"  {name}: {count} syncs").pack(anchor='w')

            # Health indicator
            health_frame = ttk.LabelFrame(dialog, text="System Health", padding=10)
            health_frame.pack(fill='x', padx=10, pady=5)

            if error_rate < 5:
                health_status = "HEALTHY"
            elif error_rate < 20:
                health_status = "WARNING"
            else:
                health_status = "CRITICAL"

            health_label = ttk.Label(health_frame, text=f"Overall Status: {health_status}",
                                    font=('Arial', 14, 'bold'))
            health_label.pack()

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

            log_activity('view', 'dashboard', None)

        except Exception as e:
            logger.error(f"Error showing dashboard: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to show dashboard: {e}")

    def generate_health_report(self):
        """Comprehensive health report for all integrations"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT
                        ic.integration_name,
                        ii.status,
                        ii.is_enabled,
                        ii.last_sync_date,
                        (SELECT COUNT(*) FROM integration_sync_logs isl
                         WHERE isl.install_id = ii.install_id AND isl.sync_status = 'success'
                         AND isl.sync_start_time >= date('now', '-30 days')) as success_count,
                        (SELECT COUNT(*) FROM integration_sync_logs isl
                         WHERE isl.install_id = ii.install_id AND isl.sync_status = 'failed'
                         AND isl.sync_start_time >= date('now', '-30 days')) as fail_count
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE ii.status != 'uninstalled'
                    ORDER BY ic.integration_name
                ''')
                integrations = cursor.fetchall()

            report = "Integration Health Report\n"
            report += "=" * 50 + "\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            healthy_count = 0
            warning_count = 0
            critical_count = 0

            for integration in integrations:
                name, status, enabled, last_sync, success, fail = integration
                total = success + fail
                success_rate = (success / total * 100) if total > 0 else 0

                if success_rate >= 95 and enabled:
                    health = "HEALTHY"
                    healthy_count += 1
                elif success_rate >= 80 or not enabled:
                    health = "WARNING"
                    warning_count += 1
                else:
                    health = "CRITICAL"
                    critical_count += 1

                report += f"\n{name}\n"
                report += f"  Status: {status} | Enabled: {_t('common.yes') if enabled else _t('common.no')}\n"
                report += f"  Last Sync: {last_sync or _t('common.never')}\n"
                report += f"  Success Rate (30d): {success_rate:.1f}% ({success}/{total})\n"
                report += f"  Health: {health}\n"

            report += "\n" + "=" * 50 + "\n"
            report += f"Summary: {healthy_count} Healthy, {warning_count} Warning, {critical_count} Critical\n"

            # Show report in dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.health_report"))
            dialog.geometry("600x500")
            dialog.transient(self.root)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
            text.pack(fill='both', expand=True, padx=10, pady=10)
            text.insert('1.0', report)
            text.config(state='disabled')

            def export_report():
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                    initialfile="health_report.txt"
                )
                if filename:
                    with open(filename, 'w') as f:
                        f.write(report)
                    messagebox.showinfo(_t("common.success"), f"Report exported to:\n{filename}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text=_t("integration_marketplace.common.export"), command=export_report).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t("common.close"), command=dialog.destroy).pack(side='left', padx=5)

            log_activity('generate', 'health_report', None)

        except Exception as e:
            logger.error(f"Error generating health report: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to generate health report: {e}")

    def show_error_analysis(self):
        """Analyze and categorize sync errors by type/frequency"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT
                        ic.integration_name,
                        isl.error_details,
                        COUNT(*) as error_count
                    FROM integration_sync_logs isl
                    JOIN installed_integrations ii ON isl.install_id = ii.install_id
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE isl.sync_status = 'failed'
                      AND isl.sync_start_time >= date('now', '-30 days')
                    GROUP BY ic.integration_name, isl.error_details
                    ORDER BY error_count DESC
                    LIMIT 50
                ''')
                errors = cursor.fetchall()

                cursor.execute('''
                    SELECT
                        date(sync_start_time) as error_date,
                        COUNT(*) as error_count
                    FROM integration_sync_logs
                    WHERE sync_status = 'failed'
                      AND sync_start_time >= date('now', '-30 days')
                    GROUP BY date(sync_start_time)
                    ORDER BY error_date
                ''')
                trends = cursor.fetchall()

            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.error_analysis"))
            dialog.geometry("800x600")
            dialog.transient(self.root)

            # Error patterns frame
            patterns_frame = ttk.LabelFrame(dialog, text="Error Patterns (Last 30 Days)", padding=10)
            patterns_frame.pack(fill='both', expand=True, padx=10, pady=5)

            columns = ('integration', 'error', 'count')
            tree = ttk.Treeview(patterns_frame, columns=columns, show='headings', height=10)

            tree.heading('integration', text='Integration')
            tree.heading('error', text='Error Details')
            tree.heading('count', text='Count')

            tree.column('integration', width=150)
            tree.column('error', width=400)
            tree.column('count', width=80)

            for error in errors:
                error_text = (error[1] or 'Unknown error')[:100]
                tree.insert('', 'end', values=(error[0], error_text, error[2]))

            tree.pack(fill='both', expand=True)

            # Trend frame
            trend_frame = ttk.LabelFrame(dialog, text="Error Trend", padding=10)
            trend_frame.pack(fill='x', padx=10, pady=5)

            if trends:
                total_errors = sum(t[1] for t in trends)
                avg_errors = total_errors / len(trends)
                ttk.Label(trend_frame,
                         text=f"Total Errors: {total_errors} | Daily Average: {avg_errors:.1f}").pack()
            else:
                ttk.Label(trend_frame, text="No errors in the last 30 days").pack()

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

            log_activity('view', 'error_analysis', None)

        except Exception as e:
            logger.error(f"Error showing error analysis: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to show error analysis: {e}")

    def generate_usage_trend_chart(self):
        """Matplotlib/chart visualization of usage over time"""
        try:
            try:
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            except ImportError:
                messagebox.showerror(_t("common.error"),
                                   "Chart generation requires matplotlib.\n"
                                   "Install with: pip install matplotlib")
                return

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        date(sync_start_time) as sync_date,
                        COUNT(*) as sync_count,
                        SUM(CASE WHEN sync_status = 'success' THEN 1 ELSE 0 END) as success_count
                    FROM integration_sync_logs
                    WHERE sync_start_time >= date('now', '-30 days')
                    GROUP BY date(sync_start_time)
                    ORDER BY sync_date
                ''')
                data = cursor.fetchall()

            if not data:
                messagebox.showinfo(_t("common.info"), "No sync data available for the last 30 days")
                return

            dates = [row[0] for row in data]
            totals = [row[1] for row in data]
            successes = [row[2] for row in data]

            dialog = tk.Toplevel(self.root)
            dialog.title("Usage Trend Chart")
            dialog.geometry("800x600")
            dialog.transient(self.root)

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

            ax1.plot(dates, totals, 'b-', label='Total Syncs', linewidth=2)
            ax1.plot(dates, successes, 'g--', label='Successful', linewidth=2)
            ax1.set_xlabel('Date')
            ax1.set_ylabel('Sync Count')
            ax1.set_title('Integration Sync Activity (Last 30 Days)')
            ax1.legend()
            ax1.tick_params(axis='x', rotation=45)

            success_rates = [s/t*100 if t > 0 else 0 for s, t in zip(successes, totals)]
            ax2.bar(dates, success_rates, color='green', alpha=0.7)
            ax2.set_xlabel('Date')
            ax2.set_ylabel('Success Rate (%)')
            ax2.set_title('Daily Success Rate')
            ax2.tick_params(axis='x', rotation=45)
            ax2.set_ylim(0, 100)

            plt.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=dialog)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

            log_activity('view', 'usage_trend_chart', None)

        except Exception as e:
            logger.error(f"Error generating usage trend chart: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to generate chart: {e}")

    def show_api_call_statistics(self):
        """Statistics on API calls per integration"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        ic.integration_name,
                        COUNT(isl.log_id) as total_calls,
                        SUM(isl.records_synced) as total_records,
                        AVG(isl.records_synced) as avg_records,
                        SUM(CASE WHEN isl.sync_status = 'success' THEN 1 ELSE 0 END) * 100.0 /
                            NULLIF(COUNT(isl.log_id), 0) as success_rate
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    LEFT JOIN integration_sync_logs isl ON ii.install_id = isl.install_id
                    WHERE ii.status = 'active'
                    GROUP BY ic.integration_name
                    ORDER BY total_calls DESC
                ''')
                stats = cursor.fetchall()

            dialog = tk.Toplevel(self.root)
            dialog.title("API Call Statistics")
            dialog.geometry("800x500")
            dialog.transient(self.root)

            columns = ('integration', 'total_calls', 'total_records', 'avg_records', 'success_rate')
            tree = ttk.Treeview(dialog, columns=columns, show='headings', height=15)

            tree.heading('integration', text='Integration')
            tree.heading('total_calls', text='Total API Calls')
            tree.heading('total_records', text='Total Records')
            tree.heading('avg_records', text='Avg Records/Call')
            tree.heading('success_rate', text='Success Rate')

            tree.column('integration', width=200)
            tree.column('total_calls', width=120)
            tree.column('total_records', width=120)
            tree.column('avg_records', width=120)
            tree.column('success_rate', width=100)

            for stat in stats:
                tree.insert('', 'end', values=(
                    stat[0],
                    stat[1] or 0,
                    stat[2] or 0,
                    f"{stat[3]:.1f}" if stat[3] else "0.0",
                    f"{stat[4]:.1f}%" if stat[4] else _t("common.na")
                ))

            vsb = ttk.Scrollbar(dialog, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)

            tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
            vsb.pack(side='right', fill='y', pady=10)

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

            log_activity('view', 'api_statistics', None)

        except Exception as e:
            logger.error(f"Error showing API statistics: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to show API statistics: {e}")

    def compare_integration_performance(self):
        """Side-by-side performance comparison"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Compare Integration Performance")
            dialog.geometry("900x600")
            dialog.transient(self.root)
            dialog.grab_set()

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ii.install_id, ic.integration_name
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE ii.status = 'active'
                    ORDER BY ic.integration_name
                ''')
                integrations = cursor.fetchall()

            if len(integrations) < 2:
                messagebox.showinfo(_t("common.info"), "Need at least 2 active integrations to compare")
                dialog.destroy()
                return

            # Selection frame
            select_frame = ttk.LabelFrame(dialog, text="Select Integrations to Compare", padding=10)
            select_frame.pack(fill='x', padx=10, pady=5)

            ttk.Label(select_frame, text="Integration 1:").grid(row=0, column=0, padx=5, pady=5)
            int1_var = tk.StringVar()
            int1_combo = ttk.Combobox(select_frame, textvariable=int1_var,
                                     values=[f"{i[0]}: {i[1]}" for i in integrations],
                                     width=40, state='readonly')
            int1_combo.grid(row=0, column=1, padx=5, pady=5)
            if integrations:
                int1_combo.current(0)

            ttk.Label(select_frame, text="Integration 2:").grid(row=1, column=0, padx=5, pady=5)
            int2_var = tk.StringVar()
            int2_combo = ttk.Combobox(select_frame, textvariable=int2_var,
                                     values=[f"{i[0]}: {i[1]}" for i in integrations],
                                     width=40, state='readonly')
            int2_combo.grid(row=1, column=1, padx=5, pady=5)
            if len(integrations) > 1:
                int2_combo.current(1)

            # Results frame
            results_frame = ttk.LabelFrame(dialog, text="Comparison Results", padding=10)
            results_frame.pack(fill='both', expand=True, padx=10, pady=5)

            results_text = scrolledtext.ScrolledText(results_frame, height=20)
            results_text.pack(fill='both', expand=True)

            def compare():
                try:
                    if not int1_var.get() or not int2_var.get():
                        messagebox.showwarning(_t("common.warning"), "Please select both integrations")
                        return

                    id1 = int(int1_var.get().split(':')[0])
                    id2 = int(int2_var.get().split(':')[0])

                    with get_connection() as conn:
                        cursor = conn.cursor()

                        def get_stats(install_id):
                            cursor.execute('''
                                SELECT
                                    ic.integration_name,
                                    COUNT(isl.log_id) as total_syncs,
                                    SUM(CASE WHEN isl.sync_status = 'success' THEN 1 ELSE 0 END) as successes,
                                    SUM(isl.records_synced) as total_records,
                                    AVG(isl.records_synced) as avg_records,
                                    ii.last_sync_date
                                FROM installed_integrations ii
                                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                                LEFT JOIN integration_sync_logs isl ON ii.install_id = isl.install_id
                                WHERE ii.install_id = ?
                                GROUP BY ic.integration_name
                            ''', (install_id,))
                            return cursor.fetchone()

                        stats1 = get_stats(id1)
                        stats2 = get_stats(id2)

                    results_text.delete('1.0', 'end')
                    results_text.insert('end', "Performance Comparison\n")
                    results_text.insert('end', "=" * 60 + "\n\n")

                    results_text.insert('end', f"{'Metric':<25} {'Integration 1':<20} {'Integration 2':<20}\n")
                    results_text.insert('end', "-" * 65 + "\n")

                    results_text.insert('end', f"{'Name':<25} {stats1[0]:<20} {stats2[0]:<20}\n")
                    results_text.insert('end', f"{'Total Syncs':<25} {stats1[1] or 0:<20} {stats2[1] or 0:<20}\n")

                    rate1 = (stats1[2] / stats1[1] * 100) if stats1[1] else 0
                    rate2 = (stats2[2] / stats2[1] * 100) if stats2[1] else 0
                    results_text.insert('end', f"{'Success Rate':<25} {rate1:.1f}%{'':<15} {rate2:.1f}%\n")

                    results_text.insert('end', f"{'Total Records':<25} {stats1[3] or 0:<20} {stats2[3] or 0:<20}\n")
                    results_text.insert('end', f"{'Avg Records/Sync':<25} {stats1[4] or 0:.1f}{'':<15} {stats2[4] or 0:.1f}\n")
                    results_text.insert('end', f"{'Last Sync':<25} {(stats1[5] or _t('common.never'))[:16]:<20} {(stats2[5] or _t('common.never'))[:16]:<20}\n")

                    results_text.insert('end', "\n" + "=" * 60 + "\n")

                    if rate1 > rate2:
                        results_text.insert('end', f"\nBetter success rate: {stats1[0]}")
                    elif rate2 > rate1:
                        results_text.insert('end', f"\nBetter success rate: {stats2[0]}")
                    else:
                        results_text.insert('end', "\nBoth integrations have similar success rates")

                except Exception as e:
                    logger.error(f"Error comparing: {e}")
                    results_text.delete('1.0', 'end')
                    results_text.insert('end', f"Error: {e}")

            ttk.Button(select_frame, text=_t("common.compare"), command=compare).grid(row=2, column=0, columnspan=2, pady=10)

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error opening comparison dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open comparison: {e}")

    def generate_compliance_report(self):
        """Report showing data handling compliance status"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT COUNT(*) FROM installed_integrations WHERE status = 'active'
                ''')
                total_active = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM integration_credentials
                ''')
                total_credentials = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM integration_data_mappings WHERE is_active = 1
                ''')
                total_mappings = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM integration_sync_logs
                    WHERE sync_start_time >= date('now', '-30 days')
                ''')
                recent_syncs = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM integration_credentials
                    WHERE token_expiry IS NOT NULL AND token_expiry < datetime('now')
                ''')
                expired_tokens = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT COUNT(*) FROM installed_integrations
                    WHERE status = 'active'
                      AND (last_sync_date IS NULL OR last_sync_date < date('now', '-7 days'))
                ''')
                stale_integrations = cursor.fetchone()[0]

            report = "Data Handling Compliance Report\n"
            report += "=" * 50 + "\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            report += "INVENTORY\n"
            report += "-" * 30 + "\n"
            report += f"Active Integrations: {total_active}\n"
            report += f"Stored Credentials: {total_credentials}\n"
            report += f"Active Data Mappings: {total_mappings}\n"
            report += f"Syncs (Last 30 Days): {recent_syncs}\n\n"

            report += "COMPLIANCE STATUS\n"
            report += "-" * 30 + "\n"

            issues = []

            if expired_tokens > 0:
                issues.append(f"- {expired_tokens} expired credential token(s) found")
                report += f"[WARNING] Expired Tokens: {expired_tokens}\n"
            else:
                report += "[OK] No expired tokens\n"

            if stale_integrations > 0:
                issues.append(f"- {stale_integrations} integration(s) haven't synced in 7+ days")
                report += f"[WARNING] Stale Integrations: {stale_integrations}\n"
            else:
                report += "[OK] All integrations recently active\n"

            if total_credentials > 0:
                report += "[INFO] Credentials stored in database (ensure encryption at rest)\n"

            report += "\nRECOMMENDATIONS\n"
            report += "-" * 30 + "\n"

            if not issues:
                report += "No immediate compliance issues detected.\n"
            else:
                for issue in issues:
                    report += issue + "\n"

            report += "\n[!] Regular compliance reviews recommended\n"
            report += "[!] Ensure data mappings comply with data protection policies\n"
            report += "[!] Review credential access logs periodically\n"

            # Show report
            dialog = tk.Toplevel(self.root)
            dialog.title("Compliance Report")
            dialog.geometry("600x500")
            dialog.transient(self.root)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
            text.pack(fill='both', expand=True, padx=10, pady=10)
            text.insert('1.0', report)
            text.config(state='disabled')

            def export_report():
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                    initialfile="compliance_report.txt"
                )
                if filename:
                    with open(filename, 'w') as f:
                        f.write(report)
                    messagebox.showinfo(_t("common.success"), f"Report exported to:\n{filename}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text=_t("integration_marketplace.common.export"), command=export_report).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t("common.close"), command=dialog.destroy).pack(side='left', padx=5)

            log_activity('generate', 'compliance_report', None)

        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to generate compliance report: {e}")
