import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

from education_system.university_system.utils.logging.gui.helpers import _t


class ApiManagementMixin:
    """Mixin providing API management functionality."""

    def start_api_server(self):
        """Start the Flask API server - not available"""
        messagebox.showinfo(_t("log_management.api_server.title"), _t("log_management.api_server.removed"))

    def stop_api_server(self):
        """Stop the Flask API server - not available"""
        messagebox.showinfo(_t("log_management.api_server.title"), _t("log_management.api_server.removed"))

    def view_api_stats(self, log_manager):
        """View API usage statistics"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title(_t("log_management.dialogs.api_stats"))
        stats_window.geometry("600x400")

        ttk.Label(stats_window, text=_t("log_management.api_stats.title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Create stats display
        stats_text = scrolledtext.ScrolledText(stats_window, wrap=tk.WORD)
        stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # API has been removed from the system
        api_stats = """API Configuration Status
    ========================================

    Note: The API has been removed from this system.
    Log management is available through the GUI and CLI interfaces only.
    """

        stats_text.insert("1.0", api_stats)
        stats_text.config(state=tk.DISABLED)

        ttk.Button(stats_window, text=_t("log_management.buttons.close"), command=stats_window.destroy).pack(pady=10)

    def refresh_api_stats(self, stats_text, log_manager):
        """Refresh API statistics display with actual data from activity logs"""
        stats_text.config(state=tk.NORMAL)
        stats_text.delete("1.0", tk.END)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Try to get API stats from activity logs
            from education_system.university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                # Create API tracking table if not exists
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS api_request_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        endpoint TEXT,
                        method TEXT,
                        status_code INTEGER,
                        response_time_ms REAL,
                        user_id INTEGER,
                        ip_address TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Get endpoint statistics
                endpoint_stats = conn.execute("""
                    SELECT endpoint, COUNT(*) as count,
                           AVG(response_time_ms) as avg_time,
                           SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
                    FROM api_request_log
                    WHERE timestamp >= datetime('now', '-24 hours')
                    GROUP BY endpoint
                    ORDER BY count DESC
                    LIMIT 10
                """).fetchall()

                # Get total stats
                total_stats = conn.execute("""
                    SELECT COUNT(*) as total,
                           AVG(response_time_ms) as avg_time,
                           SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors,
                           SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) as success
                    FROM api_request_log
                    WHERE timestamp >= datetime('now', '-24 hours')
                """).fetchone()

                # Get hourly breakdown
                hourly_stats = conn.execute("""
                    SELECT strftime('%H:00', timestamp) as hour, COUNT(*) as count
                    FROM api_request_log
                    WHERE timestamp >= datetime('now', '-24 hours')
                    GROUP BY hour
                    ORDER BY hour
                """).fetchall()

                # Get top users
                user_stats = conn.execute("""
                    SELECT user_id, COUNT(*) as count
                    FROM api_request_log
                    WHERE timestamp >= datetime('now', '-24 hours') AND user_id IS NOT NULL
                    GROUP BY user_id
                    ORDER BY count DESC
                    LIMIT 5
                """).fetchall()

            # Build stats display
            stats = [f"API Usage Statistics (Refreshed: {current_time})", "=" * 60, ""]

            # Summary
            if total_stats and total_stats[0]:
                total, avg_time, errors, success = total_stats
                error_rate = (errors / total * 100) if total > 0 else 0
                stats.append("SUMMARY (Last 24 Hours)")
                stats.append("-" * 40)
                stats.append(f"  Total Requests:    {total or 0:,}")
                stats.append(f"  Successful (2xx):  {success or 0:,}")
                stats.append(f"  Errors (4xx/5xx):  {errors or 0:,}")
                stats.append(f"  Error Rate:        {error_rate:.1f}%")
                stats.append(f"  Avg Response Time: {avg_time or 0:.1f}ms")
            else:
                stats.append("SUMMARY (Last 24 Hours)")
                stats.append("-" * 40)
                stats.append("  No API requests recorded yet")

            stats.append("")
            stats.append("ENDPOINT BREAKDOWN")
            stats.append("-" * 40)

            if endpoint_stats:
                stats.append(f"{'Endpoint':<30} {'Count':>8} {'Avg(ms)':>10} {'Errors':>8}")
                stats.append("-" * 60)
                for row in endpoint_stats:
                    endpoint, count, avg_time, errors = row
                    stats.append(f"{endpoint:<30} {count:>8} {avg_time or 0:>10.1f} {errors or 0:>8}")
            else:
                stats.append("  No endpoint data available")

            stats.append("")
            stats.append("HOURLY TRAFFIC")
            stats.append("-" * 40)

            if hourly_stats:
                for hour, count in hourly_stats:
                    bar = "█" * min(count // 10, 30)
                    stats.append(f"  {hour}: {bar} ({count})")
            else:
                stats.append("  No hourly data available")

            stats.append("")
            stats.append("TOP USERS BY REQUEST COUNT")
            stats.append("-" * 40)

            if user_stats:
                for user_id, count in user_stats:
                    stats.append(f"  User {user_id}: {count} requests")
            else:
                stats.append("  No user data available")

            stats.append("")
            stats.append("Status: API tracking active")

            refreshed_stats = "\n".join(stats)

        except Exception as e:
            refreshed_stats = f"""API Usage Statistics (Refreshed: {current_time})
{'='*60}

