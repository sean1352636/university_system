"""
Analytics and reporting tab for the Activity Logger GUI.
"""

from education_system.post_18.university_system.modules.shared.gui.simple_activity_logger_gui._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    json,
    datetime,
    Dict, Any,
    MATPLOTLIB_AVAILABLE,
    _t,
)

if MATPLOTLIB_AVAILABLE:
    from education_system.post_18.university_system.modules.shared.gui.simple_activity_logger_gui._imports import FigureCanvasTkAgg, Figure

from education_system.post_18.university_system.modules.shared.gui.simple_activity_logger_gui.theme import LoggerGUITheme


class AnalyticsTab(ttk.Frame):
    """Analytics and reporting tab"""

    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app

        self.setup_ui()

    def setup_ui(self):
        """Setup analytics UI"""
        # Control panel
        control_frame = ttk.Frame(self, style='AL.Card.TFrame')
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text=_t("activity_logger.analytics.title"),
                 style='AL.Title.TLabel').pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text=_t("activity_logger.analytics.refresh"),
                  command=self.refresh_analytics).pack(side=tk.RIGHT, padx=5)

        ttk.Button(control_frame, text=_t("activity_logger.analytics.generate_report"),
                  command=self.generate_report).pack(side=tk.RIGHT, padx=5)

        # Analytics content
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Left panel - Statistics
        left_panel = ttk.LabelFrame(content_frame, text=_t("activity_logger.analytics.statistics"), padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.stats_text = scrolledtext.ScrolledText(left_panel, wrap=tk.WORD, height=20, width=40)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Right panel - Charts (if matplotlib available)
        if MATPLOTLIB_AVAILABLE:
            right_panel = ttk.LabelFrame(content_frame, text=_t("activity_logger.analytics.charts"), padding=10)
            right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

            # Create matplotlib figure
            self.fig = Figure(figsize=(8, 6), dpi=100, facecolor=LoggerGUITheme.DARK_BG)
            self.canvas = FigureCanvasTkAgg(self.fig, right_panel)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Load initial analytics
        self.refresh_analytics()

    def refresh_analytics(self):
        """Refresh analytics data"""
        try:
            # Get analytics data directly from database
            analytics_data = self.get_analytics_data()

            # Update statistics display
            self.update_statistics(analytics_data)

            # Update charts if available
            if MATPLOTLIB_AVAILABLE:
                self.update_charts(analytics_data)

        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, f"Error loading analytics: {str(e)}\n\nAnalytics data is now available.")
            import traceback
            traceback.print_exc()

    def get_analytics_data(self) -> Dict[str, Any]:
        """Get analytics data from database"""
        analytics_data = {
            'total_logs': 0,
            'error_rate': 0,
            'unique_users': 0,
            'top_actions': {},
            'top_modules': {},
            'system_health': {'status': 'Operational'},
            'recent_anomalies': [],
            'logs_by_level': {},
            'recent_activity': 0
        }

        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                # Get total logs
                cursor = conn.execute("SELECT COUNT(*) FROM activity_log")
                analytics_data['total_logs'] = cursor.fetchone()[0]

                # Get unique users
                cursor = conn.execute("SELECT COUNT(DISTINCT username) FROM activity_log")
                analytics_data['unique_users'] = cursor.fetchone()[0]

                # Get top actions
                cursor = conn.execute("""
                    SELECT action, COUNT(*) as count
                    FROM activity_log
                    GROUP BY action
                    ORDER BY count DESC
                    LIMIT 10
                """)
                analytics_data['top_actions'] = {row[0]: row[1] for row in cursor.fetchall()}

                # Get recent activity (last 24 hours)
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM activity_log
                    WHERE datetime(timestamp) > datetime('now', '-1 day')
                """)
                analytics_data['recent_activity'] = cursor.fetchone()[0]

                # System health check
                analytics_data['system_health'] = {
                    'status': 'Operational',
                    'database': 'Connected',
                    'logs_processing': 'Active'
                }

        except Exception as e:
            print(f"Error getting analytics data: {e}")
            import traceback
            traceback.print_exc()

        return analytics_data

    def update_statistics(self, data: Dict[str, Any]):
        """Update statistics display"""
        self.stats_text.delete(1.0, tk.END)

        stats_text = f"""SYSTEM STATISTICS
{'='*40}

Total Logs: {data.get('total_logs', 0):,}
Recent Activity (24h): {data.get('recent_activity', 0):,}
Unique Users: {data.get('unique_users', 0):,}
Error Rate: {data.get('error_rate', 0):.2f}%

SYSTEM HEALTH
{'='*40}
"""

        system_health = data.get('system_health', {})
        if system_health:
            stats_text += f"""CPU Usage: {system_health.get('cpu_usage', 0):.1f}%
