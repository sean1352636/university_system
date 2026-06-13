"""
Email Queue & Scheduler Manager GUI

Provides administrative interface for:
- Email queue management (queue_email, queue_template_email)
- Scheduled email management (schedule_send, process_scheduled_emails)
- Worker thread controls (start_email_workers, stop_email_workers)
- Queue and worker status monitoring
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from tkcalendar import DateEntry
import threading

from education_system.university_system.infrastructure.email.email_service import (
    queue_email,
    queue_template_email,
    schedule_send,
    process_scheduled_emails,
    start_email_workers,
    stop_email_workers,
    email_queue,
    worker_threads,
    list_templates,
    wait_for_email_queue,
    fix_inbox_display_issue,
    update_scheduled_email_status,
)
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.core.i18n import get_text as _t, init_i18n
init_i18n()


class EmailQueueSchedulerGUI:
    """Email Queue & Scheduler Management Interface"""

    def __init__(self, parent=None):
        """Initialize the GUI"""
        if parent:
            self.window = tk.Toplevel(parent)
        else:
            self.window = tk.Tk()

        self.window.title(_t("email_queue.title"))
        self.window.geometry("1000x700")

        self.setup_ui()
        self.refresh_status()

    def setup_ui(self):
        """Set up the user interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Worker Control & Status
        self.create_worker_tab()

        # Tab 2: Queue Email
        self.create_queue_tab()

        # Tab 3: Scheduled Emails
        self.create_scheduler_tab()

        # Tab 4: Monitor
        self.create_monitor_tab()

        # Tab 5: Utilities
        self.create_utilities_tab()

    def create_worker_tab(self):
        """Create worker control and status tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("email_queue.tabs.worker_control"))

        # Title
        title = tk.Label(tab, text=_t("email_queue.worker_thread_control"), font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Status frame
        status_frame = ttk.LabelFrame(tab, text=_t("email_queue.worker_status"), padding=10)
        status_frame.pack(fill=tk.X, padx=20, pady=10)

        self.worker_status_label = tk.Label(
            status_frame,
            text=_t("email_queue.status_checking"),
            font=("Arial", 12)
        )
        self.worker_status_label.pack()

        self.worker_count_label = tk.Label(
            status_frame,
            text=_t("email_queue.active_workers", count=0),
            font=("Arial", 10)
        )
        self.worker_count_label.pack()

        # Control buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=20)

        ttk.Button(
            button_frame,
            text=_t("email_queue.buttons.start_workers"),
            command=self.start_workers,
            width=20
        ).grid(row=0, column=0, padx=10, pady=5)

        ttk.Button(
            button_frame,
            text=_t("email_queue.buttons.stop_workers"),
            command=self.stop_workers,
            width=20
        ).grid(row=0, column=1, padx=10, pady=5)

        ttk.Button(
            button_frame,
            text=_t("email_queue.buttons.refresh_status"),
            command=self.refresh_status,
            width=20
        ).grid(row=1, column=0, padx=10, pady=5)

        # Info section
        info_frame = ttk.LabelFrame(tab, text=_t("email_queue.information"), padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        info_text = scrolledtext.ScrolledText(info_frame, height=15, wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True)

        info_content = """
EMAIL WORKER THREADS
====================

Worker threads process emails in the background queue, allowing non-blocking
email operations.

Functions:
- start_email_workers(): Start background worker threads
- stop_email_workers(): Gracefully stop worker threads
- email_worker(): Internal worker function (runs in background)

Usage:
1. Click "Start Workers" to activate background email processing
2. Workers will automatically process queued emails
3. Click "Stop Workers" before shutting down the application
4. Monitor worker status on the Monitor tab

