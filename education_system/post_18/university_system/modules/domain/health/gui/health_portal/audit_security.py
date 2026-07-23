import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime

from education_system.post_18.university_system.core import paths


class AuditSecurityMixin:
    """Mixin for security audit and access summary features."""

    def create_security_audit(self):
        """Create security audit interface"""
        title = ttk.Label(self.content_frame, text="Security Audit", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        audit_tab = ttk.Frame(notebook)
        notebook.add(audit_tab, text="Audit Log")
        self.create_audit_log_viewer(audit_tab)

        summary_tab = ttk.Frame(notebook)
        notebook.add(summary_tab, text="Access Summary")
        self.create_access_summary(summary_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_audit_log_viewer(self, parent):
        """Create audit log viewer"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding="5")
        filter_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(filter_frame, text="User ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.audit_user_filter = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_user_filter, width=15).grid(row=0, column=1, pady=2, padx=(5, 10))

        ttk.Label(filter_frame, text="Action:").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.audit_action_filter = tk.StringVar()
        action_combo = ttk.Combobox(filter_frame, textvariable=self.audit_action_filter, width=15,
                                   values=['', 'login', 'logout', 'add_health_record', 'view_health_record',
                                          'schedule_appointment', 'record_vaccination'])
        action_combo.grid(row=0, column=3, pady=2, padx=(5, 10))

        ttk.Button(filter_frame, text="Filter", command=self.filter_audit_log).grid(row=0, column=4, padx=5)
        ttk.Button(filter_frame, text="Clear", command=self.clear_audit_filters).grid(row=0, column=5, padx=5)

        self.audit_log_text = scrolledtext.ScrolledText(main_frame, width=100, height=20, font=('Consolas', 9))
        self.audit_log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Button(main_frame, text="Export Audit Log", command=self.export_audit_log).grid(row=2, column=0, pady=10)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        self.load_audit_log()

    def load_audit_log(self):
        """Load audit log from file"""
        try:
            log_file = paths.LOG_DIR / "app.log"
            if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
                log_file = paths.LOG_DIR / "app.log"

            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()

                self.audit_log_text.delete(1.0, tk.END)
                self.audit_log_text.insert(tk.END, log_content)

                self.audit_log_text.see(tk.END)
            else:
                self.audit_log_text.delete(1.0, tk.END)
                self.audit_log_text.insert(tk.END, "No audit log file found. Audit events will be logged here as they occur.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audit log: {str(e)}")

    def filter_audit_log(self):
        """Filter audit log based on criteria"""
        user_filter = self.audit_user_filter.get().strip()
        action_filter = self.audit_action_filter.get().strip()

        if not user_filter and not action_filter:
            self.load_audit_log()
            return

        try:
            log_file = paths.LOG_DIR / "app.log"
            if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
                log_file = paths.LOG_DIR / "app.log"

            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                filtered_lines = []
                for line in lines:
                    include_line = True

                    if user_filter and f"USER:{user_filter}" not in line:
                        include_line = False

                    if action_filter and f"ACTION:{action_filter}" not in line:
                        include_line = False

                    if include_line:
                        filtered_lines.append(line)

                self.audit_log_text.delete(1.0, tk.END)
                self.audit_log_text.insert(tk.END, ''.join(filtered_lines))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to filter audit log: {str(e)}")

    def clear_audit_filters(self):
        """Clear audit log filters"""
        self.audit_user_filter.set("")
        self.audit_action_filter.set("")
        self.load_audit_log()

    def export_audit_log(self):
        """Export audit log to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Audit Log"
            )

            if filename:
                log_content = self.audit_log_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)

                self.log_audit_event('export_audit_log', 'audit_export', filename)
                messagebox.showinfo("Success", f"Audit log exported to: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export audit log: {str(e)}")

    def create_access_summary(self, parent):
        """Create access summary report"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.access_summary_text = scrolledtext.ScrolledText(main_frame, width=80, height=25, font=('Consolas', 10))
        self.access_summary_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Button(main_frame, text="Generate Access Summary", command=self.generate_access_summary).grid(row=1, column=0, pady=10)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self.generate_access_summary()

    def generate_access_summary(self):
        """Generate access summary report"""
        try:
            self.access_summary_text.delete(1.0, tk.END)

            report = []
            report.append("SYSTEM ACCESS SUMMARY")
            report.append("=" * 30)
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")

            log_file = paths.LOG_DIR / "app.log"
            if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
                log_file = paths.LOG_DIR / "app.log"

            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        log_content = f.read()

                    login_count = log_content.count("ACTION:login")
                    logout_count = log_content.count("ACTION:logout")
                    health_record_access = log_content.count("ACTION:add_health_record") + log_content.count("ACTION:view_health_record")
                    appointment_access = log_content.count("ACTION:schedule_appointment")
                    vaccination_access = log_content.count("ACTION:record_vaccination")

                    report.append("ACTIVITY SUMMARY")
                    report.append("-" * 20)
                    report.append(f"Login Events: {login_count}")
                    report.append(f"Logout Events: {logout_count}")
                    report.append(f"Health Record Access: {health_record_access}")
                    report.append(f"Appointment Activities: {appointment_access}")
                    report.append(f"Vaccination Activities: {vaccination_access}")
                    report.append("")

                    users = {}
                    for line in log_content.split('\n'):
                        if 'USER:' in line and 'ACTION:' in line:
                            try:
                                user_part = line.split('USER:')[1].split(' ')[0]
                                action_part = line.split('ACTION:')[1].split(' ')[0]
                                if user_part not in users:
                                    users[user_part] = {}
                                if action_part not in users[user_part]:
                                    users[user_part][action_part] = 0
                                users[user_part][action_part] += 1
                            except (IndexError, ValueError):
                                continue

                    if users:
                        report.append("USER ACTIVITY BREAKDOWN")
                        report.append("-" * 25)
                        for user, actions in users.items():
                            report.append(f"{user}:")
                            for action, count in actions.items():
                                report.append(f"  {action}: {count}")
                            report.append("")

                except Exception as e:
                    report.append(f"Error reading audit log: {str(e)}")
                    report.append("")
            else:
                report.append("No audit log file found.")
                report.append("")

            try:
                conn = self.get_connection()
                cursor = conn.cursor()

                tables = ['students', 'health_records', 'vaccination_records', 'health_appointments']
                report.append("DATABASE SUMMARY")
                report.append("-" * 20)
                for table in tables:
                    from education_system.post_18.university_system.core.sql_safety import validate_table_name
                    validated_table = validate_table_name(table, conn=conn)
                    cursor.execute("SELECT COUNT(*) FROM [" + validated_table + "]")
                    count = cursor.fetchone()[0]
                    report.append(f"{table.replace('_', ' ').title()}: {count} records")

                conn.close()
                report.append("")

            except Exception as e:
                report.append(f"Error accessing database: {str(e)}")
                report.append("")

            report.append("SECURITY RECOMMENDATIONS")
            report.append("-" * 25)
            report.append("\u2022 Regularly review audit logs for suspicious activity")
            report.append("\u2022 Monitor failed login attempts")
            report.append("\u2022 Ensure strong password policies are enforced")
            report.append("\u2022 Implement session timeouts")
            report.append("\u2022 Regular backup of audit logs")
            report.append("\u2022 Review user access permissions periodically")

            self.access_summary_text.insert(tk.END, "\n".join(report))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate access summary: {str(e)}")
