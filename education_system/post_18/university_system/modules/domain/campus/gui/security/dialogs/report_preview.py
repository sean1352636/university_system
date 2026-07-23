"""Report preview dialog."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from education_system.post_18.university_system.core.i18n import get_text as _t


class ReportPreviewDialog(tk.Toplevel):
    """Dialog for previewing and managing reports."""

    def __init__(self, parent, colors, report_content, report_type, app):
        super().__init__(parent)
        self.colors = colors
        self.report_content = report_content
        self.report_type = report_type
        self.app = app

        self.title(f"Report Preview - {report_type.title()}")
        self.geometry("700x600")
        self.configure(bg=colors["bg_dark"])
        self.transient(parent)

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")

        self.create_widgets()

        self.wait_visibility()
        self.grab_set()

    def create_widgets(self):
        # Header
        header = tk.Frame(self, bg=self.colors["bg_medium"], padx=20, pady=15)
        header.pack(fill="x")

        tk.Label(header, text=_t("police_station.reports.report_title"),
                font=("Segoe UI", 16, "bold"),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")

        tk.Label(header, text=f"Type: {self.report_type.title()}",
                font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text_secondary"]).pack(side="right")

        # Report content area
        content_frame = tk.Frame(self, bg=self.colors["bg_dark"], padx=20, pady=10)
        content_frame.pack(fill="both", expand=True)

        # Text widget with scrollbar
        text_frame = tk.Frame(content_frame, bg=self.colors["bg_dark"])
        text_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self.report_text = tk.Text(text_frame, wrap=tk.WORD,
                                   font=("Consolas", 10),
                                   bg=self.colors["bg_medium"],
                                   fg=self.colors["text"],
                                   insertbackground=self.colors["text"],
                                   yscrollcommand=scrollbar.set,
                                   padx=15, pady=15)
        self.report_text.pack(fill="both", expand=True)
        scrollbar.config(command=self.report_text.yview)

        # Insert report content
        self.report_text.insert("1.0", self.report_content)
        self.report_text.config(state="disabled")  # Make read-only

        # Button frame
        btn_frame = tk.Frame(self, bg=self.colors["bg_dark"], padx=20, pady=15)
        btn_frame.pack(fill="x")

        # Save as TXT button
        save_btn = tk.Button(btn_frame, text=_t("police_station.reports.save_as_txt"),
                            font=("Segoe UI", 11),
                            bg=self.colors["success"], fg="white",
                            bd=0, padx=25, pady=10, cursor="hand2",
                            command=self.save_as_txt)
        save_btn.pack(side="left", padx=5)

        # Send to Admin button
        send_btn = tk.Button(btn_frame, text=_t("police_station.reports.send_to_admin"),
                            font=("Segoe UI", 11),
                            bg=self.colors["accent"], fg="white",
                            bd=0, padx=25, pady=10, cursor="hand2",
                            command=self.send_to_admin)
        send_btn.pack(side="left", padx=5)

        # Show recipients button
        recipients_btn = tk.Button(btn_frame, text=_t("police_station.reports.view_recipients"),
                                  font=("Segoe UI", 11),
                                  bg=self.colors["bg_light"], fg=self.colors["text"],
                                  bd=0, padx=20, pady=10, cursor="hand2",
                                  command=self.show_recipients)
        recipients_btn.pack(side="left", padx=5)

        # Close button
        close_btn = tk.Button(btn_frame, text=_t("police_station.buttons.cancel"),
                             font=("Segoe UI", 11),
                             bg=self.colors["bg_medium"], fg=self.colors["text"],
                             bd=0, padx=25, pady=10, cursor="hand2",
                             command=self.destroy)
        close_btn.pack(side="right", padx=5)

    def save_as_txt(self):
        """Save the report as a TXT file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"campus_safety_report_{self.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.report_content)
                messagebox.showinfo(_t("police_station.msg_titles.success"), f"Report saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror(_t("police_station.msg_titles.error"), f"Could not save report:\n{e}")

    def send_to_admin(self):
        """Send the report to admin users."""
        admin_emails = self.app.get_admin_emails()

        if not admin_emails:
            messagebox.showwarning(_t("police_station.msg_titles.no_recipients"),
                "No admin email addresses found.\n\n"
                "Please ensure officers have email addresses configured,\n"
                "or add admin users to the system.")
            return

        # Confirm before sending
        confirm = messagebox.askyesno(_t("police_station.msg_titles.confirm_send"),
            f"Send this report to {len(admin_emails)} recipient(s)?\n\n"
            f"Recipients:\n" + "\n".join(f"  - {email}" for email in admin_emails[:5]) +
            ("\n  ..." if len(admin_emails) > 5 else ""))

        if confirm:
            self.app.send_report_to_admins(self.report_content, self.report_type)

    def show_recipients(self):
        """Show list of admin email recipients."""
        admin_emails = self.app.get_admin_emails()

        if admin_emails:
            msg = "Report will be sent to:\n\n"
            for email in admin_emails:
                msg += f"  - {email}\n"
        else:
            msg = "No admin email addresses found.\n\n"
            msg += "To add recipients:\n"
            msg += "1. Add email addresses to officers in the Officers section\n"
            msg += "2. Ensure admin users have emails in the system database"

        messagebox.showinfo(_t("police_station.msg_titles.email_recipients"), msg)