Error loading API statistics: {e}

To enable API tracking, ensure the api_request_log table exists
and your API endpoints log requests to it.

Example logging code for Flask:
    @app.after_request
    def log_request(response):
        # Log to api_request_log table
        return response
"""

        stats_text.insert("1.0", refreshed_stats)
        stats_text.config(state=tk.DISABLED)

    def toggle_api_gui(self):
        """GUI version of API toggle"""
        if not self.log_manager:
            messagebox.showerror("Error", "Log manager not available")
            return

        current_status = self.log_manager.config.get('api_enabled', False)
        new_status = not current_status

        action = "enable" if new_status else "disable"
        if messagebox.askyesno("Confirm", f"Are you sure you want to {action} the API?"):
            self.log_manager.config.set('api_enabled', new_status)

            status_text = "enabled" if new_status else "disabled"
            message = f"API has been {status_text}"

            if new_status:
                message += "\n\nNote: API has been removed from the system"

            messagebox.showinfo("API Status", message)

    def generate_api_key_gui(self):
        """GUI version of API key generation"""
        if not self.log_manager:
            messagebox.showerror("Error", "Log manager not available")
            return

        if messagebox.askyesno("Generate API Key",
                              "Generate a new API key?\n"
                              "This will invalidate the current key."):

            import secrets
            new_key = secrets.token_urlsafe(32)

            self.log_manager.config.set('api_secret_key', new_key)

            # Show key in a dialog
            key_window = tk.Toplevel(self.root)
            key_window.title(_t("log_management.dialogs.api_key_generated"))
            key_window.geometry("600x200")

            ttk.Label(key_window, text=_t("log_management.config.api_key_generated"),
                     font=("Arial", 14, "bold")).pack(pady=10)

            ttk.Label(key_window, text=_t("log_management.config.api_key_message"),
                     foreground="red").pack(pady=5)

            key_frame = ttk.Frame(key_window)
            key_frame.pack(fill=tk.X, padx=10, pady=10)

            key_entry = ttk.Entry(key_frame, width=60)
            key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            key_entry.insert(0, new_key)
            key_entry.config(state='readonly')

            def copy_key():
                key_window.clipboard_clear()
                key_window.clipboard_append(new_key)
                messagebox.showinfo("Copied", "API key copied to clipboard")

            ttk.Button(key_frame, text="Copy", command=copy_key).pack(side=tk.RIGHT, padx=(5, 0))

            ttk.Button(key_window, text=_t("log_management.buttons.close"), command=key_window.destroy).pack(pady=10)

    def show_api_docs_gui(self):
        """GUI version of API documentation"""
        docs_window = tk.Toplevel(self.root)
        docs_window.title(_t("log_management.dialogs.api_docs"))
        docs_window.geometry("900x700")

        ttk.Label(docs_window, text=_t("log_management.dialogs.api_docs"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Create notebook for different sections
        docs_notebook = ttk.Notebook(docs_window)
        docs_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Overview tab
        overview_frame = ttk.Frame(docs_notebook)
        docs_notebook.add(overview_frame, text="Overview")

        overview_text = scrolledtext.ScrolledText(overview_frame, wrap=tk.WORD, font=("Courier", 10))
        overview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        overview_content = """Log Management API Overview