Note: In database-only mode, emails are sent immediately without queueing.
Worker threads are only needed for high-volume async email processing.
"""
        info_text.insert("1.0", info_content)
        info_text.config(state=tk.DISABLED)

    def create_queue_tab(self):
        """Create queue email tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("email_queue.tabs.queue_emails"))

        # Title
        title = tk.Label(tab, text=_t("email_queue.queue_for_background"), font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Create sub-tabs for direct and template emails
        queue_notebook = ttk.Notebook(tab)
        queue_notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Direct Email Queue
        direct_tab = ttk.Frame(queue_notebook)
        queue_notebook.add(direct_tab, text=_t("email_queue.tabs.queue_direct_email"))
        self.create_direct_queue_form(direct_tab)

        # Template Email Queue
        template_tab = ttk.Frame(queue_notebook)
        queue_notebook.add(template_tab, text=_t("email_queue.tabs.queue_template_email"))
        self.create_template_queue_form(template_tab)

    def create_direct_queue_form(self, parent):
        """Create form for queueing direct emails"""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Recipient
        ttk.Label(form_frame, text=_t("email_queue.labels.recipient_email"), font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.queue_recipient = ttk.Entry(form_frame, width=50)
        self.queue_recipient.grid(row=0, column=1, pady=5, padx=10)

        # Subject
        ttk.Label(form_frame, text=_t("email_queue.labels.subject"), font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.queue_subject = ttk.Entry(form_frame, width=50)
        self.queue_subject.grid(row=1, column=1, pady=5, padx=10)

        # CC
        ttk.Label(form_frame, text=_t("email_queue.labels.cc"), font=("Arial", 10, "bold")).grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        self.queue_cc = ttk.Entry(form_frame, width=50)
        self.queue_cc.grid(row=2, column=1, pady=5, padx=10)

        # BCC
        ttk.Label(form_frame, text=_t("email_queue.labels.bcc"), font=("Arial", 10, "bold")).grid(
            row=3, column=0, sticky=tk.W, pady=5
        )
        self.queue_bcc = ttk.Entry(form_frame, width=50)
        self.queue_bcc.grid(row=3, column=1, pady=5, padx=10)

        # Body
        ttk.Label(form_frame, text=_t("email_queue.labels.email_body"), font=("Arial", 10, "bold")).grid(
            row=4, column=0, sticky=tk.NW, pady=5
        )
        self.queue_body = scrolledtext.ScrolledText(form_frame, width=50, height=15)
        self.queue_body.grid(row=4, column=1, pady=5, padx=10)

        # Submit button
        ttk.Button(
            form_frame,
            text=_t("email_queue.buttons.add_to_queue"),
            command=self.queue_direct_email,
            width=20
        ).grid(row=5, column=1, pady=20)

    def create_template_queue_form(self, parent):
        """Create form for queueing template emails"""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Template selection
        ttk.Label(form_frame, text=_t("email_queue.labels.template"), font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.queue_template = ttk.Combobox(form_frame, width=47, state="readonly")
        self.queue_template.grid(row=0, column=1, pady=5, padx=10)
        self.load_templates()

        # Recipient
        ttk.Label(form_frame, text=_t("email_queue.labels.recipient_email"), font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.queue_template_recipient = ttk.Entry(form_frame, width=50)
        self.queue_template_recipient.grid(row=1, column=1, pady=5, padx=10)

        # Template Variables
        ttk.Label(form_frame, text=_t("email_queue.labels.template_variables_json"), font=("Arial", 10, "bold")).grid(
            row=2, column=0, sticky=tk.NW, pady=5
        )
        self.queue_template_vars = scrolledtext.ScrolledText(form_frame, width=50, height=10)
        self.queue_template_vars.grid(row=2, column=1, pady=5, padx=10)
        self.queue_template_vars.insert("1.0", '{\n  "name": "John Doe",\n  "date": "2025-11-08"\n}')

        # CC
        ttk.Label(form_frame, text=_t("email_queue.labels.cc"), font=("Arial", 10, "bold")).grid(
            row=3, column=0, sticky=tk.W, pady=5
        )
        self.queue_template_cc = ttk.Entry(form_frame, width=50)
        self.queue_template_cc.grid(row=3, column=1, pady=5, padx=10)

        # Submit button
        ttk.Button(
            form_frame,
            text=_t("email_queue.buttons.add_template_to_queue"),
            command=self.queue_template_email_action,
            width=25
        ).grid(row=4, column=1, pady=20)

    def create_scheduler_tab(self):
        """Create scheduled emails tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("email_queue.tabs.schedule_emails"))

        # Title
        title = tk.Label(tab, text=_t("email_queue.schedule_for_future"), font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Create sub-tabs
        scheduler_notebook = ttk.Notebook(tab)
        scheduler_notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Schedule new email tab
        schedule_tab = ttk.Frame(scheduler_notebook)
        scheduler_notebook.add(schedule_tab, text=_t("email_queue.tabs.schedule_new"))
        self.create_schedule_form(schedule_tab)

        # View/process scheduled emails tab
        view_tab = ttk.Frame(scheduler_notebook)
        scheduler_notebook.add(view_tab, text=_t("email_queue.tabs.manage_scheduled"))
        self.create_scheduled_view(view_tab)

    def create_schedule_form(self, parent):
        """Create form for scheduling emails"""
        form_frame = ttk.Frame(parent)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Template selection
        ttk.Label(form_frame, text=_t("email_queue.labels.template"), font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.schedule_template = ttk.Combobox(form_frame, width=47, state="readonly")
        self.schedule_template.grid(row=0, column=1, pady=5, padx=10)
        self.load_schedule_templates()

        # Date selection
        ttk.Label(form_frame, text=_t("email_queue.labels.scheduled_date"), font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.schedule_date = DateEntry(form_frame, width=47, date_pattern='yyyy-mm-dd')
        self.schedule_date.grid(row=1, column=1, pady=5, padx=10)

        # Time selection
        ttk.Label(form_frame, text=_t("email_queue.labels.scheduled_time"), font=("Arial", 10, "bold")).grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        time_frame = ttk.Frame(form_frame)
        time_frame.grid(row=2, column=1, pady=5, padx=10, sticky=tk.W)

        self.schedule_hour = ttk.Spinbox(time_frame, from_=0, to=23, width=5, format="%02.0f")
        self.schedule_hour.set("09")
        self.schedule_hour.pack(side=tk.LEFT)

        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=5)

        self.schedule_minute = ttk.Spinbox(time_frame, from_=0, to=59, width=5, format="%02.0f")
        self.schedule_minute.set("00")
        self.schedule_minute.pack(side=tk.LEFT)

        # Recipients
        ttk.Label(form_frame, text=_t("email_queue.labels.recipients_per_line"), font=("Arial", 10, "bold")).grid(
            row=3, column=0, sticky=tk.NW, pady=5
        )
        self.schedule_recipients = scrolledtext.ScrolledText(form_frame, width=50, height=8)
        self.schedule_recipients.grid(row=3, column=1, pady=5, padx=10)

        # Template variables per recipient
        ttk.Label(form_frame, text=_t("email_queue.labels.template_variables_array"), font=("Arial", 10, "bold")).grid(
            row=4, column=0, sticky=tk.NW, pady=5
        )
        self.schedule_vars = scrolledtext.ScrolledText(form_frame, width=50, height=8)
        self.schedule_vars.grid(row=4, column=1, pady=5, padx=10)
        self.schedule_vars.insert("1.0", '[\n  {"name": "Recipient 1"},\n  {"name": "Recipient 2"}\n]')

        # Submit button
        ttk.Button(
            form_frame,
            text=_t("email_queue.buttons.schedule_emails"),
            command=self.schedule_emails,
            width=20
        ).grid(row=5, column=1, pady=20)

    def create_scheduled_view(self, parent):
        """Create view for managing scheduled emails"""
        # Control buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(
            button_frame,
            text=_t("email_queue.buttons.process_due_now"),
            command=self.process_due_emails,
            width=25
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t("email_queue.buttons.refresh_list"),
            command=self.refresh_scheduled_list,
            width=20
        ).pack(side=tk.LEFT, padx=5)

        # Scheduled emails list
        list_frame = ttk.LabelFrame(parent, text=_t("email_queue.scheduled_emails"), padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Create treeview
        columns = ("ID", _t("email_queue.columns.template"), _t("email_queue.columns.recipient"), _t("email_queue.columns.scheduled_for"), _t("email_queue.columns.status"))
        self.scheduled_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.scheduled_tree.heading(col, text=col)
            if col == "ID":
                self.scheduled_tree.column(col, width=50)
            elif col == _t("email_queue.columns.scheduled_for"):
                self.scheduled_tree.column(col, width=150)
            elif col == _t("email_queue.columns.status"):
                self.scheduled_tree.column(col, width=100)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.scheduled_tree.yview)
        self.scheduled_tree.configure(yscrollcommand=scrollbar.set)

        self.scheduled_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load scheduled emails
        self.refresh_scheduled_list()

    def create_monitor_tab(self):
        """Create monitoring tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("email_queue.tabs.monitor"))

        # Title
        title = tk.Label(tab, text=_t("email_queue.queue_worker_monitoring"), font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Status frame
        status_frame = ttk.LabelFrame(tab, text=_t("email_queue.current_status"), padding=10)
        status_frame.pack(fill=tk.X, padx=20, pady=10)

        self.monitor_queue_size = tk.Label(status_frame, text=_t("email_queue.queue_size", count=0), font=("Arial", 12))
        self.monitor_queue_size.pack()

        self.monitor_workers = tk.Label(status_frame, text=_t("email_queue.active_workers", count=0), font=("Arial", 12))
        self.monitor_workers.pack()

        self.monitor_scheduled = tk.Label(status_frame, text=_t("email_queue.pending_scheduled", count=0), font=("Arial", 12))
        self.monitor_scheduled.pack()

        # Refresh button
        ttk.Button(
            tab,
            text=_t("email_queue.buttons.refresh_status"),
            command=self.refresh_monitor,
            width=20
        ).pack(pady=10)

        # Details
        details_frame = ttk.LabelFrame(tab, text=_t("email_queue.details"), padding=10)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.monitor_details = scrolledtext.ScrolledText(details_frame, height=20, wrap=tk.WORD)
        self.monitor_details.pack(fill=tk.BOTH, expand=True)

    def create_utilities_tab(self):
        """Create utilities tab for additional functions"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("email_queue.tabs.utilities"))

        # Title
        title = tk.Label(tab, text=_t("email_queue.utilities_title"), font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Utility 1: Wait for Queue
        queue_frame = ttk.LabelFrame(tab, text=_t("email_queue.queue_management"), padding=10)
        queue_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(
            queue_frame,
            text=_t("email_queue.wait_description"),
            font=("Arial", 10)
        ).pack(pady=5)

        ttk.Button(
            queue_frame,
            text=_t("email_queue.buttons.wait_for_queue"),
            command=self.wait_for_queue,
            width=25
        ).pack(pady=5)

        # Utility 2: Fix Inbox Display
        inbox_frame = ttk.LabelFrame(tab, text=_t("email_queue.database_repair"), padding=10)
        inbox_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(
            inbox_frame,
            text=_t("email_queue.inbox_fix_description"),
            font=("Arial", 10)
        ).pack(pady=5)

        ttk.Button(
            inbox_frame,
            text=_t("email_queue.buttons.fix_inbox_display"),
            command=self.fix_inbox_display,
            width=25
        ).pack(pady=5)

        # Utility 3: Update Scheduled Email Status
        status_frame = ttk.LabelFrame(tab, text=_t("email_queue.update_scheduled_status"), padding=10)
        status_frame.pack(fill=tk.X, padx=20, pady=10)

        form_frame = ttk.Frame(status_frame)
        form_frame.pack(pady=5)

        ttk.Label(form_frame, text=_t("email_queue.labels.email_id"), font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=5, padx=5
        )
        self.status_email_id = ttk.Entry(form_frame, width=20)
        self.status_email_id.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(form_frame, text=_t("email_queue.labels.new_status"), font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=5, padx=5
        )
        self.status_new_status = ttk.Combobox(
            form_frame,
            values=["pending", "sent", "failed", "cancelled"],
            state="readonly",
            width=18
        )
        self.status_new_status.grid(row=1, column=1, pady=5, padx=5)
        self.status_new_status.current(0)

        ttk.Button(
            status_frame,
            text=_t("email_queue.buttons.update_status"),
            command=self.update_email_status,
            width=20
        ).pack(pady=10)

        # Utility 4: Automated Scheduler Reference
        scheduler_frame = ttk.LabelFrame(tab, text=_t("email_queue.automated_scheduler"), padding=10)
        scheduler_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        info_text = scrolledtext.ScrolledText(scheduler_frame, height=8, wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True, pady=5)

        scheduler_info = _t("email_queue.scheduler_info")
        info_text.insert("1.0", scheduler_info)
        info_text.config(state=tk.DISABLED)

    # Action methods

    def start_workers(self):
        """Start email worker threads"""
        try:
            result = start_email_workers()
            if result:
                messagebox.showinfo(_t("common.success"), _t("email_queue.messages.workers_started"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("email_queue.messages.workers_already_running"))
            self.refresh_status()
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_start_workers')}: {str(e)}")

    def stop_workers(self):
        """Stop email worker threads"""
        try:
            result = stop_email_workers()
            if result:
                messagebox.showinfo(_t("common.success"), _t("email_queue.messages.workers_stopped"))
            self.refresh_status()
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_stop_workers')}: {str(e)}")

    def queue_direct_email(self):
        """Queue a direct email"""
        recipient = self.queue_recipient.get().strip()
        subject = self.queue_subject.get().strip()
        body = self.queue_body.get("1.0", tk.END).strip()
        cc = self.queue_cc.get().strip()
        bcc = self.queue_bcc.get().strip()

        if not recipient or not subject or not body:
            messagebox.showerror(_t("common.error"), _t("email_queue.messages.recipient_subject_body_required"))
            return

        try:
            # Parse CC and BCC
            cc_list = [x.strip() for x in cc.split(",")] if cc else None
            bcc_list = [x.strip() for x in bcc.split(",")] if bcc else None

            result = queue_email(recipient, subject, body, cc_list, bcc_list)

            if result:
                messagebox.showinfo(_t("common.success"), _t("email_queue.messages.email_queued"))
                # Clear form
                self.queue_recipient.delete(0, tk.END)
                self.queue_subject.delete(0, tk.END)
                self.queue_body.delete("1.0", tk.END)
                self.queue_cc.delete(0, tk.END)
                self.queue_bcc.delete(0, tk.END)
            else:
                messagebox.showwarning(_t("common.warning"), _t("email_queue.messages.email_sent_immediately"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_queue_email')}: {str(e)}")

    def queue_template_email_action(self):
        """Queue a template email"""
        import json

        template = self.queue_template.get()
        recipient = self.queue_template_recipient.get().strip()
        template_vars_str = self.queue_template_vars.get("1.0", tk.END).strip()
        cc = self.queue_template_cc.get().strip()

        if not template or not recipient:
            messagebox.showerror(_t("common.error"), _t("email_queue.messages.template_recipient_required"))
            return

        try:
            # Parse template vars
            template_vars = json.loads(template_vars_str) if template_vars_str else {}

            # Parse CC
            cc_list = [x.strip() for x in cc.split(",")] if cc else None

            result = queue_template_email(template, recipient, template_vars, cc_list)

            if result:
                messagebox.showinfo(_t("common.success"), _t("email_queue.messages.template_email_queued"))
                # Clear form
                self.queue_template_recipient.delete(0, tk.END)
            else:
                messagebox.showwarning(_t("common.warning"), _t("email_queue.messages.email_sent_immediately"))

        except json.JSONDecodeError:
            messagebox.showerror(_t("common.error"), _t("email_queue.messages.invalid_json"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_queue_email')}: {str(e)}")

    def schedule_emails(self):
        """Schedule emails for future delivery"""
        import json

        template = self.schedule_template.get()
        date = self.schedule_date.get_date()
        hour = int(self.schedule_hour.get())
        minute = int(self.schedule_minute.get())
        recipients_str = self.schedule_recipients.get("1.0", tk.END).strip()
        vars_str = self.schedule_vars.get("1.0", tk.END).strip()

        if not template or not recipients_str:
            messagebox.showerror(_t("common.error"), _t("email_queue.messages.template_recipients_required"))
            return

        try:
            # Parse recipients
            recipients = [r.strip() for r in recipients_str.split("\n") if r.strip()]

            # Parse template vars
            template_vars_list = json.loads(vars_str) if vars_str else None

            # Create datetime
            scheduled_datetime = datetime(date.year, date.month, date.day, hour, minute)

            if scheduled_datetime <= datetime.now():
                messagebox.showerror(_t("common.error"), _t("email_queue.messages.time_must_be_future"))
                return

            result = schedule_send(scheduled_datetime, recipients, template, template_vars_list)

            if result:
                messagebox.showinfo(_t("common.success"), _t("email_queue.messages.emails_scheduled", count=len(recipients)))
                self.refresh_scheduled_list()
            else:
                messagebox.showerror(_t("common.error"), _t("email_queue.messages.failed_schedule_emails"))

        except json.JSONDecodeError:
            messagebox.showerror(_t("common.error"), _t("email_queue.messages.invalid_json"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_schedule_emails')}: {str(e)}")

    def process_due_emails(self):
        """Process due scheduled emails"""
        try:
            count = process_scheduled_emails()
            messagebox.showinfo(_t("common.success"), _t("email_queue.messages.emails_processed", count=count))
            self.refresh_scheduled_list()
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_process_emails')}: {str(e)}")

    def refresh_scheduled_list(self):
        """Refresh the list of scheduled emails"""
        # Clear existing items
        for item in self.scheduled_tree.get_children():
            self.scheduled_tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, template_name, recipient_email, scheduled_date, status
                FROM scheduled_emails
                ORDER BY scheduled_date DESC
                LIMIT 100
            ''')

            scheduled_emails = cursor.fetchall()
            conn.close()

            for email in scheduled_emails:
                self.scheduled_tree.insert("", tk.END, values=email)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_load_scheduled')}: {str(e)}")

    def load_templates(self):
        """Load available email templates"""
        try:
            templates = list_templates()
            self.queue_template['values'] = templates
            if templates:
                self.queue_template.current(0)
        except Exception:
            pass

    def load_schedule_templates(self):
        """Load available email templates for scheduler"""
        try:
            templates = list_templates()
            self.schedule_template['values'] = templates
            if templates:
                self.schedule_template.current(0)
        except Exception:
            pass

    def refresh_status(self):
        """Refresh worker status"""
        try:
            worker_count = len(worker_threads)
            is_running = any(t.is_alive() for t in worker_threads)

            if is_running:
                self.worker_status_label.config(
                    text=_t("email_queue.status_running"),
                    fg="green"
                )
            else:
                self.worker_status_label.config(
                    text=_t("email_queue.status_stopped"),
                    fg="red"
                )

            self.worker_count_label.config(text=_t("email_queue.active_workers", count=worker_count))

        except Exception as e:
            self.worker_status_label.config(
                text=f"{_t('email_queue.status_error')}: {str(e)}",
                fg="red"
            )

    def refresh_monitor(self):
        """Refresh monitoring information"""
        try:
            # Get queue size
            queue_size = email_queue.qsize()

            # Get worker count
            worker_count = len([t for t in worker_threads if t.is_alive()])

            # Get scheduled email count
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM scheduled_emails WHERE status = 'pending'")
            scheduled_count = cursor.fetchone()[0]
            conn.close()

            # Update labels
            self.monitor_queue_size.config(text=_t("email_queue.queue_size", count=queue_size))
            self.monitor_workers.config(text=_t("email_queue.active_workers", count=worker_count))
            self.monitor_scheduled.config(text=_t("email_queue.pending_scheduled", count=scheduled_count))

            # Update details
            details = _t("email_queue.monitoring_details",
                        queue_size=queue_size,
                        worker_count=worker_count,
                        scheduled_count=scheduled_count,
                        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            self.monitor_details.delete("1.0", tk.END)
            self.monitor_details.insert("1.0", details)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_refresh_monitor')}: {str(e)}")

    def wait_for_queue(self):
        """Wait for email queue to empty"""
        try:
            # Show a progress dialog
            progress_window = tk.Toplevel(self.window)
            progress_window.title(_t("email_queue.waiting_for_queue"))
            progress_window.geometry("300x100")
            progress_window.transient(self.window)
            progress_window.grab_set()

            label = tk.Label(progress_window, text=_t("email_queue.waiting_message"), pady=20)
            label.pack()

            # Run wait_for_email_queue in a thread
            def wait_thread():
                try:
                    result = wait_for_email_queue()
                    progress_window.destroy()
                    if result:
                        messagebox.showinfo(_t("common.success"), _t("email_queue.messages.all_emails_sent"))
                    else:
                        messagebox.showinfo(_t("common.info"), _t("email_queue.messages.no_queue_to_wait"))
                except Exception as e:
                    progress_window.destroy()
                    messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.error_waiting_queue')}: {str(e)}")

            thread = threading.Thread(target=wait_thread, daemon=True)
            thread.start()

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_wait_queue')}: {str(e)}")

    def fix_inbox_display(self):
        """Fix inbox display issues"""
        try:
            if messagebox.askyesno(_t("common.confirm"), _t("email_queue.messages.confirm_fix_inbox")):
                result = fix_inbox_display_issue()
                if result:
                    messagebox.showinfo(_t("common.success"), _t("email_queue.messages.inbox_fixed"))
                else:
                    messagebox.showwarning(_t("common.warning"), _t("email_queue.messages.no_issues_found"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_fix_inbox')}: {str(e)}")

    def update_email_status(self):
        """Update scheduled email status"""
        email_id = self.status_email_id.get().strip()
        new_status = self.status_new_status.get()

        if not email_id:
            messagebox.showerror(_t("common.error"), _t("email_queue.messages.email_id_required"))
            return

        try:
            email_id = int(email_id)
            result = update_scheduled_email_status(email_id, new_status)

            if result:
                messagebox.showinfo(_t("common.success"), _t("email_queue.messages.status_updated", email_id=email_id, status=new_status))
                self.status_email_id.delete(0, tk.END)
                self.refresh_scheduled_list()
            else:
                messagebox.showerror(_t("common.error"), _t("email_queue.messages.failed_update_status"))

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("email_queue.messages.email_id_must_be_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('email_queue.messages.failed_update_status')}: {str(e)}")

    def run(self):
        """Run the GUI"""
        self.window.mainloop()


def main():
    """Main entry point"""
    app = EmailQueueSchedulerGUI()
    app.run()


if __name__ == "__main__":
    main()
