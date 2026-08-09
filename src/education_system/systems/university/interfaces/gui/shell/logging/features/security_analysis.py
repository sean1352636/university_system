import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from collections import defaultdict
from datetime import datetime, timedelta

from education_system.systems.university.interfaces.gui.shell.logging.helpers import _t


class SecurityAnalysisMixin:
    """Mixin providing security analysis functionality."""

    def security_analysis_menu_gui(self):
        """GUI version of security analysis menu"""
        security_window = tk.Toplevel(self.root)
        security_window.title(_t("log_management.security_analysis.title"))
        security_window.geometry("800x600")

        ttk.Label(security_window, text=_t("log_management.security_analysis.tools_title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Analysis buttons
        button_frame = ttk.Frame(security_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(button_frame, text=_t("log_management.security_analysis.failed_logins"),
                  command=lambda: self.analyze_failed_logins_gui(security_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.security_analysis.unusual_activity"),
                  command=lambda: self.detect_unusual_activity_gui(security_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.security_analysis.admin_audit"),
                  command=lambda: self.audit_admin_actions_gui(security_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.security_analysis.user_behavior"),
                  command=lambda: self.analyze_user_behavior_gui(security_window)).pack(side=tk.LEFT, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(security_window, text=_t("log_management.security_analysis.results"))
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.security_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                              font=("Courier", 10),
                                                              fg="#000000", bg="#FFFFFF")
        self.security_results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def analyze_failed_logins_gui(self, parent_window):
        """GUI version of failed login analysis"""
        try:
            # Get failed logins from last 24 hours
            filters = {
                'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d'),
                'action': 'login',
                'status': 'failure'
            }

            failed_logins = self.log_manager.db.search_logs(filters, limit=1000)

            if not failed_logins:
                output = _t("log_management.security_analysis.no_failed_logins")
            else:
                # Analyze by user
                user_failures = defaultdict(int)
                for login in failed_logins:
                    user_failures[login['username']] += 1

                output = f"""Failed Login Analysis - Last 24 Hours
{'='*45}

Total failed logins: {len(failed_logins)}
Unique users with failures: {len(user_failures)}

Top users with failed logins:
{'-'*35}
"""

                sorted_failures = sorted(user_failures.items(), key=lambda x: x[1], reverse=True)
                for user, count in sorted_failures[:10]:
                    output += f"{user:<25} {count:>8}\n"

                # Users with excessive failures
                suspicious_users = [user for user, count in user_failures.items() if count >= 5]
                if suspicious_users:
                    output += "\n⚠️ Users with 5+ failed logins (potential brute force):\n"
                    for user in suspicious_users:
                        output += f"  {user}: {user_failures[user]} failures\n"

            self.security_results_text.delete("1.0", tk.END)
            self.security_results_text.insert("1.0", output)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.security_analysis.error_failed_logins", error=str(e)))

    def detect_unusual_activity_gui(self, parent_window):
        """GUI version of unusual activity detection"""
        try:
            # Get activities from last 7 days
            filters = {
                'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            }

            activities = self.log_manager.db.search_logs(filters, limit=5000)

            if not activities:
                output = _t("log_management.security_analysis.no_activities")
            else:
                # Analyze by hour
                hour_activity = defaultdict(int)
                unusual_hours = []

                for activity in activities:
                    try:
                        hour = datetime.fromisoformat(activity['timestamp']).hour
                        hour_activity[hour] += 1

                        # Flag activities between 2-6 AM as unusual
                        if 2 <= hour <= 6:
                            unusual_hours.append(activity)
                    except (ValueError, KeyError, TypeError):
                        continue

                output = "Unusual Activity Detection - Last 7 Days\n"
                output += "="*42 + "\n\n"
                output += "Activity by hour of day:\n"
                output += f"{'Hour':<6} {'Count':<8} {'Chart'}\n"
                output += "-" * 30 + "\n"

                for hour in range(24):
                    count = hour_activity.get(hour, 0)
                    bar = "█" * min(count // 10, 50)  # Limit bar length
                    output += f"{hour:02d}:00  {count:<8} {bar}\n"

                if unusual_hours:
                    output += f"\n⚠️ Activities during unusual hours (2-6 AM): {len(unusual_hours)}\n"
                    output += "Recent unusual activities:\n"
                    recent_unusual = unusual_hours[-5:]  # Show last 5
                    for activity in recent_unusual:
                        timestamp = activity['timestamp'][:19]
                        user = activity['username']
                        action = activity['action']
                        output += f"  {timestamp} - {user}: {action}\n"

            self.security_results_text.delete("1.0", tk.END)
            self.security_results_text.insert("1.0", output)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.security_analysis.error_unusual_activity", error=str(e)))

    def audit_admin_actions_gui(self, parent_window):
        """GUI version of admin action audit"""
        try:
            # Get admin actions from last 30 days
            filters = {
                'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            }

            admin_actions = self.log_manager.db.search_logs(filters, limit=1000)

            if not admin_actions:
                output = _t("log_management.security_analysis.no_admin_actions")
            else:
                # Categorize actions
                sensitive_actions = ['delete', 'user_management', 'system_config']

                sensitive_count = 0
                regular_count = 0
                action_breakdown = defaultdict(int)
                admin_breakdown = defaultdict(int)

                for action in admin_actions:
                    action_type = action['action']
                    admin_user = action['username']

                    action_breakdown[action_type] += 1
                    admin_breakdown[admin_user] += 1

                    if action_type in sensitive_actions:
                        sensitive_count += 1
                    else:
                        regular_count += 1

                output = f"""Admin Action Audit - Last 30 Days
{'='*38}

Total admin actions: {len(admin_actions)}
Sensitive actions: {sensitive_count}
Regular actions: {regular_count}

Actions by type:
{'-'*20}
"""

                for action_type, count in sorted(action_breakdown.items(), key=lambda x: x[1], reverse=True):
                    sensitivity = "⚠️" if action_type in sensitive_actions else "✅"
                    output += f"{sensitivity} {action_type:<20} {count:>8}\n"

                output += f"\nActions by admin:\n{'-'*20}\n"
                for admin, count in sorted(admin_breakdown.items(), key=lambda x: x[1], reverse=True):
                    output += f"{admin:<25} {count:>8}\n"

                # Show recent sensitive actions
                recent_sensitive = [a for a in admin_actions if a['action'] in sensitive_actions][-10:]
                if recent_sensitive:
                    output += f"\nRecent sensitive admin actions:\n{'-'*35}\n"
                    for action in recent_sensitive:
                        timestamp = action['timestamp'][:19]
                        user = action['username']
                        action_type = action['action']
                        module = action['module']
                        output += f"{timestamp} - {user}: {action_type} on {module}\n"

            self.security_results_text.delete("1.0", tk.END)
            self.security_results_text.insert("1.0", output)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.security_analysis.error_admin_audit", error=str(e)))

    def analyze_user_behavior_gui(self, parent_window):
        """GUI version of user behavior analysis"""
        try:
            import logging as _logging

            # Get activities from last 7 days
            filters = {
                'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            }

            activities = self.log_manager.db.search_logs(filters, limit=5000)

            if not activities:
                output = _t("log_management.security_analysis.no_activities")
            else:
                # Analyze user patterns
                user_stats = defaultdict(lambda: {
                    'total_actions': 0,
                    'unique_modules': set(),
                    'actions_by_hour': defaultdict(int),
                    'success_rate': 0,
                    'failures': 0
                })

                for activity in activities:
                    user = activity['username']
                    stats = user_stats[user]

                    stats['total_actions'] += 1
                    stats['unique_modules'].add(activity['module'])

                    try:
                        hour = datetime.fromisoformat(activity['timestamp']).hour
                        stats['actions_by_hour'][hour] += 1
                    except Exception as e:
                        _logging.debug(f"Failed to parse activity timestamp: {e}")

                    if activity['status'] == 'failure':
                        stats['failures'] += 1

                # Calculate success rates
                for user, stats in user_stats.items():
                    if stats['total_actions'] > 0:
                        stats['success_rate'] = ((stats['total_actions'] - stats['failures']) / stats['total_actions']) * 100
                    stats['unique_modules'] = len(stats['unique_modules'])

                # Sort by activity level
                sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['total_actions'], reverse=True)

                output = f"""User Behavior Analysis - Last 7 Days
{'='*40}

Analysis for {len(sorted_users)} users:

{'User':<15} {'Actions':<8} {'Modules':<8} {'Success%':<8} {'Failures':<8}
{'-'*60}
"""

                for user, stats in sorted_users[:15]:  # Top 15 users
                    output += f"{user:<15} {stats['total_actions']:<8} {stats['unique_modules']:<8} "
                    output += f"{stats['success_rate']:<7.1f}% {stats['failures']:<8}\n"

                # Identify unusual patterns
                output += f"\nUnusual patterns detected:\n{'-'*30}\n"

                # Users with low success rates
                low_success_users = [(user, stats) for user, stats in user_stats.items()
                                    if stats['success_rate'] < 80 and stats['total_actions'] > 10]

                if low_success_users:
                    output += "Users with low success rates (<80%):\n"
                    for user, stats in low_success_users:
                        output += f"  {user}: {stats['success_rate']:.1f}% success rate ({stats['failures']} failures)\n"

                # Users with very high activity
                high_activity_users = [(user, stats) for user, stats in user_stats.items()
                                      if stats['total_actions'] > 100]

                if high_activity_users:
                    output += "\nUsers with very high activity (>100 actions):\n"
                    for user, stats in high_activity_users:
                        output += f"  {user}: {stats['total_actions']} actions\n"

            self.security_results_text.delete("1.0", tk.END)
            self.security_results_text.insert("1.0", output)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.security_analysis.error_user_behavior", error=str(e)))