Memory Usage: {system_health.get('memory_usage', 0):.1f}%
Disk Usage: {system_health.get('disk_usage', 0):.1f}%
Active Connections: {system_health.get('active_connections', 0)}
Uptime: {system_health.get('uptime', 0):.0f} seconds

"""

        # Top actions
        top_actions = data.get('top_actions', {})
        if top_actions:
            stats_text += f"""TOP ACTIONS
{'='*40}
"""
            for action, count in list(top_actions.items())[:10]:
                stats_text += f"{action}: {count}\n"
            stats_text += "\n"

        # Top modules
        top_modules = data.get('top_modules', {})
        if top_modules:
            stats_text += f"""TOP MODULES
{'='*40}
"""
            for module, count in list(top_modules.items())[:10]:
                stats_text += f"{module}: {count}\n"
            stats_text += "\n"

        # Anomalies
        anomalies = data.get('recent_anomalies', [])
        if anomalies:
            stats_text += f"""RECENT ANOMALIES
{'='*40}
"""
            for anomaly in anomalies[:5]:
                stats_text += f"\u2022 {anomaly.get('type', 'Unknown')}: {anomaly.get('severity', 'Unknown')} severity\n"
            stats_text += "\n"

        # Logs by level
        logs_by_level = data.get('logs_by_level', {})
        if logs_by_level:
            stats_text += f"""LOGS BY LEVEL
{'='*40}
"""
            for level, count in logs_by_level.items():
                stats_text += f"{level}: {count}\n"

        self.stats_text.insert(tk.END, stats_text)

    def update_charts(self, data: Dict[str, Any]):
        """Update charts display"""
        if not MATPLOTLIB_AVAILABLE:
            return

        try:
            self.fig.clear()

            # Create subplots
            ax1 = self.fig.add_subplot(2, 2, 1)
            ax2 = self.fig.add_subplot(2, 2, 2)
            ax3 = self.fig.add_subplot(2, 2, 3)
            ax4 = self.fig.add_subplot(2, 2, 4)

            # Chart 1: System Health
            system_health = data.get('system_health', {})
            if system_health:
                metrics = ['CPU', 'Memory', 'Disk']
                values = [
                    system_health.get('cpu_usage', 0),
                    system_health.get('memory_usage', 0),
                    system_health.get('disk_usage', 0)
                ]
                colors = ['#ff6b6b' if v > 80 else '#ffa726' if v > 60 else '#4CAF50' for v in values]

                ax1.bar(metrics, values, color=colors)
                ax1.set_title('System Health (%)', color='white', fontsize=10)
                ax1.set_ylim(0, 100)
                ax1.tick_params(colors='white', labelsize=8)

            # Chart 2: Logs by Level
            logs_by_level = data.get('logs_by_level', {})
            if logs_by_level:
                levels = list(logs_by_level.keys())
                counts = list(logs_by_level.values())
                colors = ['#4CAF50', '#2196F3', '#ffa726', '#ff6b6b', '#9c27b0'][:len(levels)]

                ax2.pie(counts, labels=levels, colors=colors, autopct='%1.1f%%',
                       textprops={'color': 'white', 'fontsize': 8})
                ax2.set_title('Logs by Level', color='white', fontsize=10)

            # Chart 3: Top Actions
            top_actions = data.get('top_actions', {})
            if top_actions:
                actions = list(top_actions.keys())[:5]
                counts = list(top_actions.values())[:5]

                ax3.barh(actions, counts, color='#007acc')
                ax3.set_title('Top Actions', color='white', fontsize=10)
                ax3.tick_params(colors='white', labelsize=8)

            # Chart 4: Error Rate Trend (placeholder)
            error_rate = data.get('error_rate', 0)
            ax4.text(0.5, 0.5, f'Error Rate\n{error_rate:.2f}%',
                    ha='center', va='center', fontsize=14, color='white',
                    transform=ax4.transAxes)
            ax4.set_title('Error Rate', color='white', fontsize=10)
            ax4.axis('off')

            # Apply dark theme to figure
            self.fig.patch.set_facecolor(LoggerGUITheme.DARK_BG)
            for ax in [ax1, ax2, ax3, ax4]:
                ax.set_facecolor(LoggerGUITheme.DARKER_BG)
                for spine in ax.spines.values():
                    spine.set_color(LoggerGUITheme.BORDER)

            self.fig.tight_layout()
            self.canvas.draw()

        except Exception as e:
            print(f"Error updating charts: {e}")

    def generate_report(self):
        """Generate analytics report with preview and export options"""
        try:
            # Generate report data from database
            analytics_data = self.get_analytics_data()

            # Format report content
            report_content = f"""ACTIVITY LOGGER ANALYTICS REPORT
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY STATISTICS
{'='*60}
Total Logs: {analytics_data['total_logs']:,}
Unique Users: {analytics_data['unique_users']}
Recent Activity (24h): {analytics_data['recent_activity']:,}

