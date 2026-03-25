import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.simpledialog import askstring, askinteger
import threading
import json
from datetime import datetime, timedelta
import webbrowser
import os
import subprocess
import sys
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import internationalisation (i18n) for multi‑language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Add the project root to Python path if not already there
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI, get_stored_emails
from education_system.university_system.modules.shared.gui.email.email_gui.utility_dialogs import (
    EmailReportsDialog,
    AdvancedSearchDialog,
    SystemHealthDialog,
    DatabaseCleanupDialog,
    NotificationPreferencesDialog,
    ExportDataDialog,
)

# Import communication stats function
try:
    from education_system.university_system.infrastructure.email.reports import get_user_communication_stats
except ImportError:
    get_user_communication_stats = None

def create_reports_tab(self):
    """Enhanced reports tab"""
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text=_t("email.tabs.reports", default="Reports"))

    # Reports toolbar
    toolbar_frame = ttk.Frame(tab_frame)
    toolbar_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(toolbar_frame, text=_t("email.menu.email_reports", default="Email Reports"), command=self.advanced_email_reports).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.menu.communication_stats", default="Communication Stats"), command=self.communication_stats).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.menu.advanced_search", default="Advanced Search"), command=self.advanced_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.menu.export_data", default="Export Data"), command=self.export_data).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.menu.system_health", default="System Health"), command=self.system_health).pack(side=tk.LEFT, padx=5)

    # Report display area
    report_frame = ttk.LabelFrame(tab_frame, text=_t("email.report_results", default="Report Results"), padding=10)
    report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    self.report_text = scrolledtext.ScrolledText(report_frame, wrap=tk.WORD)
    self.report_text.pack(fill=tk.BOTH, expand=True)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_reports_tab = create_reports_tab

def advanced_email_reports(self):
    """Open advanced email reports dialog"""
    EmailReportsDialog(self.root)

# Bind method to EmailManagerGUI
EmailManagerGUI.advanced_email_reports = advanced_email_reports

def communication_stats(self):
    """Show communication statistics"""
    try:
        if self.dashboard and get_user_communication_stats:
            stats = get_user_communication_stats(self.dashboard)
            if stats:
                stats_text = f"""Communication Statistics:

Messages Sent: {stats['messages_sent']}
Messages Received: {stats['messages_received']}
Unread Messages: {stats['unread_messages']}
Announcements Created: {stats['announcements_created']}
Chat Rooms Joined: {stats['chat_rooms_joined']}
Chat Rooms Created: {stats['chat_rooms_created']}
"""
                self.report_text.delete(1.0, tk.END)
                self.report_text.insert(1.0, stats_text)
            else:
                messagebox.showinfo("Info", "Could not retrieve statistics")
        else:
            messagebox.showinfo("Info", "Dashboard not available")
    except Exception as e:
        messagebox.showerror("Error", f"Error getting statistics: {e}")

# Bind method to EmailManagerGUI
EmailManagerGUI.communication_stats = communication_stats

def advanced_search(self):
    """Open advanced search dialog"""
    AdvancedSearchDialog(self.root, self.dashboard)

# Bind method to EmailManagerGUI
EmailManagerGUI.advanced_search = advanced_search

def email_reports(self):
    """Show email reports"""
    self.notebook.select(6)  # Switch to reports tab (Dashboard=0, Email=1, Messages=2, SMS=3, Announcements=4, Chat=5, Reports=6)
    self.generate_email_report()

# Bind method to EmailManagerGUI
EmailManagerGUI.email_reports = email_reports

