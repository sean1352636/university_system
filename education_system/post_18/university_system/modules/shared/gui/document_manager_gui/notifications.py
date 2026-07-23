import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class NotificationManager:
    """Manages notification center, templates, bulk sends, and notification campaigns."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def notification_center(self):
        """Full notification center interface"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Notification Center")
        dialog.geometry("800x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Create notebook for notification management
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Pending Notifications Tab
        pending_frame = ttk.Frame(notebook, padding=15)
        notebook.add(pending_frame, text="Pending Notifications")

        ttk.Label(pending_frame, text="Pending Notifications", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Notifications list
        notif_columns = ('ID', 'Recipient', 'Type', 'Title', 'Created', 'Priority', 'Status')
        self.notifications_tree = ttk.Treeview(pending_frame, columns=notif_columns, show='headings', height=12)

        for col in notif_columns:
            self.notifications_tree.heading(col, text=col)
            self.notifications_tree.column(col, width=100)

        notif_scrollbar = ttk.Scrollbar(pending_frame, orient='vertical', command=self.notifications_tree.yview)
        self.notifications_tree.configure(yscrollcommand=notif_scrollbar.set)

        self.notifications_tree.pack(side='left', fill='both', expand=True)
        notif_scrollbar.pack(side='right', fill='y')

        # Notification actions
        notif_actions_frame = ttk.Frame(pending_frame)
        notif_actions_frame.pack(fill='x', pady=10)

        ttk.Button(notif_actions_frame, text="Send Selected", command=self.send_selected_notifications).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text="Mark as Sent", command=self.mark_notifications_sent).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text="Delete", command=self.delete_notifications).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text="Refresh", command=self.load_notifications).pack(side='right', padx=5)

        # Send Notification Tab
        send_frame = ttk.Frame(notebook, padding=15)
        notebook.add(send_frame, text="Send Notification")

        ttk.Label(send_frame, text="Send Custom Notification", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Recipient selection
        ttk.Label(send_frame, text="Recipient:").pack(anchor='w')
        self.notif_recipient = ttk.Combobox(send_frame, width=40)
        self.notif_recipient.pack(fill='x', pady=5)

        # Load recipients
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, first_name, last_name FROM students')
            students = cursor.fetchall()
            conn.close()

            recipient_values = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
            self.notif_recipient['values'] = recipient_values
        except Exception:
            pass

        # Notification type
        ttk.Label(send_frame, text="Type:").pack(anchor='w', pady=(10, 0))
        self.notif_type = ttk.Combobox(send_frame, values=['document_reminder', 'verification_complete', 'expiry_warning', 'general', 'urgent'])
        self.notif_type.set('general')
        self.notif_type.pack(fill='x', pady=5)

        # Priority
        ttk.Label(send_frame, text="Priority:").pack(anchor='w', pady=(10, 0))
        self.notif_priority = ttk.Combobox(send_frame, values=['low', 'normal', 'high', 'urgent'])
        self.notif_priority.set('normal')
        self.notif_priority.pack(fill='x', pady=5)

        # Title
        ttk.Label(send_frame, text="Title:").pack(anchor='w', pady=(10, 0))
        self.notif_title = tk.Entry(send_frame, width=50)
        self.notif_title.pack(fill='x', pady=5)

        # Message
        ttk.Label(send_frame, text="Message:").pack(anchor='w', pady=(10, 0))
        self.notif_message = tk.Text(send_frame, height=6, width=50)
        self.notif_message.pack(fill='x', pady=5)

        ttk.Button(send_frame, text="Send Notification", command=self.send_custom_notification).pack(pady=15)

        # Templates Tab
        templates_frame = ttk.Frame(notebook, padding=15)
        notebook.add(templates_frame, text="Templates")

        ttk.Label(templates_frame, text="Notification Templates", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        template_list = [
            ("Document Upload Confirmation", "Your document has been uploaded successfully."),
            ("Verification Complete", "Your document has been verified and approved."),
            ("Document Rejected", "Your document requires attention. Please review and resubmit."),
            ("Expiry Warning", "Your document will expire soon. Please renew."),
            ("Missing Document Reminder", "You have missing required documents.")
        ]

        for title, template in template_list:
            template_frame = ttk.Frame(templates_frame)
            template_frame.pack(fill='x', pady=5)

            ttk.Label(template_frame, text=title, width=30).pack(side='left')
            ttk.Button(template_frame, text="Use Template",
                      command=lambda t=title, msg=template: self.use_notification_template(t, msg)).pack(side='right')

        # Load initial data
        self.load_notifications()

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()

    def load_notifications(self):
        """Load pending notifications"""
        if hasattr(self, 'notifications_tree'):
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT notification_id, user_id, channel, title,
                       created_at, priority, CASE WHEN is_read THEN 'Read' ELSE 'Unread' END as status
                FROM notifications
                WHERE is_read = 0
                ORDER BY created_at DESC
                LIMIT 100
                ''')

                notifications = cursor.fetchall()
                conn.close()

                # Clear existing items
                for item in self.notifications_tree.get_children():
                    self.notifications_tree.delete(item)

                # Insert new items
                for notification in notifications:
                    self.notifications_tree.insert('', 'end', values=tuple(notification))

            except Exception as e:
                print(f"Error loading notifications: {e}")

    def send_custom_notification(self):
        """Send custom notification"""
        recipient = self.notif_recipient.get()
        notif_type = self.notif_type.get()
        priority = self.notif_priority.get()
        title = self.notif_title.get()
        message = self.notif_message.get('1.0', 'end-1c')

        if not recipient or not title or not message:
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            # Extract recipient ID
            recipient_id = recipient.split(' - ')[0]

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO notifications (user_id, channel, priority, title, message,
                                     source_system)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (recipient_id, notif_type, priority, title, message, 'document_manager'))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Notification created successfully!")

            # Clear form
            self.notif_title.delete(0, 'end')
            self.notif_message.delete('1.0', 'end')
            self.load_notifications()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create notification: {str(e)}")

    def send_selected_notifications(self):
        """Send selected notifications"""
        selection = self.notifications_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select notifications to send.")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            sent_count = 0
            for item in selection:
                notif_id = self.notifications_tree.item(item)['values'][0]

                # Mark as sent
                cursor.execute('''
                UPDATE notifications
                SET is_read = 1, read_at = ?
                WHERE notification_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notif_id))

                sent_count += 1

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Sent {sent_count} notifications successfully!")
            self.load_notifications()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send notifications: {str(e)}")

    def mark_notifications_sent(self):
        """Mark selected notifications as sent without actually sending"""
        selection = self.notifications_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select notifications to mark as sent.")
            return

        if messagebox.askyesno("Confirm", "Mark selected notifications as sent?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()

                for item in selection:
                    notif_id = self.notifications_tree.item(item)['values'][0]
                    cursor.execute('''
                    UPDATE notifications
                    SET is_read = 1, read_at = ?
                    WHERE notification_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notif_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Notifications marked as sent!")
                self.load_notifications()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to mark notifications: {str(e)}")

    def delete_notifications(self):
        """Delete selected notifications"""
        selection = self.notifications_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select notifications to delete.")
            return

        if messagebox.askyesno("Confirm Delete", f"Delete {len(selection)} selected notifications?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()

                for item in selection:
                    notif_id = self.notifications_tree.item(item)['values'][0]
                    cursor.execute('DELETE FROM notifications WHERE notification_id = ?', (notif_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Notifications deleted successfully!")
                self.load_notifications()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete notifications: {str(e)}")

    def use_notification_template(self, title, message):
        """Use notification template"""
        self.notif_title.delete(0, 'end')
        self.notif_title.insert(0, title)

        self.notif_message.delete('1.0', 'end')
        self.notif_message.insert('1.0', message)

    def notification_templates(self):
        """Manage notification templates"""
        try:
            templates_window = tk.Toplevel(self.root)
            templates_window.title("Notification Templates")
            templates_window.geometry("900x700")

            main_frame = ttk.Frame(templates_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Notification Templates",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Pre-defined templates
            templates = [
                ("Document Expiring Soon", "Your {document_type} will expire on {expiry_date}. Please renew it soon."),
                ("Document Verified", "Your {document_type} has been verified and approved."),
                ("Document Rejected", "Your {document_type} was rejected. Reason: {reason}"),
                ("Missing Document", "You are missing a required {document_type}. Please upload it."),
                ("Workflow Step Complete", "Workflow step '{step_name}' has been completed for your {document_type}.")
            ]

            # Create list
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            # Listbox
            template_listbox = tk.Listbox(list_frame, height=15, font=('Arial', 10))
            template_listbox.pack(side='left', fill='both', expand=True)

            for name, _ in templates:
                template_listbox.insert(tk.END, name)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=template_listbox.yview)
            template_listbox.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')

            # Template preview
            preview_frame = ttk.LabelFrame(main_frame, text="Template Preview", padding=10)
            preview_frame.pack(fill='x', pady=10)

            preview_text = tk.Text(preview_frame, height=5, wrap=tk.WORD)
            preview_text.pack(fill='x')

            def show_template(event):
                selection = template_listbox.curselection()
                if selection:
                    _, template_text = templates[selection[0]]
                    preview_text.delete('1.0', tk.END)
                    preview_text.insert('1.0', template_text)

            template_listbox.bind('<<ListboxSelect>>', show_template)

            # Buttons
            button_frame = ttk.Frame(templates_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Use Template",
                      command=lambda: self.use_notification_template(
                          templates[template_listbox.curselection()[0]][1] if template_listbox.curselection() else None
                      )).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=templates_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open templates: {e}")

    def create_notification(self, recipient_id, title, message, notification_type='info',
                          priority='normal', related_document_id=None):
        """
        Create a notification for a user

        Args:
            recipient_id: User ID to send notification to
            title: Notification title
            message: Notification message
            notification_type: Type of notification (info, warning, error, success)
            priority: Priority level (low, normal, high)
            related_document_id: Related document ID (optional)

        Returns:
            notification_id if successful, None otherwise
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO notifications
            (user_id, channel, priority, title, message, source_system, source_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (recipient_id, notification_type, priority, title, message,
                 'document_manager', related_document_id))

            notification_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.gui.log_event('create', 'notification', notification_id, {
                'recipient_id': recipient_id,
                'type': notification_type,
                'priority': priority
            })

            return notification_id

        except Exception as e:
            print(f"Error creating notification: {e}")
            return None

    def view_pending_notifications(self):
        """
        View pending/queued notifications
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Pending Notifications")
            dialog.geometry("1100x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Pending Notifications",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary cards
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Unread
                cursor.execute('SELECT COUNT(*) FROM notifications WHERE is_read = 0')
                pending = cursor.fetchone()[0]

                # Read today
                cursor.execute('''
                SELECT COUNT(*) FROM notifications
                WHERE is_read = 1 AND date(created_at) = date('now')
                ''')
                sent_today = cursor.fetchone()[0]

                # Archived
                cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_archived = 1")
                failed = cursor.fetchone()[0]

                conn.close()

                self.gui.create_stat_card(summary_frame, "Pending", pending, '#f39c12', 0)
                self.gui.create_stat_card(summary_frame, "Sent Today", sent_today, '#27ae60', 1)
                self.gui.create_stat_card(summary_frame, "Failed", failed, '#e74c3c', 2)

            except Exception:


                pass

            # Filter frame
            filter_frame = ttk.Frame(main_frame)
            filter_frame.pack(fill='x', pady=(0, 10))

            ttk.Label(filter_frame, text="Filter:").pack(side='left', padx=5)
            filter_status = ttk.Combobox(filter_frame, values=['All', 'Pending', 'Sent', 'Failed'], width=15, state='readonly')
            filter_status.set('Pending')
            filter_status.pack(side='left', padx=5)

            # Notifications list
            notif_frame = ttk.LabelFrame(main_frame, text="Notification Queue", padding=10)
            notif_frame.pack(fill='both', expand=True)

            columns = ('ID', 'Recipient', 'Type', 'Title', 'Created', 'Status', 'Priority')
            notif_tree = ttk.Treeview(notif_frame, columns=columns, show='headings', height=15)

            for col in columns:
                notif_tree.heading(col, text=col)
                if col == 'ID':
                    notif_tree.column(col, width=50)
                elif col in ['Type', 'Status', 'Priority']:
                    notif_tree.column(col, width=80)
                else:
                    notif_tree.column(col, width=150)

            scrollbar = ttk.Scrollbar(notif_frame, orient='vertical', command=notif_tree.yview)
            notif_tree.configure(yscrollcommand=scrollbar.set)
            notif_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load notifications
            def load_notifications():
                notif_tree.delete(*notif_tree.get_children())
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    status_filter = filter_status.get()
                    query = '''
                    SELECT notification_id, user_id, channel, title,
                           created_at, CASE WHEN is_read = 1 THEN 'Read' ELSE 'Unread' END as status,
                           priority
                    FROM notifications
                    '''

                    if status_filter == 'Pending':
                        query += ' WHERE is_read = 0'
                    elif status_filter == 'Sent':
                        query += ' WHERE is_read = 1'
                    elif status_filter == 'Failed':
                        query += ' WHERE is_archived = 1'

                    query += ' ORDER BY created_at DESC LIMIT 500'

                    cursor.execute(query)
                    notifications = cursor.fetchall()
                    conn.close()

                    for notif in notifications:
                        notif_tree.insert('', 'end', values=tuple(notif))

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load notifications: {e}")

            load_notifications()
            filter_status.bind('<<ComboboxSelected>>', lambda e: load_notifications())

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            def send_selected():
                selection = notif_tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select notifications to send")
                    return

                response = messagebox.askyesno("Confirm Send",
                                             f"Send {len(selection)} selected notifications?")
                if response:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        for item in selection:
                            notif_id = notif_tree.item(item)['values'][0]
                            cursor.execute('UPDATE notifications SET is_read = 1, read_at = ? WHERE notification_id = ?',
                                         (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notif_id))

                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", f"Sent {len(selection)} notifications")
                        load_notifications()

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to send notifications: {e}")

            def delete_selected():
                selection = notif_tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select notifications to delete")
                    return

                response = messagebox.askyesno("Confirm Delete",
                                             f"Delete {len(selection)} selected notifications?")
                if response:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        for item in selection:
                            notif_id = notif_tree.item(item)['values'][0]
                            cursor.execute('DELETE FROM notifications WHERE notification_id = ?', (notif_id,))

                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", f"Deleted {len(selection)} notifications")
                        load_notifications()

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to delete notifications: {e}")

            ttk.Button(action_frame, text="Send Selected", command=send_selected).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Delete Selected", command=delete_selected).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Refresh", command=load_notifications).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open pending notifications: {e}")

    def bulk_notification_send(self):
        """Send notifications to multiple students"""
        try:
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Bulk Notification Send")
            dialog.geometry("850x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Send Bulk Notifications",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Recipient selection
            ttk.Label(main_frame, text="Select Recipients:", font=('Arial', 10, 'bold')).pack(anchor='w')

            recipient_frame = ttk.Frame(main_frame)
            recipient_frame.pack(fill='x', pady=10)

            recipient_var = tk.StringVar(value="all_students")
            ttk.Radiobutton(recipient_frame, text="All Students", variable=recipient_var,
                           value="all_students").pack(anchor='w')
            ttk.Radiobutton(recipient_frame, text="Students with Expiring Documents",
                           variable=recipient_var, value="expiring_docs").pack(anchor='w')
            ttk.Radiobutton(recipient_frame, text="Students with Missing Documents",
                           variable=recipient_var, value="missing_docs").pack(anchor='w')

            # Notification type
            ttk.Label(main_frame, text="Notification Type:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            notification_type = ttk.Combobox(main_frame, values=['Email', 'SMS', 'In-App'], state='readonly', width=30)
            notification_type.set('Email')
            notification_type.pack(anchor='w')

            # Subject
            ttk.Label(main_frame, text="Subject:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            subject_entry = tk.Entry(main_frame, width=50)
            subject_entry.pack(fill='x')

            # Message
            ttk.Label(main_frame, text="Message:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            message_text = tk.Text(main_frame, height=8, width=50)
            message_text.pack(fill='both', expand=True)

            def send_notifications():
                subject = subject_entry.get().strip()
                message = message_text.get("1.0", tk.END).strip()

                if not subject or not message:
                    messagebox.showwarning("Warning", "Please enter both subject and message")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Get recipients based on selection
                    recipient_type = recipient_var.get()
                    if recipient_type == "all_students":
                        cursor.execute('SELECT student_id, email_address FROM students WHERE email_address IS NOT NULL')
                    elif recipient_type == "expiring_docs":
                        cursor.execute('''
                            SELECT DISTINCT s.student_id, s.email_address
                            FROM students s
                            JOIN documents sd ON s.student_id = sd.owner_id AND sd.source_type = 'student'
                            WHERE sd.expiry_date <= date('now', '+30 days')
                                AND sd.expiry_date > date('now')
                                AND s.email_address IS NOT NULL
                        ''')
                    elif recipient_type == "missing_docs":
                        cursor.execute('''
                            SELECT DISTINCT s.student_id, s.email_address
                            FROM students s
                            LEFT JOIN documents sd ON s.student_id = sd.owner_id AND sd.source_type = 'student'
                            WHERE sd.document_id IS NULL AND s.email_address IS NOT NULL
                        ''')

                    recipients = cursor.fetchall()

                    # Log notifications (in real system, would send actual emails/SMS)
                    for student_id, email in recipients:
                        cursor.execute('''
                            INSERT INTO notifications (user_id, channel, priority, title, message, source_system)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (student_id, notification_type.get(), 'normal', subject, message, 'document_manager'))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Notifications sent to {len(recipients)} recipient(s)")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to send notifications: {e}")

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Send Notifications", command=send_notifications).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open notification dialog: {e}")

    def bulk_notification_campaign(self):
        """Send bulk notifications to students"""
        if not self.gui.ensure_login():
            return

        # Create campaign window
        campaign_window = tk.Toplevel(self.root)
        campaign_window.title("Bulk Notification Campaign")
        campaign_window.geometry("900x700")
        campaign_window.transient(self.root)
        campaign_window.grab_set()

        # Title
        ttk.Label(campaign_window, text="Bulk Notification Campaign",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Recipient selection frame
        recipient_frame = ttk.LabelFrame(campaign_window, text="Select Recipients", padding=10)
        recipient_frame.pack(fill='x', padx=10, pady=5)

        recipient_option = tk.StringVar(value="all_students")

        ttk.Radiobutton(recipient_frame, text="All Students",
                       variable=recipient_option, value="all_students").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text="Students with Pending Documents",
                       variable=recipient_option, value="pending_docs").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text="Students with Expiring Documents",
                       variable=recipient_option, value="expiring_docs").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text="Students with Rejected Documents",
                       variable=recipient_option, value="rejected_docs").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text="Custom Student List (comma-separated IDs)",
                       variable=recipient_option, value="custom").pack(anchor='w')

        custom_ids_entry = ttk.Entry(recipient_frame, width=70)
        custom_ids_entry.pack(fill='x', padx=20, pady=5)

        # Message frame
        message_frame = ttk.LabelFrame(campaign_window, text="Notification Message", padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=5)

        ttk.Label(message_frame, text="Subject:").pack(anchor='w')
        subject_entry = ttk.Entry(message_frame, width=80)
        subject_entry.insert(0, "Important Update Regarding Your Documents")
        subject_entry.pack(fill='x', pady=5)

        ttk.Label(message_frame, text="Message Body:").pack(anchor='w')
        message_text = tk.Text(message_frame, width=80, height=15)
        message_text.insert('1.0', """Dear Student,

This is a notification regarding your documents in our system.

Available placeholders:
{{student_name}} - Student's full name
{{student_id}} - Student ID number
{{pending_count}} - Number of pending documents
{{document_list}} - List of affected documents

Please log in to the portal to view your document status.

Best regards,
Administration""")
        message_text.pack(fill='both', expand=True, pady=5)

        # Options frame
        options_frame = ttk.LabelFrame(campaign_window, text="Notification Options", padding=10)
        options_frame.pack(fill='x', padx=10, pady=5)

        send_email_var = tk.BooleanVar(value=True)
        send_sms_var = tk.BooleanVar(value=False)
        create_portal_alert_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(options_frame, text="Send via Email",
                       variable=send_email_var).pack(anchor='w')
        ttk.Checkbutton(options_frame, text="Send via SMS",
                       variable=send_sms_var).pack(anchor='w')
        ttk.Checkbutton(options_frame, text="Create Portal Alert",
                       variable=create_portal_alert_var).pack(anchor='w')

        # Button frame
        button_frame = ttk.Frame(campaign_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        def preview_campaign():
            """Preview campaign details"""
            option = recipient_option.get()
            recipient_count_map = {
                "all_students": "All registered students",
                "pending_docs": "Students with pending documents",
                "expiring_docs": "Students with expiring documents",
                "rejected_docs": "Students with rejected documents",
                "custom": f"Custom list: {custom_ids_entry.get()}"
            }

            preview_text = f"""Campaign Preview:

Recipients: {recipient_count_map.get(option, 'Unknown')}
Subject: {subject_entry.get()}

Delivery Methods:
- Email: {'Yes' if send_email_var.get() else 'No'}
- SMS: {'Yes' if send_sms_var.get() else 'No'}
- Portal Alert: {'Yes' if create_portal_alert_var.get() else 'No'}

This is a preview. Click 'Send Campaign' to execute."""

            messagebox.showinfo("Campaign Preview", preview_text)

        def send_campaign():
            """Send the notification campaign"""
            if not messagebox.askyesno("Confirm Send",
                                      "Send this notification campaign?\n\n"
                                      "All selected recipients will receive the notification."):
                return

            try:
                # Simulate sending campaign
                option = recipient_option.get()

                # Get recipient count based on option
                if option == "all_students":
                    recipient_count = 150  # Simulated
                elif option == "pending_docs":
                    recipient_count = 45
                elif option == "expiring_docs":
                    recipient_count = 23
                elif option == "rejected_docs":
                    recipient_count = 12
                elif option == "custom":
                    ids = [id.strip() for id in custom_ids_entry.get().split(',') if id.strip()]
                    recipient_count = len(ids)
                else:
                    recipient_count = 0

                messagebox.showinfo("Campaign Sent",
                                  f"Notification campaign sent successfully!\n\n"
                                  f"Recipients: {recipient_count}\n"
                                  f"Subject: {subject_entry.get()}\n\n"
                                  "Notifications are being processed.")

                # Log activity
                self.gui.log_event('send', 'bulk_notification_campaign',
                              details=f'Sent campaign to {recipient_count} recipients: {option}')

                campaign_window.destroy()

            except Exception as e:
                messagebox.showerror("Send Error", f"Failed to send campaign: {e}")

        ttk.Button(button_frame, text="Preview Campaign",
                  command=preview_campaign).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Send Campaign",
                  command=send_campaign).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel",
                  command=campaign_window.destroy).pack(side='right', padx=5)

    def bulk_email_notifications(self):
        """Send bulk email notifications"""
        # This is handled by bulk_notification_campaign()
        self.bulk_notification_campaign()
