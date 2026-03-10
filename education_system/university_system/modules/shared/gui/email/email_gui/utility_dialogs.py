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

# Import functions from email_manager_main
try:
    from .email_manager_main import (
        get_system_health_info,
        clear_stored_emails,
        optimize_database,
    )
except ImportError:
    get_system_health_info = None
    clear_stored_emails = None
    optimize_database = None

# Import config
try:
    from .email_manager_main import config
except ImportError:
    config = {}

class SystemHealthDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("System Health")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
        self.load_health_info()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="System Health Status", font=('Arial', 14, 'bold')).pack(pady=10)
        
        self.health_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.health_text.pack(fill=tk.BOTH, expand=True)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Refresh", command=self.load_health_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_health_info(self):
        """Load system health information"""
        try:
            self.health_text.config(state=tk.NORMAL)
            self.health_text.delete(1.0, tk.END)
            
            health_info = "SYSTEM HEALTH REPORT\n"
            health_info += "=" * 30 + "\n\n"
            health_info += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            if get_system_health_info is not None:
                health = get_system_health_info()
                health_info += f"Email System: {health.get('email_system', 'Unknown')}\n"
                health_info += f"Message System: {health.get('message_system', 'Unknown')}\n"
                health_info += f"Chat System: {health.get('chat_system', 'Unknown')}\n"
                health_info += f"Database: {health.get('database_status', 'Unknown')}\n"
                health_info += f"Queue Size: {health.get('queue_size', 0)}\n"
            else:
                health_info += "Health monitoring not available\n"

            # Check configuration
            if config:
                health_info += f"\nConfiguration:\n"
                health_info += f"Mode: {'Database Only' if config.get('database_only_mode', True) else 'SMTP'}\n"
                health_info += f"Sender Email: {config.get('sender_email', 'Not set')}\n"
                health_info += f"SMTP Server: {config.get('smtp_server', 'Not set')}\n"
            
            self.health_text.insert(1.0, health_info)
            self.health_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.health_text.config(state=tk.NORMAL)
            self.health_text.delete(1.0, tk.END)
            self.health_text.insert(1.0, f"Error loading health info: {e}")
            self.health_text.config(state=tk.DISABLED)


class DatabaseCleanupDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Database Cleanup")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Database Cleanup Options", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Cleanup options
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(options_frame, text="Clean Old Emails (30+ days)", 
                  command=lambda: self.cleanup_emails(30)).pack(fill=tk.X, pady=2)
        
        ttk.Button(options_frame, text="Clean Old Emails (90+ days)", 
                  command=lambda: self.cleanup_emails(90)).pack(fill=tk.X, pady=2)
        
        ttk.Button(options_frame, text="Cleanup Deleted Messages", 
                  command=self.cleanup_messages).pack(fill=tk.X, pady=2)
        
        ttk.Button(options_frame, text="Optimize Database",
                  command=self.optimize_db).pack(fill=tk.X, pady=2)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=20)
    
    def cleanup_emails(self, days):
        """Clean up old emails"""
        if messagebox.askyesno("Confirm", f"Delete emails older than {days} days?"):
            try:
                if clear_stored_emails is not None:
                    count = clear_stored_emails(older_than_days=days)
                    messagebox.showinfo("Success", f"Deleted {count} old emails")
                else:
                    messagebox.showerror("Error", "Cleanup function not available")
            except Exception as e:
                messagebox.showerror("Error", f"Error during cleanup: {e}")
    
    def cleanup_messages(self):
        """Clean up deleted messages"""
        if messagebox.askyesno("Confirm", "Clean up messages deleted by both parties?"):
            try:
                from education_system.university_system.infrastructure.database.db import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()

                # Delete messages deleted by both sender and recipient or older than 90 days
                cursor.execute("""
                    DELETE FROM messages
                    WHERE (is_deleted_by_sender = 1 AND is_deleted_by_recipient = 1)
                       OR (is_deleted_by_sender = 1 AND sent_at < date('now', '-90 days'))
                       OR (is_deleted_by_recipient = 1 AND sent_at < date('now', '-90 days'))
                """)

                deleted = cursor.rowcount
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Cleaned up {deleted} messages")
            except Exception as e:
                messagebox.showerror("Error", f"Error during cleanup: {e}")
    
    def optimize_db(self):
        """Optimize database"""
        try:
            if optimize_database is not None:
                optimize_database()
                messagebox.showinfo("Success", "Database optimized successfully")
            else:
                messagebox.showinfo("Info", "Database optimization not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error optimizing database: {e}")


class AdvancedSearchDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Search")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Search criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=10)
        criteria_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Search in
        ttk.Label(criteria_frame, text="Search in:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.search_in = ttk.Combobox(criteria_frame, values=["Messages", "Stored Emails", "Both"])
        self.search_in.grid(row=0, column=1, sticky=tk.W, pady=5)
        self.search_in.set("Messages")
        
        # Keywords
        ttk.Label(criteria_frame, text="Keywords:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.keywords = ttk.Entry(criteria_frame, width=40)
        self.keywords.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # From/To
        ttk.Label(criteria_frame, text="From/To:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.sender_recipient = ttk.Entry(criteria_frame, width=40)
        self.sender_recipient.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Date range
        ttk.Label(criteria_frame, text="Date from:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.date_from = ttk.Entry(criteria_frame, width=15)
        self.date_from.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(criteria_frame, text="Date to:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.date_to = ttk.Entry(criteria_frame, width=15)
        self.date_to.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Search button
        ttk.Button(criteria_frame, text="Search", command=self.perform_search).grid(row=5, column=0, columnspan=2, pady=10)
        
        # Results
        results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("Type", "From/To", "Subject", "Date")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        
        for col in columns:
            self.results_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def perform_search(self):
        keywords = self.keywords.get().strip()
        search_in = self.search_in.get()
        sender_recipient = self.sender_recipient.get().strip()
        date_from = self.date_from.get().strip()
        date_to = self.date_to.get().strip()

        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        if not keywords and not sender_recipient:
            messagebox.showwarning("Warning", "Please enter search keywords or sender/recipient")
            return

        try:
            def search_database(cursor):
                results = []

                # Search in messages if requested
                if search_in in ["Messages", "Both"]:
                    query = """
                    SELECT 'Message' as type,
                           u.username as sender,
                           m.subject,
                           m.sent_at,
                           m.id
                    FROM messages m
                    JOIN users u ON m.sender_id = u.id
                    WHERE 1=1
                    """
                    params = []

                    if keywords:
                        query += " AND (m.subject LIKE ? OR m.message LIKE ? OR m.content LIKE ?)"
                        keyword_param = f"%{keywords}%"
                        params.extend([keyword_param, keyword_param, keyword_param])

                    if sender_recipient:
                        query += " AND u.username LIKE ?"
                        params.append(f"%{sender_recipient}%")

                    if date_from:
                        query += " AND m.sent_at >= ?"
                        params.append(date_from)

                    if date_to:
                        query += " AND m.sent_at <= ?"
                        params.append(date_to)

                    cursor.execute(query, params)
                    for row in cursor.fetchall():
                        results.append(('Message', row[1], row[2], row[3]))

                # Search in stored emails if requested
                if search_in in ["Stored Emails", "Both"]:
                    query = """
                    SELECT 'Email' as type,
                           sender_name,
                           subject,
                           created_date
                    FROM stored_emails
                    WHERE 1=1
                    """
                    params = []

                    if keywords:
                        query += " AND (subject LIKE ? OR body LIKE ?)"
                        keyword_param = f"%{keywords}%"
                        params.extend([keyword_param, keyword_param])

                    if sender_recipient:
                        query += " AND (sender_name LIKE ? OR recipient_email LIKE ?)"
                        sender_param = f"%{sender_recipient}%"
                        params.extend([sender_param, sender_param])

                    if date_from:
                        query += " AND created_date >= ?"
                        params.append(date_from)

                    if date_to:
                        query += " AND created_date <= ?"
                        params.append(date_to)

                    cursor.execute(query, params)
                    for row in cursor.fetchall():
                        results.append(('Email', row[1], row[2], row[3]))

                return results

            results = execute_db_operation(search_database)

            # Display results
            for result in results:
                self.results_tree.insert('', tk.END, values=result)

            if results:
                messagebox.showinfo("Search Complete", f"Found {len(results)} results")
            else:
                messagebox.showinfo("Search Complete", "No results found")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")


class EmailReportsDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Email Reports")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Filter options
        filter_frame = ttk.LabelFrame(main_frame, text="Report Filters", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Date range
        ttk.Label(filter_frame, text="From Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.start_date = ttk.Entry(filter_frame, width=15)
        self.start_date.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(filter_frame, text="To Date:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.end_date = ttk.Entry(filter_frame, width=15)
        self.end_date.grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        
        # Report type
        ttk.Label(filter_frame, text="Report Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.report_type = ttk.Combobox(filter_frame, values=[
            "Email Statistics", "Stored Emails", "Email Log", "Messages",
            "Template Usage", "User Activity", "Failed Emails"
        ])
        self.report_type.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.report_type.set("Email Statistics")
        
        # Generate button
        ttk.Button(filter_frame, text="Generate Report", command=self.generate_report).grid(row=2, column=0, columnspan=4, pady=10)
        
        # Report display
        report_frame = ttk.LabelFrame(main_frame, text="Report Results", padding=10)
        report_frame.pack(fill=tk.BOTH, expand=True)
        
        self.report_text = scrolledtext.ScrolledText(report_frame, wrap=tk.WORD)
        self.report_text.pack(fill=tk.BOTH, expand=True)
        
        # Export buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def generate_report(self):
        try:
            start_date = self.start_date.get() or None
            end_date = self.end_date.get() or None
            report_type = self.report_type.get()

            # Generate basic report
            self.report_text.delete(1.0, tk.END)

            report_content = f"EMAIL SYSTEM REPORT - {report_type}\n"
            report_content += "=" * 70 + "\n\n"
            report_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

            if start_date:
                report_content += f"From: {start_date}\n"
            if end_date:
                report_content += f"To: {end_date}\n"

            report_content += "\n" + "=" * 70 + "\n\n"

            # Generate actual report data
            try:
                from education_system.university_system.infrastructure.database.db import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()

                if report_type == "Email Statistics":
                    # Stored Emails Statistics
                    cursor.execute("SELECT COUNT(*) FROM stored_emails")
                    stored_count = cursor.fetchone()[0]
                    report_content += f"STORED EMAILS\n"
                    report_content += "-" * 40 + "\n"
                    report_content += f"Total Stored: {stored_count}\n\n"

                    # Email Log Statistics
                    cursor.execute("SELECT COUNT(*) FROM email_log")
                    log_count = cursor.fetchone()[0]
                    report_content += f"EMAIL LOG (Sent Emails)\n"
                    report_content += "-" * 40 + "\n"
                    report_content += f"Total Logged: {log_count}\n"

                    # Count by status
                    cursor.execute("SELECT status, COUNT(*) FROM email_log GROUP BY status")
                    report_content += "\nBy Status:\n"
                    for row in cursor.fetchall():
                        status = row[0] or 'Unknown'
                        report_content += f"  {status}: {row[1]}\n"

                    # Messages Statistics
                    cursor.execute("SELECT COUNT(*) FROM messages")
                    msg_count = cursor.fetchone()[0]
                    report_content += f"\nINTERNAL MESSAGES\n"
                    report_content += "-" * 40 + "\n"
                    report_content += f"Total Messages: {msg_count}\n"

                    cursor.execute("SELECT COUNT(*) FROM messages WHERE is_read = 1")
                    read_count = cursor.fetchone()[0]
                    report_content += f"Read Messages: {read_count}\n"
                    report_content += f"Unread Messages: {msg_count - read_count}\n"

                elif report_type == "Stored Emails":
                    cursor.execute("""
                        SELECT recipient_email, subject, sender_email, sender_name, created_date
                        FROM stored_emails
                        ORDER BY created_date DESC LIMIT 50
                    """)
                    rows = cursor.fetchall()
                    report_content += f"STORED EMAILS (Last 50)\n"
                    report_content += "-" * 70 + "\n\n"

                    for row in rows:
                        report_content += f"To: {row[0]}\n"
                        report_content += f"From: {row[3]} <{row[2]}>\n"
                        report_content += f"Subject: {row[1]}\n"
                        report_content += f"Date: {row[4]}\n"
                        report_content += "-" * 40 + "\n\n"

                elif report_type == "Email Log":
                    cursor.execute("""
                        SELECT recipient, subject, status, sent_date, sender_name
                        FROM email_log
                        ORDER BY sent_date DESC LIMIT 50
                    """)
                    rows = cursor.fetchall()
                    report_content += f"EMAIL SEND LOG (Last 50)\n"
                    report_content += "-" * 70 + "\n\n"

                    for row in rows:
                        report_content += f"To: {row[0]}\n"
                        report_content += f"From: {row[4] or 'System'}\n"
                        report_content += f"Subject: {row[1]}\n"
                        report_content += f"Status: {row[2] or 'Unknown'}\n"
                        report_content += f"Sent: {row[3]}\n"
                        report_content += "-" * 40 + "\n\n"

                elif report_type == "Messages":
                    cursor.execute("""
                        SELECT
                            m.subject,
                            m.sent_at,
                            m.is_read,
                            sender.username as sender_username,
                            sender.email as sender_email,
                            recipient.username as recipient_username,
                            recipient.email as recipient_email
                        FROM messages m
                        LEFT JOIN users sender ON m.sender_id = sender.id
                        LEFT JOIN users recipient ON m.recipient_id = recipient.id
                        ORDER BY m.sent_at DESC LIMIT 50
                    """)
                    rows = cursor.fetchall()
                    report_content += f"INTERNAL MESSAGES (Last 50)\n"
                    report_content += "-" * 70 + "\n\n"

                    for row in rows:
                        status = "✓ Read" if row[2] else "⚬ Unread"
                        report_content += f"From: {row[3] or 'Unknown'} <{row[4] or 'N/A'}>\n"
                        report_content += f"To: {row[5] or 'Unknown'} <{row[6] or 'N/A'}>\n"
                        report_content += f"Subject: {row[0]}\n"
                        report_content += f"Status: {status}\n"
                        report_content += f"Sent: {row[1]}\n"
                        report_content += "-" * 40 + "\n\n"

                elif report_type == "Template Usage":
                    cursor.execute("""
                        SELECT template_name, template_type, created_date, created_by
                        FROM email_templates
                        ORDER BY template_name
                    """)
                    templates = cursor.fetchall()
                    report_content += f"EMAIL TEMPLATES\n"
                    report_content += "-" * 70 + "\n"
                    report_content += f"Total Templates: {len(templates)}\n\n"

                    for tmpl in templates:
                        report_content += f"Name: {tmpl[0]}\n"
                        report_content += f"Type: {tmpl[1] or 'N/A'}\n"
                        report_content += f"Created: {tmpl[2] or 'N/A'}\n"
                        report_content += f"Created By: {tmpl[3] or 'System'}\n"
                        report_content += "-" * 40 + "\n\n"

                    # Template usage in stored emails
                    cursor.execute("""
                        SELECT template_name, COUNT(*) as count
                        FROM stored_emails
                        WHERE template_name IS NOT NULL
                        GROUP BY template_name
                        ORDER BY count DESC
                    """)
                    usage = cursor.fetchall()
                    if usage:
                        report_content += "\nTEMPLATE USAGE STATISTICS\n"
                        report_content += "-" * 40 + "\n"
                        for row in usage:
                            report_content += f"  {row[0]}: {row[1]} emails\n"

                elif report_type == "User Activity":
                    # Top email recipients from stored_emails
                    cursor.execute("""
                        SELECT recipient_email, COUNT(*) as count
                        FROM stored_emails
                        GROUP BY recipient_email
                        ORDER BY count DESC LIMIT 20
                    """)
                    report_content += "TOP 20 EMAIL RECIPIENTS (Stored Emails)\n"
                    report_content += "-" * 70 + "\n"
                    for row in cursor.fetchall():
                        report_content += f"  {row[0]}: {row[1]} emails\n"

                    # Top message senders
                    cursor.execute("""
                        SELECT u.username, u.email, COUNT(*) as count
                        FROM messages m
                        LEFT JOIN users u ON m.sender_id = u.id
                        GROUP BY m.sender_id
                        ORDER BY count DESC LIMIT 20
                    """)
                    report_content += "\n\nTOP 20 MESSAGE SENDERS (Internal Messages)\n"
                    report_content += "-" * 70 + "\n"
                    for row in cursor.fetchall():
                        username = row[0] or 'Unknown'
                        email = row[1] or 'N/A'
                        report_content += f"  {username} <{email}>: {row[2]} messages\n"

                elif report_type == "Failed Emails":
                    cursor.execute("""
                        SELECT recipient, subject, sent_date, status, message
                        FROM email_log
                        WHERE status LIKE '%fail%' OR status LIKE '%error%'
                        ORDER BY sent_date DESC LIMIT 50
                    """)
                    rows = cursor.fetchall()
                    report_content += f"FAILED EMAILS\n"
                    report_content += "-" * 70 + "\n"
                    report_content += f"Total Failed: {len(rows)}\n\n"

                    for row in rows:
                        report_content += f"To: {row[0]}\n"
                        report_content += f"Subject: {row[1]}\n"
                        report_content += f"Date: {row[2]}\n"
                        report_content += f"Status: {row[3]}\n"
                        if row[4]:
                            report_content += f"Details: {row[4][:100]}...\n"
                        report_content += "-" * 40 + "\n\n"

                conn.close()

            except Exception as e:
                import traceback
                report_content += f"\nError generating detailed report:\n"
                report_content += f"{str(e)}\n\n"
                report_content += traceback.format_exc()

            self.report_text.insert(1.0, report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def export_csv(self):
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")]
            )
            if filename:
                content = self.report_text.get(1.0, tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")


class NotificationPreferencesDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Notification Preferences")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.preferences = {}
        self.create_widgets()
        self.load_preferences()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Notification Preferences", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Preference checkboxes
        self.email_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Email Notifications", variable=self.email_var).pack(anchor=tk.W, pady=5)
        
        self.message_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Message Notifications", variable=self.message_var).pack(anchor=tk.W, pady=5)
        
        self.announcement_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Announcement Notifications", variable=self.announcement_var).pack(anchor=tk.W, pady=5)
        
        self.chat_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Chat Notifications", variable=self.chat_var).pack(anchor=tk.W, pady=5)
        
        self.digest_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Daily Digest", variable=self.digest_var).pack(anchor=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_preferences).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_preferences(self):
        try:
            if self.dashboard:
                prefs = self.dashboard.get_notification_preferences()
                if prefs:
                    self.email_var.set(prefs.get('email_notifications', True))
                    self.message_var.set(prefs.get('message_notifications', True))
                    self.announcement_var.set(prefs.get('announcement_notifications', True))
                    self.chat_var.set(prefs.get('chat_notifications', True))
                    self.digest_var.set(prefs.get('daily_digest', False))
        except Exception as e:
            print(f"Error loading preferences: {e}")
    
    def save_preferences(self):
        try:
            preferences = {
                'email_notifications': self.email_var.get(),
                'message_notifications': self.message_var.get(),
                'announcement_notifications': self.announcement_var.get(),
                'chat_notifications': self.chat_var.get(),
                'daily_digest': self.digest_var.get()
            }

            # Save directly to database
            from education_system.university_system.infrastructure.database.db import get_db_connection
            import json

            conn = get_db_connection()
            cursor = conn.cursor()

            # Save preferences (using user_id 1 as default)
            user_id = 1  # Would need actual user ID from auth

            # Store preferences as JSON string
            prefs_json = json.dumps(preferences)

            # Use INSERT OR REPLACE to handle existing records
            cursor.execute('''
                INSERT OR REPLACE INTO user_preferences (user_id, preferences, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, prefs_json))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Preferences saved successfully!")
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Error saving preferences: {e}")


class ExportDataDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Data")
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Export Email Data", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Export options
        options_frame = ttk.LabelFrame(main_frame, text="Select Data to Export", padding=10)
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.export_emails_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Emails", variable=self.export_emails_var).pack(anchor=tk.W, pady=2)

        self.export_templates_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Templates", variable=self.export_templates_var).pack(anchor=tk.W, pady=2)

        self.export_scheduled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Scheduled Emails", variable=self.export_scheduled_var).pack(anchor=tk.W, pady=2)

        self.export_announcements_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Announcements", variable=self.export_announcements_var).pack(anchor=tk.W, pady=2)

        self.export_chatrooms_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Chat Rooms", variable=self.export_chatrooms_var).pack(anchor=tk.W, pady=2)

        # Format selection
        format_frame = ttk.LabelFrame(main_frame, text="Export Format", padding=10)
        format_frame.pack(fill=tk.X, pady=(0, 10))

        self.format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(format_frame, text="CSV", variable=self.format_var, value="csv").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="JSON", variable=self.format_var, value="json").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="HTML Report", variable=self.format_var, value="html").pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Export", command=self.export_data).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def export_data(self):
        # Check if at least one option is selected
        if not any([
            self.export_emails_var.get(),
            self.export_templates_var.get(),
            self.export_scheduled_var.get(),
            self.export_announcements_var.get(),
            self.export_chatrooms_var.get()
        ]):
            messagebox.showwarning("No Selection", "Please select at least one data type to export")
            return

        format_type = self.format_var.get()

        # Ask for file location
        file_types = {
            "csv": [("CSV files", "*.csv"), ("All files", "*.*")],
            "json": [("JSON files", "*.json"), ("All files", "*.*")],
            "html": [("HTML files", "*.html"), ("All files", "*.*")]
        }

        file_path = filedialog.asksaveasfilename(
            title="Save Export",
            defaultextension=f".{format_type}",
            filetypes=file_types.get(format_type, [("All files", "*.*")])
        )

        if not file_path:
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            import csv as csv_module

            conn = get_db_connection()
            cursor = conn.cursor()

            export_data = {}
            export_headers = {}

            # Export emails with comprehensive details
            if self.export_emails_var.get():
                try:
                    # Query messages with full sender/recipient details
                    cursor.execute('''
                        SELECT
                            m.id as message_id,
                            m.subject,
                            COALESCE(m.content, m.message) as content,
                            m.sent_at,
                            m.read_at,
                            m.is_read,
                            sender.id as sender_id,
                            sender.username as sender_username,
                            sender.email as sender_email,
                            sender.first_name as sender_first_name,
                            sender.last_name as sender_last_name,
                            recipient.id as recipient_id,
                            recipient.username as recipient_username,
                            recipient.email as recipient_email,
                            recipient.first_name as recipient_first_name,
                            recipient.last_name as recipient_last_name,
                            m.attachment_path,
                            m.is_archived,
                            m.is_deleted_by_sender,
                            m.is_deleted_by_recipient
                        FROM messages m
                        LEFT JOIN users sender ON m.sender_id = sender.id
                        LEFT JOIN users recipient ON m.recipient_id = recipient.id
                        ORDER BY m.sent_at DESC
                    ''')
                    export_data['messages'] = cursor.fetchall()
                    export_headers['messages'] = [
                        'Message ID', 'Subject', 'Content', 'Sent Date/Time', 'Read Date/Time', 'Is Read',
                        'Sender ID', 'Sender Username', 'Sender Email', 'Sender First Name', 'Sender Last Name',
                        'Recipient ID', 'Recipient Username', 'Recipient Email', 'Recipient First Name', 'Recipient Last Name',
                        'Attachments', 'Is Archived', 'Deleted by Sender', 'Deleted by Recipient'
                    ]
                except Exception as e:
                    print(f"Error exporting messages: {e}")

                # Also export stored emails (sent via SMTP or database-only mode)
                try:
                    cursor.execute('''
                        SELECT
                            id,
                            recipient_email,
                            subject,
                            body,
                            sender_email,
                            sender_name,
                            cc_recipients,
                            bcc_recipients,
                            attachment_paths,
                            created_date,
                            template_name,
                            template_vars
                        FROM stored_emails
                        ORDER BY created_date DESC
                    ''')
                    export_data['stored_emails'] = cursor.fetchall()
                    export_headers['stored_emails'] = [
                        'Email ID', 'Recipient Email', 'Subject', 'Body', 'Sender Email', 'Sender Name',
                        'CC Recipients', 'BCC Recipients', 'Attachments', 'Sent Date/Time',
                        'Template Name', 'Template Variables'
                    ]
                except Exception as e:
                    print(f"Error exporting stored emails: {e}")

                # Export email logs
                try:
                    cursor.execute('''
                        SELECT
                            id,
                            recipient,
                            subject,
                            sent_date,
                            status,
                            related_to,
                            student_id,
                            sender_email,
                            sender_name,
                            cc_recipients,
                            bcc_recipients,
                            attachment_info
                        FROM email_log
                        ORDER BY sent_date DESC
                    ''')
                    export_data['email_log'] = cursor.fetchall()
                    export_headers['email_log'] = [
                        'Log ID', 'Recipient', 'Subject', 'Sent Date/Time', 'Status',
                        'Related To', 'Student ID', 'Sender Email', 'Sender Name',
                        'CC Recipients', 'BCC Recipients', 'Attachment Info'
                    ]
                except Exception as e:
                    print(f"Error exporting email logs: {e}")

            # Export templates with full details
            if self.export_templates_var.get():
                try:
                    cursor.execute('''
                        SELECT
                            template_id,
                            template_name,
                            template_content,
                            template_type,
                            created_date,
                            created_by
                        FROM email_templates
                        ORDER BY template_name
                    ''')
                    export_data['templates'] = cursor.fetchall()
                    export_headers['templates'] = [
                        'Template ID', 'Template Name', 'Template Content', 'Template Type',
                        'Created Date', 'Created By'
                    ]
                except Exception as e:
                    print(f"Error exporting templates: {e}")

            # Export scheduled emails
            if self.export_scheduled_var.get():
                try:
                    cursor.execute('''
                        SELECT
                            id,
                            template_name,
                            recipient_email,
                            template_vars,
                            scheduled_date,
                            status,
                            created_at
                        FROM scheduled_emails
                        ORDER BY scheduled_date
                    ''')
                    export_data['scheduled_emails'] = cursor.fetchall()
                    export_headers['scheduled_emails'] = [
                        'Schedule ID', 'Template Name', 'Recipient Email', 'Template Variables',
                        'Scheduled Date', 'Status', 'Created At'
                    ]
                except Exception as e:
                    print(f"Error exporting scheduled emails: {e}")

            # Export announcements with creator details
            if self.export_announcements_var.get():
                try:
                    cursor.execute('''
                        SELECT
                            a.id,
                            a.title,
                            a.content,
                            a.target_audience,
                            a.is_urgent,
                            a.is_active,
                            a.start_date,
                            a.end_date,
                            a.created_at,
                            a.updated_at,
                            u.id as creator_id,
                            u.username as creator_username,
                            u.email as creator_email,
                            u.first_name as creator_first_name,
                            u.last_name as creator_last_name
                        FROM announcements a
                        LEFT JOIN users u ON a.creator_id = u.id
                        ORDER BY a.created_at DESC
                    ''')
                    export_data['announcements'] = cursor.fetchall()
                    export_headers['announcements'] = [
                        'Announcement ID', 'Title', 'Content', 'Target Audience', 'Is Urgent', 'Is Active',
                        'Start Date', 'End Date', 'Created Date/Time', 'Updated Date/Time',
                        'Creator ID', 'Creator Username', 'Creator Email', 'Creator First Name', 'Creator Last Name'
                    ]
                except Exception as e:
                    print(f"Error exporting announcements: {e}")

            # Export chat rooms with creator details
            if self.export_chatrooms_var.get():
                try:
                    cursor.execute('''
                        SELECT
                            cr.id,
                            cr.name,
                            cr.description,
                            cr.room_type,
                            cr.max_members,
                            cr.is_active,
                            cr.created_at,
                            u.id as creator_id,
                            u.username as creator_username,
                            u.email as creator_email
                        FROM chat_rooms cr
                        LEFT JOIN users u ON cr.created_by = u.id
                        ORDER BY cr.created_at DESC
                    ''')
                    export_data['chat_rooms'] = cursor.fetchall()
                    export_headers['chat_rooms'] = [
                        'Room ID', 'Room Name', 'Description', 'Room Type', 'Max Members',
                        'Is Active', 'Created Date/Time', 'Creator ID', 'Creator Username', 'Creator Email'
                    ]
                except Exception as e:
                    print(f"Error exporting chat rooms: {e}")

            conn.close()

            # Export based on format
            if format_type == "csv":
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv_module.writer(f)
                    writer.writerow(['Email System Comprehensive Export'])
                    writer.writerow([f'Exported on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                    writer.writerow([])

                    for data_type, rows in export_data.items():
                        writer.writerow([f"=== {data_type.upper().replace('_', ' ')} ==="])
                        writer.writerow([f'Total Records: {len(rows)}'])
                        writer.writerow([])

                        # Write headers if available
                        if data_type in export_headers:
                            writer.writerow(export_headers[data_type])

                        # Write data
                        for row in rows:
                            writer.writerow(row)
                        writer.writerow([])
                        writer.writerow([])

            elif format_type == "json":
                # Convert tuples to dictionaries with headers for better readability
                json_data = {
                    'export_info': {
                        'exported_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'format': 'json'
                    }
                }

                for data_type, rows in export_data.items():
                    headers = export_headers.get(data_type, [f'field_{i}' for i in range(len(rows[0]) if rows else 0)])
                    json_data[data_type] = {
                        'total_records': len(rows),
                        'records': [dict(zip(headers, row)) for row in rows]
                    }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4, default=str)

            elif format_type == "html":
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("""
                    <html>
                    <head>
                        <title>Email System Comprehensive Export</title>
                        <style>
                            body { font-family: Arial, sans-serif; margin: 20px; }
                            h1 { color: #333; }
                            h2 { color: #666; border-bottom: 2px solid #ddd; padding-bottom: 5px; }
                            table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
                            th { background-color: #4CAF50; color: white; padding: 10px; text-align: left; }
                            td { border: 1px solid #ddd; padding: 8px; }
                            tr:nth-child(even) { background-color: #f2f2f2; }
                            .metadata { background-color: #f9f9f9; padding: 10px; border-left: 4px solid #4CAF50; margin-bottom: 20px; }
                            .content { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: pre-wrap; }
                        </style>
                    </head>
                    <body>
                    """)
                    f.write("<h1>Email System Comprehensive Export</h1>")
                    f.write(f"<div class='metadata'>")
                    f.write(f"<p><strong>Exported on:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
                    f.write(f"<p><strong>Total sections:</strong> {len(export_data)}</p>")
                    f.write("</div>")

                    for data_type, rows in export_data.items():
                        f.write(f"<h2>{data_type.replace('_', ' ').title()}</h2>")
                        f.write(f"<p><strong>Total records:</strong> {len(rows)}</p>")
                        if rows:
                            headers = export_headers.get(data_type, [f'Field {i+1}' for i in range(len(rows[0]))])
                            f.write("<table>")
                            f.write("<tr>")
                            for header in headers:
                                f.write(f"<th>{header}</th>")
                            f.write("</tr>")

                            for row in rows[:500]:  # Limit to first 500 rows in HTML
                                f.write("<tr>")
                                for item in row:
                                    # Truncate very long content for display
                                    display_item = str(item) if item is not None else ''
                                    if len(display_item) > 200:
                                        display_item = display_item[:200] + '...'
                                    f.write(f"<td class='content'>{display_item}</td>")
                                f.write("</tr>")
                            f.write("</table>")

                            if len(rows) > 500:
                                f.write(f"<p><em>Showing first 500 of {len(rows)} records</em></p>")

                    f.write("</body></html>")

            # Show summary
            summary = f"Data exported successfully to {file_path}\n\n"
            summary += "Export Summary:\n"
            for data_type, rows in export_data.items():
                summary += f"  - {data_type.replace('_', ' ').title()}: {len(rows)} records\n"

            messagebox.showinfo("Export Complete", summary)
            self.dialog.destroy()

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Export Error", f"Failed to export data: {e}")


class HelpDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Help")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="University Communication System - Help", font=('Arial', 14, 'bold')).pack(pady=10)
        
        help_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD)
        help_text.pack(fill=tk.BOTH, expand=True)
        
        help_content = """
UNIVERSITY COMMUNICATION SYSTEM - USER GUIDE

Getting Started:
1. Use the Dashboard tab to see an overview
2. Navigate between tabs to access different features
3. Use toolbar buttons for quick actions

Email Features:
- Compose individual emails or bulk announcements
- Use templates for consistent messaging
- Schedule emails for later delivery
- View stored emails and their details

Messaging:
- Send direct messages to other users
- Reply to received messages
- Archive or delete messages as needed

Announcements:
- View system-wide announcements
- Create announcements (if you have permission)
- Mark announcements as read

Chat Rooms:
- Join public chat rooms
- Create your own rooms
- Invite other users to private rooms
- Participate in real-time conversations

Reports:
- Generate email usage reports
- Export data to CSV
- Monitor system health
- View communication statistics

For additional help, contact your system administrator.
        """
        
        help_text.insert(1.0, help_content)
        help_text.config(state=tk.DISABLED)
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)


class AboutDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("About")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="University Communication System", font=('Arial', 16, 'bold')).pack(pady=10)
        ttk.Label(main_frame, text="Email Manager GUI", font=('Arial', 12)).pack()
        ttk.Label(main_frame, text="Version 1.0", font=('Arial', 10)).pack(pady=5)
        
        desc_text = """
A comprehensive communication platform for universities
featuring email management, messaging, announcements,
and chat rooms with full backwards compatibility.

Features:
- Email composition and bulk sending
- Template management
- Direct messaging system
- Announcements and notifications
- Chat rooms and invitations
- Reporting and analytics
- Database and SMTP support
        """
        
        ttk.Label(main_frame, text=desc_text, justify=tk.CENTER).pack(pady=10)
        ttk.Label(main_frame, text="© 2024 University Communication System", font=('Arial', 9)).pack(pady=5)
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=20)


class ProgressDialog:
    """Progress dialog for long-running operations"""
    def __init__(self, parent, title="Processing..."):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x100")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.label = ttk.Label(main_frame, text="Please wait...")
        self.label.pack(pady=5)
        
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=5)
        self.progress.start()
        
        self.dialog.update()
    
    def update_text(self, text):
        """Update progress text"""
        self.label.config(text=text)
        self.dialog.update()
    
    def close(self):
        """Close progress dialog"""
        self.progress.stop()
        self.dialog.destroy()


class StatusNotification:
    """Temporary status notification"""
    def __init__(self, parent, message, duration=3000):
        self.notification = tk.Toplevel(parent)
        self.notification.title("")
        self.notification.geometry("300x80")
        
        # Position at bottom right of parent
        parent.update_idletasks()
        x = parent.winfo_x() + parent.winfo_width() - 320
        y = parent.winfo_y() + parent.winfo_height() - 100
        self.notification.geometry(f"+{x}+{y}")
        
        self.notification.overrideredirect(True)
        self.notification.configure(bg='#333333')
        
        # Message label
        label = tk.Label(self.notification, text=message, 
                        bg='#333333', fg='white', 
                        font=('Arial', 10), wraplength=280)
        label.pack(expand=True)
        
        # Auto-close after duration
        self.notification.after(duration, self.notification.destroy)