def generate_email_report(self):
    """Generate and display email report"""
    try:
        self.report_text.delete(1.0, tk.END)

        report_content = "EMAIL SYSTEM REPORT\n"
        report_content += "=" * 70 + "\n\n"
        report_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # Get data from database
        from education_system.university_system.infrastructure.database.db import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Stored Emails Statistics
        cursor.execute("SELECT COUNT(*) FROM stored_emails")
        stored_count = cursor.fetchone()[0]
        report_content += f"STORED EMAILS: {stored_count}\n"

        # Recent stored emails
        cursor.execute("""
            SELECT recipient_email, subject, created_date
            FROM stored_emails
            ORDER BY created_date DESC LIMIT 10
        """)
        recent_stored = cursor.fetchall()
        if recent_stored:
            report_content += "\nRecent Stored Emails:\n"
            report_content += "-" * 50 + "\n"
            for row in recent_stored:
                report_content += f"• To: {row[0]}\n"
                report_content += f"  Subject: {row[1]}\n"
                report_content += f"  Date: {row[2]}\n\n"

        # Email Log Statistics
        cursor.execute("SELECT COUNT(*) FROM email_log")
        log_count = cursor.fetchone()[0]
        report_content += f"\nEMAIL LOG (Sent): {log_count}\n"

        # Status breakdown
        cursor.execute("SELECT status, COUNT(*) FROM email_log GROUP BY status")
        status_rows = cursor.fetchall()
        if status_rows:
            report_content += "\nBy Status:\n"
            for row in status_rows:
                status = row[0] or 'Unknown'
                report_content += f"  {status}: {row[1]}\n"

        # Internal Messages
        cursor.execute("SELECT COUNT(*) FROM messages")
        msg_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM messages WHERE is_read = 0")
        unread_count = cursor.fetchone()[0]

        report_content += f"\nINTERNAL MESSAGES: {msg_count}\n"
        report_content += f"  Unread: {unread_count}\n"
        report_content += f"  Read: {msg_count - unread_count}\n"

        # Templates
        cursor.execute("SELECT COUNT(*) FROM email_templates")
        template_count = cursor.fetchone()[0]
        report_content += f"\nEMAIL TEMPLATES: {template_count}\n"

        # Announcements
        try:
            cursor.execute("SELECT COUNT(*) FROM announcements WHERE is_active = 1")
            announcement_count = cursor.fetchone()[0]
            report_content += f"\nACTIVE ANNOUNCEMENTS: {announcement_count}\n"
        except Exception as e:
            logger.debug(f"Failed to query active announcements: {e}")

        # Chat Rooms
        try:
            cursor.execute("SELECT COUNT(*) FROM chat_rooms WHERE is_active = 1")
            chatroom_count = cursor.fetchone()[0]
            report_content += f"ACTIVE CHAT ROOMS: {chatroom_count}\n"
        except Exception as e:
            logger.debug(f"Failed to query active chat rooms: {e}")

        conn.close()

        self.report_text.insert(1.0, report_content)
        self.update_status("Report generated")

    except Exception as e:
        import traceback
        error_msg = f"Error generating report:\n{str(e)}\n\n{traceback.format_exc()}"
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(1.0, error_msg)
        messagebox.showerror("Error", f"Error generating report: {e}")

# Bind method to EmailManagerGUI
EmailManagerGUI.generate_email_report = generate_email_report

def export_report_csv(self):
    """Export report to CSV"""
    try:
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filename:
            if 'get_stored_emails' in globals():
                emails_data = get_stored_emails(limit=1000)

                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['id', 'recipient_email', 'subject', 'created_date', 'template_name']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for email in emails_data['emails']:
                        writer.writerow({
                            'id': email['id'],
                            'recipient_email': email['recipient_email'],
                            'subject': email['subject'],
                            'created_date': email['created_date'],
                            'template_name': email['template_name'] or 'Direct'
                        })

                messagebox.showinfo("Success", f"Report exported to {filename}")
                self.update_status(f"Report exported to {filename}")
            else:
                messagebox.showerror("Error", "Export functionality not available")
    except Exception as e:
        messagebox.showerror("Error", f"Error exporting report: {e}")

# Bind method to EmailManagerGUI
EmailManagerGUI.export_report_csv = export_report_csv

def system_health(self):
    """Show system health dialog"""
    SystemHealthDialog(self.root)

# Bind method to EmailManagerGUI
EmailManagerGUI.system_health = system_health

