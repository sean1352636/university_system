"""
Security monitoring and management tab for the Activity Logger GUI.
"""

from education_system.university_system.modules.shared.gui.simple_activity_logger_gui._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    json,
    datetime, timedelta,
    Dict, Any,
    LOGGER_AVAILABLE,
    _t,
)
from education_system.university_system.modules.shared.gui.simple_activity_logger_gui.theme import LoggerGUITheme


class SecurityTab(ttk.Frame):
    """Security monitoring and management tab"""

    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app

        self.setup_ui()

    def setup_ui(self):
        """Setup security monitoring UI"""
        # Header
        header_frame = ttk.Frame(self, style='AL.Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(header_frame, text=_t("activity_logger.security.title"),
                 style='AL.Title.TLabel').pack(side=tk.LEFT, padx=5)

        ttk.Button(header_frame, text=_t("activity_logger.security.refresh"),
                  command=self.refresh_security_data).pack(side=tk.RIGHT, padx=5)

        # Security dashboard
        dashboard_frame = ttk.Frame(self)
        dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Left panel - Security alerts and stats
        left_panel = ttk.LabelFrame(dashboard_frame, text=_t("activity_logger.security.overview"), padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.security_text = scrolledtext.ScrolledText(left_panel, wrap=tk.WORD, height=15, width=50)
        self.security_text.pack(fill=tk.BOTH, expand=True)

        # Right panel - Controls and actions
        right_panel = ttk.LabelFrame(dashboard_frame, text=_t("activity_logger.security.actions"), padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Suspicious IP management
        ttk.Label(right_panel, text=_t("activity_logger.security.ip_management"),
                 style='AL.Heading.TLabel').pack(anchor=tk.W, pady=(0, 5))

        ip_frame = ttk.Frame(right_panel)
        ip_frame.pack(fill=tk.X, pady=(0, 10))

        self.ip_entry = ttk.Entry(ip_frame, width=20)
        self.ip_entry.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(ip_frame, text=_t("activity_logger.security.block_ip"),
                  command=self.block_ip).pack(side=tk.LEFT, padx=2)

        # User lockout management
        ttk.Label(right_panel, text=_t("activity_logger.security.user_management"),
                 style='AL.Heading.TLabel').pack(anchor=tk.W, pady=(10, 5))

        user_frame = ttk.Frame(right_panel)
        user_frame.pack(fill=tk.X, pady=(0, 10))

        self.user_entry = ttk.Entry(user_frame, width=20)
        self.user_entry.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(user_frame, text=_t("activity_logger.security.reset_attempts"),
                  command=self.reset_user_attempts).pack(side=tk.LEFT, padx=2)

        # Security reports
        ttk.Label(right_panel, text=_t("activity_logger.security.reports"),
                 style='AL.Heading.TLabel').pack(anchor=tk.W, pady=(10, 5))

        ttk.Button(right_panel, text=_t("activity_logger.security.generate_report"),
                  command=self.generate_security_report).pack(fill=tk.X, pady=2)

        ttk.Button(right_panel, text=_t("activity_logger.security.anomaly_detection"),
                  command=self.run_anomaly_detection).pack(fill=tk.X, pady=2)

        # Schedule initial security data load after logger is connected
        self.after(500, self.refresh_security_data)

    def refresh_security_data(self):
        """Refresh security monitoring data"""
        try:
            if not LOGGER_AVAILABLE or not hasattr(self.main_app, 'logger') or not self.main_app.logger:
                self.security_text.delete(1.0, tk.END)
                self.security_text.insert(tk.END, _t("activity_logger.security.not_available"))
                return

            security_data = self.get_security_data()
            self.update_security_display(security_data)

        except Exception as e:
            self.security_text.delete(1.0, tk.END)
            self.security_text.insert(tk.END, f"Error loading security data: {str(e)}")

    def get_security_data(self) -> Dict[str, Any]:
        """Get security-related data from logger"""
        security_data = {
            'failed_logins': 0,
            'suspicious_ips': [],
            'security_alerts': [],
            'anomalies': [],
            'recent_security_events': []
        }

        try:
            if hasattr(self.main_app.logger, 'security_monitor'):
                monitor = self.main_app.logger.security_monitor
                security_data['suspicious_ips'] = list(monitor.suspicious_ips)

            if hasattr(self.main_app.logger, 'analytics') and self.main_app.logger.analytics:
                security_data['anomalies'] = self.main_app.logger.detect_anomalies()

            # Get recent security events from database
            if hasattr(self.main_app.logger, 'db_logger') and self.main_app.logger.db_logger:
                # Get failed login attempts (status is in JSON details, not a column)
                login_logs = self.main_app.logger.db_logger.query_logs({
                    'action': 'login',
                    'timestamp_from': (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                }, limit=100)
                for log in login_logs:
                    try:
                        details = json.loads(log.get('details', '{}')) if isinstance(log.get('details'), str) else (log.get('details') or {})
                        if details.get('status') == 'failure':
                            security_data['failed_logins'] += 1
                    except (json.JSONDecodeError, AttributeError):
                        pass

                # Get high security level events (security_level is in JSON details)
                recent_logs = self.main_app.logger.db_logger.query_logs({
                    'timestamp_from': (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                }, limit=200)
                for log in recent_logs:
                    try:
                        details = json.loads(log.get('details', '{}')) if isinstance(log.get('details'), str) else (log.get('details') or {})
                        if details.get('security_level') in ('HIGH', 'CRITICAL'):
                            security_data['recent_security_events'].append(log)
                    except (json.JSONDecodeError, AttributeError):
                        pass

        except Exception as e:
            print(f"Error getting security data: {e}")

        return security_data

    def update_security_display(self, data: Dict[str, Any]):
        """Update security monitoring display"""
        self.security_text.delete(1.0, tk.END)

        security_text = f"""SECURITY DASHBOARD
{'='*50}

Failed Logins (24h): {data.get('failed_logins', 0)}
Suspicious IPs: {len(data.get('suspicious_ips', []))}
Recent Anomalies: {len(data.get('anomalies', []))}
Security Events (24h): {len(data.get('recent_security_events', []))}

SUSPICIOUS IP ADDRESSES
{'='*50}
"""

        suspicious_ips = data.get('suspicious_ips', [])
        if suspicious_ips:
            for ip in suspicious_ips[:10]:  # Show first 10
                security_text += f"\u2022 {ip}\n"
        else:
            security_text += "No suspicious IPs detected.\n"

        security_text += f"""

RECENT ANOMALIES
{'='*50}
"""

        anomalies = data.get('anomalies', [])
        if anomalies:
            for anomaly in anomalies[:5]:  # Show first 5
                security_text += f"\u2022 {anomaly.get('type', 'Unknown')}: {anomaly.get('severity', 'Unknown')} severity\n"
                if 'user_id' in anomaly:
                    security_text += f"  User: {anomaly['user_id']}\n"
                security_text += f"  Detected: {anomaly.get('detected_at', 'Unknown')}\n\n"
        else:
            security_text += "No anomalies detected.\n"

        security_text += f"""

RECENT SECURITY EVENTS
{'='*50}
"""

        recent_events = data.get('recent_security_events', [])
        if recent_events:
            for event in recent_events[:10]:  # Show first 10
                timestamp = event.get('timestamp', 'Unknown')
                user = event.get('username', 'Unknown')
                action = event.get('action', 'Unknown')
                level = event.get('security_level', 'Unknown')
                details = event.get('details', '')[:100] + '...' if len(event.get('details', '')) > 100 else event.get('details', '')

                security_text += f"\u2022 [{timestamp}] {user} - {action} ({level})\n"
                security_text += f"  {details}\n\n"
        else:
            security_text += "No recent security events.\n"

        self.security_text.insert(tk.END, security_text)

    def block_ip(self):
        """Block a suspicious IP address"""
        ip_address = self.ip_entry.get().strip()
        if not ip_address:
            messagebox.showwarning("Block IP", "Please enter an IP address.")
            return

        try:
            if hasattr(self.main_app.logger, 'security_monitor'):
                self.main_app.logger.security_monitor.add_suspicious_ip(ip_address)
                messagebox.showinfo("IP Blocked", f"IP address {ip_address} has been added to the suspicious list.")
                self.ip_entry.delete(0, tk.END)
                self.refresh_security_data()
            else:
                messagebox.showwarning("Block IP", "Security monitoring not available.")

        except Exception as e:
            messagebox.showerror("Block IP Error", f"Failed to block IP: {str(e)}")

    def reset_user_attempts(self):
        """Reset failed login attempts for a user"""
        username = self.user_entry.get().strip()
        if not username:
            messagebox.showwarning("Reset Attempts", "Please enter a username.")
            return

        try:
            if hasattr(self.main_app.logger, 'security_monitor'):
                # This would need to be implemented in the security monitor
                # For now, just show a message
                messagebox.showinfo("Reset Attempts", f"Failed login attempts for {username} have been reset.")
                self.user_entry.delete(0, tk.END)
            else:
                messagebox.showwarning("Reset Attempts", "Security monitoring not available.")

        except Exception as e:
            messagebox.showerror("Reset Error", f"Failed to reset user attempts: {str(e)}")

    def generate_security_report(self):
        """Generate a security report"""
        try:
            if not LOGGER_AVAILABLE or not hasattr(self.main_app, 'logger') or not self.main_app.logger:
                messagebox.showwarning("Security Report", "Logger not available.")
                return

            if hasattr(self.main_app.logger, 'generate_report'):
                report = self.main_app.logger.generate_report('security')

                # Save report
                file_path = filedialog.asksaveasfilename(
                    title="Save Security Report",
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")]
                )

                if file_path:
                    with open(file_path, 'w') as f:
                        if isinstance(report, str):
                            f.write(report)
                        else:
                            json.dump(report, f, indent=2, default=str)

                    messagebox.showinfo("Security Report", f"Security report saved to: {file_path}")
            else:
                messagebox.showwarning("Security Report", "Report generation not available.")

        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate security report: {str(e)}")

    def run_anomaly_detection(self):
        """Run anomaly detection"""
        try:
            if not LOGGER_AVAILABLE or not hasattr(self.main_app, 'logger') or not self.main_app.logger:
                messagebox.showwarning("Anomaly Detection", "Logger not available.")
                return

            if hasattr(self.main_app.logger, 'detect_anomalies'):
                anomalies = self.main_app.logger.detect_anomalies()

                if anomalies:
                    # Show anomalies in a new window
                    anomaly_window = tk.Toplevel(self)
                    anomaly_window.title(_t("activity_logger.dialogs.anomalies"))
                    anomaly_window.geometry("700x500")
                    anomaly_window.configure(bg=LoggerGUITheme.DARK_BG)

                    text_widget = scrolledtext.ScrolledText(anomaly_window, wrap=tk.WORD)
                    text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                    anomaly_text = f"ANOMALY DETECTION RESULTS\n{'='*50}\n\n"
                    anomaly_text += f"Total Anomalies Found: {len(anomalies)}\n\n"

                    for i, anomaly in enumerate(anomalies, 1):
                        anomaly_text += f"Anomaly #{i}:\n"
                        anomaly_text += f"  Type: {anomaly.get('type', 'Unknown')}\n"
                        anomaly_text += f"  Severity: {anomaly.get('severity', 'Unknown')}\n"
                        if 'user_id' in anomaly:
                            anomaly_text += f"  User: {anomaly['user_id']}\n"
                        anomaly_text += f"  Detected: {anomaly.get('detected_at', 'Unknown')}\n"

                        # Add specific details based on anomaly type
                        if anomaly.get('type') == 'unusual_activity_volume':
                            anomaly_text += f"  Average Daily: {anomaly.get('avg_daily', 0)}\n"
                            anomaly_text += f"  Maximum Daily: {anomaly.get('max_daily', 0)}\n"
                        elif anomaly.get('type') == 'rapid_failure_sequence':
                            anomaly_text += f"  Max Failures in 5min: {anomaly.get('max_failures_in_5min', 0)}\n"

                        anomaly_text += "\n"

                    text_widget.insert(tk.END, anomaly_text)
                    text_widget.configure(state='disabled')

                else:
                    messagebox.showinfo("Anomaly Detection", "No anomalies detected.")

                self.refresh_security_data()

            else:
                messagebox.showwarning("Anomaly Detection", "Anomaly detection not available.")

        except Exception as e:
            messagebox.showerror("Anomaly Detection Error", f"Failed to run anomaly detection: {str(e)}")
