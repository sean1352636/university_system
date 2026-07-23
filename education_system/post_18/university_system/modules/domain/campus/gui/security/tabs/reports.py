"""Reports and analytics tab mixin."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import logging
from datetime import datetime

from education_system.post_18.university_system.core.i18n import get_text as _t

from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.report_preview import ReportPreviewDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.utils import send_notification_email

logger = logging.getLogger(__name__)


class ReportsMixin:
    """Reports and analytics view methods."""

    def show_reports(self):
        """Display reports view"""
        self.clear_content()
        self.create_section_header("Reports & Statistics")

        # Statistics frame
        stats_frame = tk.Frame(self.content_frame, bg=self.colors["bg_medium"], padx=20, pady=20)
        stats_frame.pack(fill="x", pady=10)

        tk.Label(stats_frame, text=_t("police_station.reports.station_statistics"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(anchor="w", pady=(0, 15))

        # Calculate statistics
        total_cases = len(self.data["cases"])
        open_cases = len([c for c in self.data["cases"] if c.get("status") in ["Open", "In Progress"]])
        closed_cases = len([c for c in self.data["cases"] if c.get("status") == "Closed"])
        total_officers = len(self.data["officers"])
        active_officers = len([o for o in self.data["officers"] if o.get("status") == "Active"])
        total_complaints = len(self.data["complaints"])
        resolved_complaints = len([c for c in self.data["complaints"] if c.get("status") == "Resolved"])
        total_patrols = len(self.data.get("patrol_logs", []))

        student_incidents = len([c for c in self.data["cases"] if c.get("is_student_involved")])

        stats_data = [
            ("Total Incidents", total_cases),
            ("Active Incidents", open_cases),
            ("Resolved Incidents", closed_cases),
            ("Student-Involved Incidents", student_incidents),
            ("Resolution Rate", f"{(closed_cases/total_cases*100):.1f}%" if total_cases > 0 else "N/A"),
            ("", ""),
            ("Campus Officers", total_officers),
            ("Officers on Duty", active_officers),
            ("", ""),
            ("Safety Concerns Filed", total_complaints),
            ("Concerns Resolved", resolved_complaints),
            ("Response Rate", f"{(resolved_complaints/total_complaints*100):.1f}%" if total_complaints > 0 else "N/A"),
            ("", ""),
            ("Persons of Interest", len(self.data["criminals"])),
            ("Evidence Items Logged", len(self.data["evidence"])),
            ("Campus Patrol Entries", total_patrols),
            ("Emergency Alerts Issued", len(self.data.get("emergency_alerts", []))),
        ]

        for label, value in stats_data:
            if label == "":
                tk.Frame(stats_frame, height=10, bg=self.colors["bg_medium"]).pack()
                continue

            row = tk.Frame(stats_frame, bg=self.colors["bg_medium"])
            row.pack(fill="x", pady=3)

            tk.Label(row, text=label, font=("Segoe UI", 11),
                    bg=self.colors["bg_medium"], fg=self.colors["text_secondary"]).pack(side="left")
            tk.Label(row, text=str(value), font=("Segoe UI", 11, "bold"),
                    bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="right")

        # Report generation buttons
        btn_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", pady=20)

        tk.Label(btn_frame, text=_t("police_station.reports.generate_report"),
                font=("Segoe UI", 11, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left", padx=(0, 15))

        tk.Button(btn_frame, text=_t("police_station.reports.full_report"),
                 bg=self.colors["accent"], fg="white",
                 bd=0, padx=20, pady=10, font=("Segoe UI", 11), cursor="hand2",
                 command=lambda: self.open_report_window("full")).pack(side="left", padx=5)

        tk.Button(btn_frame, text=_t("police_station.reports.incidents_only"),
                 bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=10, font=("Segoe UI", 11), cursor="hand2",
                 command=lambda: self.open_report_window("incidents")).pack(side="left", padx=5)

        tk.Button(btn_frame, text=_t("police_station.reports.safety_concerns"),
                 bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=10, font=("Segoe UI", 11), cursor="hand2",
                 command=lambda: self.open_report_window("complaints")).pack(side="left", padx=5)

        tk.Button(btn_frame, text=_t("police_station.reports.patrol_logs"),
                 bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=10, font=("Segoe UI", 11), cursor="hand2",
                 command=lambda: self.open_report_window("patrols")).pack(side="left", padx=5)

        # Legacy export buttons
        export_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        export_frame.pack(fill="x", pady=10)

        tk.Label(export_frame, text=_t("police_station.reports.export_data"),
                font=("Segoe UI", 11, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left", padx=(0, 15))

        tk.Button(export_frame, text=_t("police_station.reports.export_json"),
                 bg=self.colors["bg_medium"], fg=self.colors["text"],
                 bd=0, padx=15, pady=8, font=("Segoe UI", 10), cursor="hand2",
                 command=self.export_report).pack(side="left", padx=5)

        tk.Button(export_frame, text=_t("police_station.reports.export_csv"),
                 bg=self.colors["bg_medium"], fg=self.colors["text"],
                 bd=0, padx=15, pady=8, font=("Segoe UI", 10), cursor="hand2",
                 command=self.export_cases).pack(side="left", padx=5)

    def export_report(self):
        """Export data to JSON"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"campus_safety_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.data, f, indent=2)
                messagebox.showinfo(_t("police_station.msg_titles.success"), f"Report exported to {filename}")
            except Exception as e:
                messagebox.showerror(_t("police_station.msg_titles.error"), f"Export failed: {e}")

    def generate_text_report(self, report_type="full"):
        """Generate a formatted text report."""
        today = datetime.now()
        report_lines = []

        # Header
        report_lines.append("=" * 60)
        report_lines.append("CAMPUS PUBLIC SAFETY REPORT")
        report_lines.append("University Police Department")
        report_lines.append("=" * 60)
        report_lines.append(f"Generated: {today.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Report Type: {report_type.title()}")
        report_lines.append(f"Generated By: {self.current_user.get('username', 'Unknown') if self.current_user else 'System'}")
        report_lines.append("")

        # Calculate statistics
        total_cases = len(self.data["cases"])
        open_cases = len([c for c in self.data["cases"] if c.get("status") in ["Open", "In Progress"]])
        closed_cases = len([c for c in self.data["cases"] if c.get("status") == "Closed"])
        student_incidents = len([c for c in self.data["cases"] if c.get("is_student_involved")])
        total_officers = len(self.data["officers"])
        active_officers = len([o for o in self.data["officers"] if o.get("status") == "Active"])
        total_complaints = len(self.data["complaints"])
        resolved_complaints = len([c for c in self.data["complaints"] if c.get("status") == "Resolved"])
        total_patrols = len(self.data.get("patrol_logs", []))

        # Summary Statistics
        report_lines.append("-" * 60)
        report_lines.append("SUMMARY STATISTICS")
        report_lines.append("-" * 60)
        report_lines.append(f"Total Incidents:              {total_cases}")
        report_lines.append(f"  - Active:                   {open_cases}")
        report_lines.append(f"  - Resolved:                 {closed_cases}")
        report_lines.append(f"  - Student-Involved:         {student_incidents}")
        if total_cases > 0:
            report_lines.append(f"  - Resolution Rate:          {(closed_cases/total_cases*100):.1f}%")
        report_lines.append("")
        report_lines.append(f"Campus Officers:              {total_officers}")
        report_lines.append(f"  - On Duty:                  {active_officers}")
        report_lines.append("")
        report_lines.append(f"Safety Concerns:              {total_complaints}")
        report_lines.append(f"  - Resolved:                 {resolved_complaints}")
        report_lines.append("")
        report_lines.append(f"Patrol Entries:               {total_patrols}")
        report_lines.append(f"Evidence Items:               {len(self.data['evidence'])}")
        report_lines.append(f"Persons of Interest:          {len(self.data['criminals'])}")
        report_lines.append("")

        if report_type in ["full", "incidents"]:
            # Recent Incidents
            report_lines.append("-" * 60)
            report_lines.append("RECENT INCIDENTS")
            report_lines.append("-" * 60)
            recent_cases = sorted(self.data["cases"], key=lambda x: x.get('date', ''), reverse=True)[:10]
            if recent_cases:
                for case in recent_cases:
                    report_lines.append(f"ID: {case.get('id', 'N/A')}")
                    report_lines.append(f"  Title: {case.get('title', 'Untitled')}")
                    report_lines.append(f"  Type: {case.get('type', 'N/A')} | Status: {case.get('status', 'N/A')}")
                    report_lines.append(f"  Location: {case.get('location', 'N/A')}")
                    report_lines.append(f"  Date: {case.get('date', 'N/A')}")
                    if case.get('is_student_involved'):
                        report_lines.append(f"  Student ID: {case.get('student_id', 'N/A')}")
                    report_lines.append("")
            else:
                report_lines.append("No incidents recorded.")
                report_lines.append("")

        if report_type in ["full", "complaints"]:
            # Pending Complaints
            report_lines.append("-" * 60)
            report_lines.append("PENDING SAFETY CONCERNS")
            report_lines.append("-" * 60)
            pending = [c for c in self.data["complaints"] if c.get("status") in ["Pending", "Under Investigation"]]
            if pending:
                for complaint in pending[:10]:
                    report_lines.append(f"ID: {complaint.get('id', 'N/A')}")
                    report_lines.append(f"  Type: {complaint.get('type', 'N/A')} | Priority: {complaint.get('priority', 'N/A')}")
                    report_lines.append(f"  Location: {complaint.get('location', 'N/A')}")
                    report_lines.append(f"  Date Filed: {complaint.get('date', 'N/A')}")
                    report_lines.append("")
            else:
                report_lines.append("No pending concerns.")
                report_lines.append("")

        if report_type in ["full", "patrols"]:
            # Today's Patrols
            report_lines.append("-" * 60)
            report_lines.append("TODAY'S PATROL LOGS")
            report_lines.append("-" * 60)
            today_str = today.strftime("%Y-%m-%d")
            today_patrols = [p for p in self.data.get("patrol_logs", []) if p.get("date") == today_str]
            if today_patrols:
                for patrol in today_patrols:
                    report_lines.append(f"Officer: {patrol.get('officer', 'N/A')}")
                    report_lines.append(f"  Area: {patrol.get('area', 'N/A')}")
                    report_lines.append(f"  Time: {patrol.get('start_time', 'N/A')} - {patrol.get('end_time', 'N/A')}")
                    report_lines.append(f"  Status: {patrol.get('status', 'N/A')}")
                    report_lines.append("")
            else:
                report_lines.append("No patrols logged today.")
                report_lines.append("")

        # Footer
        report_lines.append("=" * 60)
        report_lines.append("END OF REPORT")
        report_lines.append("=" * 60)
        report_lines.append("")
        report_lines.append("This report is confidential and intended for authorized")
        report_lines.append("Campus Public Safety personnel only.")

        return "\n".join(report_lines)

    def open_report_window(self, report_type="full"):
        """Open a window to preview and manage the report."""
        report_content = self.generate_text_report(report_type)
        dialog = ReportPreviewDialog(self.root, self.colors, report_content, report_type, self)

    def get_admin_emails(self):
        """Get email addresses of admin users from the database."""
        admin_emails = []
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                # Try to get admin/staff users
                result = conn.execute("""
                    SELECT DISTINCT email FROM users
                    WHERE role IN ('admin', 'Admin', 'administrator', 'staff', 'Staff', 'security', 'Security')
                    AND email IS NOT NULL AND email != ''
                """).fetchall()
                admin_emails = [row[0] for row in result if row[0] and '@' in row[0]]

                # Also get security officers emails
                for officer in self.data.get("officers", []):
                    if officer.get("email") and '@' in officer.get("email", ""):
                        if officer["email"] not in admin_emails:
                            admin_emails.append(officer["email"])
        except Exception as e:
            logger.debug(f"Could not fetch admin emails: {e}")
            # Fallback to officers in data
            for officer in self.data.get("officers", []):
                if officer.get("email") and '@' in officer.get("email", ""):
                    if officer["email"] not in admin_emails:
                        admin_emails.append(officer["email"])

        return admin_emails

    def send_report_to_admins(self, report_content, report_type="full"):
        """Send report to all admin users via email."""
        admin_emails = self.get_admin_emails()

        if not admin_emails:
            messagebox.showwarning(_t("police_station.msg_titles.no_recipients"),
                "No admin email addresses found in the system.\n\n"
                "Please add email addresses to officers or ensure admin users have emails configured.")
            return False

        # Use email template
        try:
            from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template("police_safety_report", {
                "report_type": report_type.title(),
                "report_date": datetime.now().strftime('%Y-%m-%d'),
                "report_content": report_content
            })
        except Exception:
            # Fallback to hardcoded email
            subject = f"Campus Public Safety Report - {report_type.title()} - {datetime.now().strftime('%Y-%m-%d')}"
            body = f"""Campus Public Safety Report

This is an automated report from the Campus Public Safety System.

{report_content}

---
This email was sent automatically. Please do not reply.
Campus Public Safety - University Police Department
"""

        sent_count = 0
        failed = []

        for email in admin_emails:
            if send_notification_email(email, subject, body):
                sent_count += 1
            else:
                failed.append(email)

        if sent_count > 0:
            msg = f"Report sent successfully to {sent_count} recipient(s)."
            if failed:
                msg += f"\n\nFailed to send to: {', '.join(failed)}"
            messagebox.showinfo(_t("police_station.msg_titles.report_sent"), msg)
            return True
        else:
            messagebox.showerror(_t("police_station.msg_titles.send_failed"), "Could not send report to any recipients.")
            return False