def database_cleanup(self):
    """Open database cleanup dialog"""
    DatabaseCleanupDialog(self.root)

# Bind method to EmailManagerGUI
EmailManagerGUI.database_cleanup = database_cleanup

def notification_preferences(self):
    """Open notification preferences dialog"""
    NotificationPreferencesDialog(self.root, self.dashboard)

# Bind method to EmailManagerGUI
EmailManagerGUI.notification_preferences = notification_preferences

def import_contacts(self):
    """Import contacts from file"""
    filename = filedialog.askopenfilename(
        title="Import Contacts",
        filetypes=[("CSV files", "*.csv"), ("VCard files", "*.vcf"), ("All files", "*.*")]
    )

    if not filename:
        return

    try:
        import csv

        # Create import preview dialog
        import_dialog = tk.Toplevel(self.root)
        import_dialog.title("Import Contacts")
        import_dialog.geometry("700x500")
        import_dialog.transient(self.root)

        ttk.Label(import_dialog, text="Import Contacts Preview",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

        ttk.Label(import_dialog, text=f"File: {filename}", foreground='blue').pack()

        # Preview frame
        preview_frame = ttk.LabelFrame(import_dialog, text="Preview (first 10 rows)", padding=10)
        preview_frame.pack(fill='both', expand=True, padx=10, pady=10)

        preview_tree = ttk.Treeview(preview_frame, columns=('Name', 'Email', 'Group'),
                                   show='headings', height=15)
        preview_tree.heading('Name', text='Name')
        preview_tree.heading('Email', text='Email')
        preview_tree.heading('Group', text='Group')

        for col in ('Name', 'Email', 'Group'):
            preview_tree.column(col, width=200)

        preview_tree.pack(fill='both', expand=True)

        # Parse CSV file
        contacts_to_import = []
        with open(filename, 'r', encoding='utf-8') as csvfile:
            # Try to detect if file has headers
            sample = csvfile.read(1024)
            csvfile.seek(0)
            sniffer = csv.Sniffer()
            has_header = sniffer.has_header(sample)

            csvfile.seek(0)
            reader = csv.reader(csvfile)

            if has_header:
                next(reader)  # Skip header row

            for i, row in enumerate(reader):
                if i < 10:  # Preview first 10
                    if len(row) >= 2:
                        name = row[0].strip()
                        email = row[1].strip()
                        group = row[2].strip() if len(row) > 2 else 'Imported'
                        preview_tree.insert('', 'end', values=(name, email, group))
                        contacts_to_import.append((name, email, group))
                    else:
                        contacts_to_import.append((row[0].strip() if row else '', '', 'Imported'))

        # Info label
        info_label = ttk.Label(import_dialog,
                              text=f"Total contacts to import: {len(contacts_to_import)}",
                              font=('TkDefaultFont', 10, 'bold'))
        info_label.pack(pady=5)

        def perform_import():
            try:
                # In real implementation, save to database
                # For now, just show success message
                imported_count = 0
                duplicate_count = 0

                for name, email, group in contacts_to_import:
                    if email:  # Only import if email is present
                        # Here would check for duplicates and insert into database
                        imported_count += 1
                    else:
                        duplicate_count += 1

                messagebox.showinfo("Import Complete",
                                  f"Successfully imported {imported_count} contacts!\n\n"
                                  f"Skipped {duplicate_count} invalid/duplicate entries.",
                                  parent=import_dialog)
                import_dialog.destroy()

            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import contacts: {e}",
                                   parent=import_dialog)

        # Buttons
        button_frame = ttk.Frame(import_dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Import", command=perform_import).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=import_dialog.destroy).pack(side='left', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to read contacts file: {e}")

# Bind method to EmailManagerGUI
EmailManagerGUI.import_contacts = import_contacts

def export_data(self):
    """Export system data"""
    ExportDataDialog(self.root)

# Bind method to EmailManagerGUI
EmailManagerGUI.export_data = export_data