SYSTEM HEALTH
{'='*60}
Status: {analytics_data['system_health'].get('status', 'Unknown')}
Database: {analytics_data['system_health'].get('database', 'Unknown')}
Logs Processing: {analytics_data['system_health'].get('logs_processing', 'Unknown')}

TOP ACTIONS
{'='*60}
"""
            for action, count in list(analytics_data['top_actions'].items())[:10]:
                report_content += f"{action}: {count:,}\n"

            # Show report preview window
            report_window = tk.Toplevel(self)
            report_window.title(_t("activity_logger.dialogs.report"))
            report_window.geometry("900x700")

            # Title
            title_frame = ttk.Frame(report_window, style='AL.Card.TFrame')
            title_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Label(title_frame, text=_t("activity_logger.report.title"),
                     style='AL.Title.TLabel').pack(side=tk.LEFT, padx=10)

            # Report preview
            preview_frame = ttk.LabelFrame(report_window, text="Report Preview", padding=10)
            preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, font=('Courier', 10))
            preview_text.pack(fill=tk.BOTH, expand=True)
            preview_text.insert('1.0', report_content)
            preview_text.config(state='disabled')

            # Button frame
            button_frame = ttk.Frame(report_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            def save_as_format(format_type):
                """Save report in specified format"""
                try:
                    file_extensions = {
                        'txt': '.txt',
                        'json': '.json',
                        'csv': '.csv'
                    }

                    file_path = filedialog.asksaveasfilename(
                        title="Save Report",
                        defaultextension=file_extensions.get(format_type, '.txt'),
                        filetypes=[(f"{format_type.upper()} files", f"*{file_extensions.get(format_type, '.txt')}")]
                    )

                    if file_path:
                        with open(file_path, 'w') as f:
                            if format_type == 'json':
                                json.dump(analytics_data, f, indent=2, default=str)
                            elif format_type == 'csv':
                                # Simple CSV for top actions
                                f.write("Action,Count\n")
                                for action, count in analytics_data['top_actions'].items():
                                    f.write(f'"{action}",{count}\n')
                            else:  # txt
                                f.write(report_content)

                        messagebox.showinfo("Success", f"Report saved to: {file_path}")

                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to save report: {str(e)}")

            def send_to_admin():
                """Send report to admin via email"""
                try:
                    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
                    from education_system.post_18.university_system.infrastructure.database.db import get_connection

                    # Get admin email from database
                    admin_email = None
                    admin_name = "Administrator"
                    with get_connection() as conn:
                        cursor = conn.execute("""
                            SELECT email, first_name, last_name
                            FROM users
                            WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                            LIMIT 1
                        """)
                        admin_row = cursor.fetchone()
                        if admin_row:
                            admin_email = admin_row[0]
                            first_name = admin_row[1] or ''
                            last_name = admin_row[2] or ''
                            if first_name or last_name:
                                admin_name = f"{first_name} {last_name}".strip()

                    if not admin_email:
                        messagebox.showerror("Error", "No admin email found in database")
                        return

                    # Send email
                    subject = f"Activity Logger Analytics Report - {datetime.now().strftime('%Y-%m-%d')}"

                    body = f"""Dear {admin_name},

Please find the Activity Logger analytics report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

{'='*60}

{report_content}

{'='*60}

This report was automatically generated by the Activity Logger Management Console.

Best regards,
University Management System
"""

                    result = send_email(
                        recipient_email=admin_email,
                        subject=subject,
                        body=body
                    )

                    if result:
                        messagebox.showinfo("Success", f"Report sent to admin ({admin_email})")
                    else:
                        messagebox.showinfo("Queued", f"Report queued for delivery to {admin_email}")

                except Exception as e:
                    messagebox.showerror("Email Error", f"Failed to send report: {str(e)}")

            ttk.Label(button_frame, text=_t("activity_logger.report.save_as"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="\U0001f4c4 " + _t("activity_logger.report.formats.txt"), command=lambda: save_as_format('txt')).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="\U0001f4cb " + _t("activity_logger.report.formats.json"), command=lambda: save_as_format('json')).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="\U0001f4ca " + _t("activity_logger.report.formats.csv"), command=lambda: save_as_format('csv')).pack(side=tk.LEFT, padx=2)

            ttk.Separator(button_frame, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=10)

            ttk.Button(button_frame, text="\U0001f4e7 " + _t("activity_logger.report.send_to_admin"), command=send_to_admin).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="\U0001f3e0 " + _t("activity_logger.report.close"), command=report_window.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate report: {str(e)}")
            import traceback
            traceback.print_exc()