============================

Note: The API has been removed from this system.
Log management is available through the GUI and CLI interfaces only.
"""

        overview_text.insert("1.0", overview_content)
        overview_text.config(state=tk.DISABLED)

        # Endpoints tab
        endpoints_frame = ttk.Frame(docs_notebook)
        docs_notebook.add(endpoints_frame, text="Endpoints")

        endpoints_text = scrolledtext.ScrolledText(endpoints_frame, wrap=tk.WORD, font=("Courier", 9))
        endpoints_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        endpoints_content = """API Endpoints Reference
========================

Authentication:
POST /api/auth/login
  Body: {"username": "user", "password": "pass"}
  Returns: {"token": "jwt_token", "expires_in": 86400}

Log Operations:
POST /api/logs/search
  Headers: Authorization: Bearer <token>
  Body: {"date_from": "2024-01-01", "user_id": "admin", "limit": 100}

GET /api/logs/recent?hours=24&limit=50
  Headers: Authorization: Bearer <token>

GET /api/logs/user/{user_id}?days=7&limit=100
  Headers: Authorization: Bearer <token>

Analytics:
GET /api/analytics/summary?days=7
  Headers: Authorization: Bearer <token>

GET /api/analytics/user/{user_id}?days=30
  Headers: Authorization: Bearer <token>

POST /api/analytics/chart
  Headers: Authorization: Bearer <token>
  Body: {"days": 7, "type": "daily"}

Alerts:
GET /api/alerts?hours=24
  Headers: Authorization: Bearer <token>

POST /api/alerts/check
  Headers: Authorization: Bearer <token>

Export:
POST /api/export/logs
  Headers: Authorization: Bearer <token>
  Body: {"filters": {...}, "format": "json|csv|excel"}

System:
GET /api/system/status
  Headers: Authorization: Bearer <token>

GET /api/config
  Headers: Authorization: Bearer <token>

PUT /api/config
  Headers: Authorization: Bearer <token>
  Body: {"retention_days": 90, "enable_alerts": true}

Health:
GET /api/health
  No authentication required
  Returns: {"status": "healthy", "timestamp": "..."}
"""

        endpoints_text.insert("1.0", endpoints_content)
        endpoints_text.config(state=tk.DISABLED)

        # Examples tab
        examples_frame = ttk.Frame(docs_notebook)
        docs_notebook.add(examples_frame, text="Examples")

        examples_text = scrolledtext.ScrolledText(examples_frame, wrap=tk.WORD, font=("Courier", 9))
        examples_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        examples_content = """API Usage Examples
===================

Note: The API has been removed from this system.
Log management is available through the GUI and CLI interfaces only.
"""

        examples_text.insert("1.0", examples_content)
        examples_text.config(state=tk.DISABLED)

        ttk.Button(docs_window, text=_t("log_management.buttons.close"), command=docs_window.destroy).pack(pady=10)

    def view_scheduled_tasks_gui(self):
        """GUI version of viewing scheduled tasks"""
        tasks_window = tk.Toplevel(self.root)
        tasks_window.title(_t("log_management.dialogs.scheduled_tasks"))
        tasks_window.geometry("600x400")

        ttk.Label(tasks_window, text=_t("log_management.scheduled_tasks.title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Tasks display
        tasks_frame = ttk.LabelFrame(tasks_window, text="Current Scheduled Tasks")
        tasks_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tasks_text = scrolledtext.ScrolledText(tasks_frame, wrap=tk.WORD, height=15)
        tasks_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Build tasks overview
        tasks_overview = """Scheduled Tasks Status
=======================

System Tasks:
- Daily log archival at 02:00
- Daily log cleanup at 03:00
- Hourly alert checks

Email Notifications:
"""

        if self.log_manager.config.get('alert_email'):
            tasks_overview += f"- Daily email reports to: {self.log_manager.config.get('alert_email')}\n"

        if self.log_manager.config.get('weekly_report_email'):
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_index = self.log_manager.config.get('weekly_report_day', 1) - 1
            tasks_overview += f"- Weekly analytics reports to: {self.log_manager.config.get('weekly_report_email')} ({day_names[day_index]})\n"

        if self.log_manager.config.get('security_alert_email'):
            threshold = self.log_manager.config.get('failed_login_threshold', 5)
            tasks_overview += f"- Security alerts to: {self.log_manager.config.get('security_alert_email')} (threshold: {threshold})\n"

        if not any([self.log_manager.config.get('alert_email'),
                   self.log_manager.config.get('weekly_report_email'),
                   self.log_manager.config.get('security_alert_email')]):
            tasks_overview += "- No email notifications configured\n"

        tasks_overview += f"""
API Status:
- API Server: {'Running' if self.log_manager.config.get('api_enabled') else 'Stopped'}

Real-time Monitoring:
- Status: {'Active' if self.log_manager.monitor.running else 'Inactive'}
- Subscribers: {len(self.log_manager.monitor.subscribers)}

Configuration:
- Log retention: {self.log_manager.config.get('retention_days', 90)} days
- Auto archive: {self.log_manager.config.get('auto_archive_days', 30)} days
- Alerts enabled: {self.log_manager.config.get('enable_alerts', True)}
"""

        tasks_text.insert("1.0", tasks_overview)
        tasks_text.config(state=tk.DISABLED)

        ttk.Button(tasks_window, text=_t("log_management.buttons.close"), command=tasks_window.destroy).pack(pady=10)

    def show_api_docs(self):
        """Show API documentation"""
        docs_window = tk.Toplevel(self.root)
        docs_window.title(_t("log_management.dialogs.api_docs"))
        docs_window.geometry("800x600")

        ttk.Label(docs_window, text=_t("log_management.dialogs.api_docs"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        docs_text = scrolledtext.ScrolledText(docs_window, wrap=tk.WORD, font=("Courier", 10))
        docs_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        api_docs = """
Log Management API Endpoints
============================

Authentication:
POST /api/auth/login - Get authentication token
  Body: {"username": "user", "password": "pass"}
  Returns: {"token": "jwt_token", "expires_in": 86400}

Log Operations:
POST /api/logs/search - Search logs with filters
  Headers: Authorization: Bearer <token>
  Body: {"date_from": "2024-01-01", "user_id": "admin", "limit": 100}

GET /api/logs/recent?hours=24&limit=50 - Get recent logs
  Headers: Authorization: Bearer <token>

GET /api/logs/user/{user_id}?days=7&limit=100 - Get logs for specific user
  Headers: Authorization: Bearer <token>

Analytics:
GET /api/analytics/summary?days=7 - Get activity summary
  Headers: Authorization: Bearer <token>

GET /api/analytics/user/{user_id}?days=30 - Get user analytics
  Headers: Authorization: Bearer <token>

POST /api/analytics/chart - Generate activity chart
  Headers: Authorization: Bearer <token>
  Body: {"days": 7, "type": "daily"}

Alerts:
GET /api/alerts?hours=24 - Get recent alerts
  Headers: Authorization: Bearer <token>

POST /api/alerts/check - Trigger alert checks
  Headers: Authorization: Bearer <token>

Export:
POST /api/export/logs - Export logs with filters
  Headers: Authorization: Bearer <token>
  Body: {"filters": {...}, "format": "json|csv|excel"}

System:
GET /api/system/status - Get system status
  Headers: Authorization: Bearer <token>

GET /api/config - Get configuration
  Headers: Authorization: Bearer <token>

PUT /api/config - Update configuration
  Headers: Authorization: Bearer <token>
  Body: {"retention_days": 90, "enable_alerts": true}

Webhooks:
POST /api/webhooks/log - Receive external log entries
  Headers: X-Webhook-Key: <webhook_secret>
  Body: {log_entry_data}

Health:
GET /api/health - Health check (no auth required)
  Returns: {"status": "healthy", "timestamp": "..."}

Error Responses:
All endpoints return appropriate HTTP status codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error

Response format:
{
  "success": true/false,
  "data": {...},
  "error": "error message if applicable"
}
"""

        docs_text.insert("1.0", api_docs)
        docs_text.config(state=tk.DISABLED)
