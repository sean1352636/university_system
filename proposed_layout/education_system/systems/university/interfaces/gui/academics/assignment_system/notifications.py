"""Notification management"""

from education_system.systems.university.infrastructure.sql_safety import escape_like
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure import paths
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from collections import deque

# Try to import desktop notification library
try:
    from plyer import notification as desktop_notification
    DESKTOP_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    DESKTOP_NOTIFICATIONS_AVAILABLE = False


def send_push_notification(title: str, message: str, app_name: str = "University System",
                          timeout: int = 10, root: tk.Tk = None):
    """
    Send a push notification to the user.

    Uses desktop notifications if available, falls back to in-app popup.

    Args:
        title: Notification title
        message: Notification message body
        app_name: Application name for the notification
        timeout: Time in seconds before notification disappears
        root: Tkinter root window for fallback popup

    Returns:
        bool: True if notification was sent successfully
    """
    try:
        if DESKTOP_NOTIFICATIONS_AVAILABLE:
            # Use desktop notification
            desktop_notification.notify(
                title=title,
                message=message[:256],  # Limit message length for notifications
                app_name=app_name,
                timeout=timeout
            )
            return True
        elif root:
            # Fallback: Show in-app toast notification
            _show_toast_notification(root, title, message, timeout)
            return True
        else:
            print(f"Push notification (no handler): {title} - {message}")
            return False
    except Exception as e:
        print(f"Failed to send push notification: {e}")
        return False


def _show_toast_notification(root: tk.Tk, title: str, message: str, timeout: int = 10):
    """Show an in-app toast notification popup"""
    try:
        # Create toast window
        toast = tk.Toplevel(root)
        toast.overrideredirect(True)
        toast.attributes('-topmost', True)

        # Position in bottom-right corner
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        toast_width = 350
        toast_height = 100
        x_pos = screen_width - toast_width - 20
        y_pos = screen_height - toast_height - 60
        toast.geometry(f"{toast_width}x{toast_height}+{x_pos}+{y_pos}")

        # Style the toast
        toast.configure(bg='#2c3e50')

        # Add content frame
        content_frame = tk.Frame(toast, bg='#2c3e50', padx=10, pady=10)
        content_frame.pack(fill='both', expand=True)

        # Title
        title_label = tk.Label(content_frame, text=title, font=('Arial', 10, 'bold'),
                              fg='white', bg='#2c3e50', anchor='w')
        title_label.pack(fill='x')

        # Message (truncate if too long)
        display_msg = message[:100] + "..." if len(message) > 100 else message
        msg_label = tk.Label(content_frame, text=display_msg, font=('Arial', 9),
                            fg='#ecf0f1', bg='#2c3e50', anchor='w', wraplength=320,
                            justify='left')
        msg_label.pack(fill='x', pady=(5, 0))

        # Close button
        close_btn = tk.Label(content_frame, text="×", font=('Arial', 14, 'bold'),
                            fg='#ecf0f1', bg='#2c3e50', cursor='hand2')
        close_btn.place(relx=1.0, rely=0, anchor='ne')
        close_btn.bind('<Button-1>', lambda e: toast.destroy())

        # Auto-close after timeout
        toast.after(timeout * 1000, toast.destroy)

    except Exception as e:
        print(f"Failed to show toast notification: {e}")



class NotificationManager:
    """Notification management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def show_notifications(self):
        """Open the unified Notifications Hub (unread inbox over the live
        ``messages`` + cross-system feed) — the same window the main GUI bell
        opens.

        This screen previously built its own window over the retired
        ``notifications`` table, which no longer receives messages, so it always
        showed an empty list even when the user had unread mail. Routing to the
        shared Hub keeps the list consistent with the header count."""
        try:
            from education_system.systems.university.interfaces.gui.operations.communications.notifications.notifications_gui import (
                NotificationsGUI,
            )
            NotificationsGUI(parent=self.root)
        except Exception as e:
            messagebox.showerror("Notifications", f"Unable to open notifications: {e}")

        # The user is about to read them, so refresh the header badge.
        try:
            self.update_notifications()
        except Exception:
            pass


    def mark_notifications_read(self, tree):
        """Mark all notifications as read"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            user_id = self.auth.current_user['id']
            cursor.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (user_id,))

            conn.commit()
            conn.close()

            # Update tree view
            for item in tree.get_children():
                tree.set(item, 'Read', 'Yes')
                tree.item(item, tags=[])

            # Update notification count
            self.update_notifications()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to mark notifications as read: {e}")


    def update_notifications(self):
        """Update notification count in header"""
        try:
            # Get current user ID
            user_id = None
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                user_id = self.auth.current_user.get('id')

            if not user_id:
                self.gui.notification_count = 0
                if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'notification_btn'):
                    self.gui.layout.notification_btn.configure(text="\U0001f514 Notifications (0)")
                return

            count = self._get_unread_notification_count(user_id)
            self.gui.notification_count = count

            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'notification_btn'):
                self.gui.layout.notification_btn.configure(text=f"\U0001f514 Notifications ({count})")

        except Exception as e:
            print(f"Error updating notifications: {e}")
            self.gui.notification_count = 0
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'notification_btn'):
                self.gui.layout.notification_btn.configure(text="\U0001f514 Notifications (0)")


    def _get_unread_notification_count(self, user_id):
        """Live unread count = unread University ``messages`` (keyed by the
        legacy ``users.id``) + unread cross-system messages (keyed by the
        shared auth id). Mirrors the main GUI bell.

        The legacy ``notifications`` table this used to query was retired when
        notifications became an unread inbox over ``messages``/cross-system, so
        counting it always returned 0 — the cause of the "0 notifications" bug.
        Returns 0 on any failure. ``user_id`` is accepted for signature
        compatibility; the ids are derived from the auth session so the
        cross-system lookup uses the correct shared auth id."""
        cu = getattr(self.auth, "current_user", None) if self.auth else None
        if not isinstance(cu, dict):
            return 0

        total = 0

        # University inbox: messages addressed to this user's legacy users.id.
        uni_id = cu.get("id")
        if uni_id is not None:
            try:
                from education_system.systems.university.infrastructure.database.db import (
                    get_connection,
                )
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM messages "
                        "WHERE recipient_id = ? "
                        "AND (is_read IS NULL OR is_read = 0) "
                        "AND (is_archived IS NULL OR is_archived = 0) "
                        "AND (is_deleted_by_recipient IS NULL OR is_deleted_by_recipient = 0)",
                        (uni_id,),
                    ).fetchone()
                    if row:
                        total += int(row[0])
            except Exception as e:
                print(f"Error getting university unread count: {e}")

        # Cross-system inbox: keyed by the shared auth.db id.
        cross_id = cu.get("shared_auth_id") or cu.get("user_id") or cu.get("id")
        if cross_id is not None:
            try:
                from education_system.platform.features.messaging.messaging_service import (
                    InterSystemMessagingService,
                )
                total += int(
                    InterSystemMessagingService().get_unread_count(cross_id, "university")
                )
            except Exception as e:
                print(f"Error getting cross-system unread count: {e}")

        return total


    def _refresh_notifications(self, tree, user_id, type_filter="all", status_filter="all", search_text=""):
        """Refresh notifications list"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check column names for compatibility
            cursor.execute("PRAGMA table_info(notifications)")
            columns = {col[1] for col in cursor.fetchall()}
            id_col = 'notification_id' if 'notification_id' in columns else 'id'
            date_col = 'created_datetime' if 'created_datetime' in columns else 'created_at'

            # Build query
            query = f'''
                SELECT {id_col}, title, message, type, is_read, {date_col}
                FROM notifications
                WHERE user_id = ?
            '''
            params = [user_id]

            # Apply type filter
            if type_filter != "all":
                query += " AND (type = ? OR notification_type = ?)"
                params.extend([type_filter, type_filter])

            # Apply status filter
            if status_filter == "unread":
                query += " AND is_read = 0"
            elif status_filter == "read":
                query += " AND is_read = 1"

            # Apply search
            if search_text:
                query += " AND (title LIKE ? OR message LIKE ?)"
                params.extend([f"%{escape_like(search_text)}%", f"%{escape_like(search_text)}%"])

            query += f" ORDER BY {date_col} DESC"

            cursor.execute(query, params)
            notifications = cursor.fetchall()

            # Type colors
            type_colors = {
                'info': '#17a2b8',
                'warning': '#ffc107',
                'success': '#28a745',
                'error': '#dc3545'
            }

            for notif in notifications:
                notif_id, title, message, notif_type, is_read, created_datetime = notif

                status = "Read" if is_read else "Unread"

                # Truncate message if too long
                display_message = message[:100] + "..." if len(message) > 100 else message

                # Format date
                try:
                    date_obj = datetime.fromisoformat(created_datetime)
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    formatted_date = created_datetime

                # Insert into tree
                item_id = tree.insert('', 'end', text=notif_id,
                                     values=(status, notif_type, title or "No title",
                                            display_message, formatted_date),
                                     tags=(f'type_{notif_type}', 'unread' if not is_read else 'read'))

            # Configure tags
            tree.tag_configure('unread', font=('TkDefaultFont', 10, 'bold'))
            tree.tag_configure('read', foreground='#666666')

            for ntype, color in type_colors.items():
                tree.tag_configure(f'type_{ntype}', foreground=color)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load notifications: {str(e)}")
            print(f"Error refreshing notifications: {e}")


    def _view_notification_details(self, tree, user_id):
        """View notification details"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a notification to view")
            return

        notif_id = tree.item(selection[0])['text']

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check column names for compatibility
            cursor.execute("PRAGMA table_info(notifications)")
            columns = {col[1] for col in cursor.fetchall()}
            id_col = 'notification_id' if 'notification_id' in columns else 'id'
            safe_id_col = validate_identifier(id_col, "column")

            cursor.execute('''
                SELECT * FROM notifications WHERE [''' + safe_id_col + '''] = ?
            ''', (notif_id,))

            notification = cursor.fetchone()

            if not notification:
                messagebox.showerror("Error", "Notification not found")
                conn.close()
                return

            # Mark as read - is_read is at index 6 in the legacy schema
            cursor.execute("PRAGMA table_info(notifications)")
            col_info = cursor.fetchall()
            is_read_idx = next((i for i, col in enumerate(col_info) if col[1] == 'is_read'), None)

            if is_read_idx is not None and not notification[is_read_idx]:
                cursor.execute('''
                    UPDATE notifications SET is_read = 1 WHERE [''' + safe_id_col + '''] = ?
                ''', (notif_id,))
                conn.commit()

            conn.close()

            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title("Notification Details")
            detail_window.geometry("700x500")
            detail_window.configure(bg='#f0f0f0')

            # Info frame
            info_frame = ttk.LabelFrame(detail_window, text="Notification Information", padding=10)
            info_frame.pack(fill='x', padx=10, pady=10)

            # Type
            ttk.Label(info_frame, text="Type:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
            type_label = ttk.Label(info_frame, text=notification[4], font=('TkDefaultFont', 10, 'bold'))
            type_label.grid(row=0, column=1, sticky='w', padx=5, pady=2)

            # Title
            ttk.Label(info_frame, text="Title:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
            title_label = ttk.Label(info_frame, text=notification[2] or "No title",
                                   font=('TkDefaultFont', 10, 'bold'))
            title_label.grid(row=1, column=1, sticky='w', padx=5, pady=2)

            # Date
            ttk.Label(info_frame, text="Date:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
            try:
                date_obj = datetime.fromisoformat(notification[6])
                formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                formatted_date = notification[6]
            ttk.Label(info_frame, text=formatted_date).grid(row=2, column=1, sticky='w', padx=5, pady=2)

            # Assignment reference (if any)
            if notification[7]:  # assignment_id
                ttk.Label(info_frame, text="Assignment:").grid(row=3, column=0, sticky='w', padx=5, pady=2)
                ttk.Label(info_frame, text=f"ID: {notification[7]}").grid(row=3, column=1, sticky='w', padx=5, pady=2)

            # Message content frame
            content_frame = ttk.LabelFrame(detail_window, text="Message", padding=10)
            content_frame.pack(fill='both', expand=True, padx=10, pady=10)

            message_text = scrolledtext.ScrolledText(content_frame, width=60, height=15, wrap=tk.WORD)
            message_text.pack(fill='both', expand=True)
            message_text.insert('1.0', notification[3])
            message_text.config(state='disabled')

            # Button frame
            button_frame = ttk.Frame(detail_window)
            button_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(button_frame, text="Close", command=detail_window.destroy).pack(side='right', padx=5)

            # Refresh the tree to show updated read status
            self._refresh_notifications(tree, user_id)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to view notification: {str(e)}")
            print(f"Error viewing notification: {e}")


    def _mark_notification_read(self, tree, user_id, is_read):
        """Mark notification as read or unread"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a notification")
            return

        notif_id = tree.item(selection[0])['text']

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check column names for compatibility
            cursor.execute("PRAGMA table_info(notifications)")
            columns = {col[1] for col in cursor.fetchall()}
            id_col = 'notification_id' if 'notification_id' in columns else 'id'
            safe_id_col = validate_identifier(id_col, "column")

            cursor.execute('''
                UPDATE notifications SET is_read = ? WHERE [''' + safe_id_col + '''] = ? AND user_id = ?
            ''', (1 if is_read else 0, notif_id, user_id))

            conn.commit()
            conn.close()

            # Refresh the tree
            self._refresh_notifications(tree, user_id)

            status = "read" if is_read else "unread"
            messagebox.showinfo("Success", f"Notification marked as {status}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update notification: {str(e)}")
            print(f"Error marking notification: {e}")


    def _delete_notification(self, tree, user_id):
        """Delete selected notification"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a notification to delete")
            return

        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this notification?"):
            return

        notif_id = tree.item(selection[0])['text']

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check column names for compatibility
            cursor.execute("PRAGMA table_info(notifications)")
            columns = {col[1] for col in cursor.fetchall()}
            id_col = 'notification_id' if 'notification_id' in columns else 'id'
            safe_id_col = validate_identifier(id_col, "column")

            cursor.execute('''
                DELETE FROM notifications WHERE [''' + safe_id_col + '''] = ? AND user_id = ?
            ''', (notif_id, user_id))

            conn.commit()
            conn.close()

            # Refresh the tree
            self._refresh_notifications(tree, user_id)

            messagebox.showinfo("Success", "Notification deleted")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete notification: {str(e)}")
            print(f"Error deleting notification: {e}")


    def _mark_all_notifications_read(self, tree, user_id):
        """Mark all notifications as read"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0
            ''', (user_id,))

            rows_updated = cursor.rowcount
            conn.commit()
            conn.close()

            # Refresh the tree
            self._refresh_notifications(tree, user_id)

            messagebox.showinfo("Success", f"Marked {rows_updated} notification(s) as read")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to mark notifications as read: {str(e)}")
            print(f"Error marking all as read: {e}")


    def _clear_read_notifications(self, tree, user_id):
        """Delete all read notifications"""
        if not messagebox.askyesno("Confirm Clear",
                                   "Are you sure you want to delete all read notifications?"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM notifications WHERE user_id = ? AND is_read = 1
            ''', (user_id,))

            rows_deleted = cursor.rowcount
            conn.commit()
            conn.close()

            # Refresh the tree
            self._refresh_notifications(tree, user_id)

            messagebox.showinfo("Success", f"Cleared {rows_deleted} read notification(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear read notifications: {str(e)}")
            print(f"Error clearing read notifications: {e}")



    def manage_notifications(self, *args, **kwargs):
        """Manage notifications for the current user.

        Features:
        - Display all notifications with type, message, timestamp
        - Show read/unread status
        - Mark notifications as read/unread
        - Delete notifications
        - Filter by type (info, warning, success, error)
        - Clear all read notifications
        """
        try:
            # Create notifications window
            notif_window = tk.Toplevel(self.root)
            notif_window.title("Notification Management")
            notif_window.geometry("1000x700")
            notif_window.configure(bg='#f0f0f0')

            # Get current user ID
            user_id = self.auth.current_user.get('id')
            if not user_id:
                messagebox.showerror("Error", "User not authenticated")
                notif_window.destroy()
                return

            # Ensure notifications table exists
            self.gui.db._ensure_notifications_table()

            # Header frame
            header_frame = ttk.Frame(notif_window)
            header_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(header_frame, text="Notifications",
                     font=('TkDefaultFont', 16, 'bold')).pack(side='left')

            # Get unread count
            unread_count = self._get_unread_notification_count(user_id)
            ttk.Label(header_frame, text=f"({unread_count} unread)",
                     font=('TkDefaultFont', 12)).pack(side='left', padx=10)

            # Filter frame
            filter_frame = ttk.LabelFrame(notif_window, text="Filters", padding=10)
            filter_frame.pack(fill='x', padx=10, pady=5)

            # Type filter
            ttk.Label(filter_frame, text="Type:").pack(side='left', padx=5)
            type_var = tk.StringVar(value="all")

            ttk.Radiobutton(filter_frame, text="All", variable=type_var, value="all").pack(side='left', padx=5)
            ttk.Radiobutton(filter_frame, text="Info", variable=type_var, value="info").pack(side='left', padx=5)
            ttk.Radiobutton(filter_frame, text="Warning", variable=type_var, value="warning").pack(side='left', padx=5)
            ttk.Radiobutton(filter_frame, text="Success", variable=type_var, value="success").pack(side='left', padx=5)
            ttk.Radiobutton(filter_frame, text="Error", variable=type_var, value="error").pack(side='left', padx=5)

            # Status filter
            ttk.Separator(filter_frame, orient='vertical').pack(side='left', fill='y', padx=10)
            ttk.Label(filter_frame, text="Status:").pack(side='left', padx=5)
            status_var = tk.StringVar(value="all")

            ttk.Radiobutton(filter_frame, text="All", variable=status_var, value="all").pack(side='left', padx=5)
            ttk.Radiobutton(filter_frame, text="Unread", variable=status_var, value="unread").pack(side='left', padx=5)
            ttk.Radiobutton(filter_frame, text="Read", variable=status_var, value="read").pack(side='left', padx=5)

            # Search
            ttk.Separator(filter_frame, orient='vertical').pack(side='left', fill='y', padx=10)
            ttk.Label(filter_frame, text="Search:").pack(side='left', padx=5)
            search_var = tk.StringVar()
            search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=20)
            search_entry.pack(side='left', padx=5)

            # Apply filter button
            ttk.Button(filter_frame, text="Apply Filters",
                      command=lambda: self._refresh_notifications(tree, user_id, type_var.get(),
                                                                 status_var.get(), search_var.get())).pack(side='left', padx=10)

            # Notifications list
            list_frame = ttk.Frame(notif_window)
            list_frame.pack(fill='both', expand=True, padx=10, pady=5)

            # Treeview for notifications
            columns = ('Status', 'Type', 'Title', 'Message', 'Date')
            tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

            tree.heading('#0', text='ID')
            tree.heading('Status', text='Status')
            tree.heading('Type', text='Type')
            tree.heading('Title', text='Title')
            tree.heading('Message', text='Message')
            tree.heading('Date', text='Date')

            tree.column('#0', width=50)
            tree.column('Status', width=80)
            tree.column('Type', width=80)
            tree.column('Title', width=150)
            tree.column('Message', width=400)
            tree.column('Date', width=150)

            # Scrollbar
            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Action buttons
            button_frame = ttk.Frame(notif_window)
            button_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(button_frame, text="View Details",
                      command=lambda: self._view_notification_details(tree, user_id)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Mark as Read",
                      command=lambda: self._mark_notification_read(tree, user_id, True)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Mark as Unread",
                      command=lambda: self._mark_notification_read(tree, user_id, False)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Delete Selected",
                      command=lambda: self._delete_notification(tree, user_id)).pack(side='left', padx=5)

            ttk.Separator(button_frame, orient='vertical').pack(side='left', fill='y', padx=10)

            ttk.Button(button_frame, text="Mark All as Read",
                      command=lambda: self._mark_all_notifications_read(tree, user_id)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Clear All Read",
                      command=lambda: self._clear_read_notifications(tree, user_id)).pack(side='left', padx=5)

            ttk.Button(button_frame, text="Refresh",
                      command=lambda: self._refresh_notifications(tree, user_id, type_var.get(),
                                                                 status_var.get(), search_var.get())).pack(side='right', padx=5)

            # Load notifications
            self._refresh_notifications(tree, user_id, type_var.get(), status_var.get(), search_var.get())

            # Bind double-click to view details
            tree.bind('<Double-1>', lambda e: self._view_notification_details(tree, user_id))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load notifications: {str(e)}")
            print(f"Error in manage_notifications: {e}")


    def run_due_date_reminders(self, *args, **kwargs):
        """Trigger the due-date reminder runner from CLI."""
        self._launch_gui_feature(self.run_due_date_reminders_ui, "due date reminders")


    def _configure_notification_type(self, notification_type):
        """Configure specific notification type settings"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Configure {notification_type.replace('_', ' ').title()} Notifications")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=f"{notification_type.replace('_', ' ').title()} Settings",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Get current settings
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                user_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None

                cursor.execute('''
                SELECT enabled, email_enabled, push_enabled FROM notification_preferences
                WHERE user_id = ? AND notification_type = ?
                ''', (user_id, notification_type))

                settings = cursor.fetchone()
            finally:
                conn.close()

            if settings:
                enabled, email_enabled, push_enabled = settings
            else:
                enabled, email_enabled, push_enabled = 1, 1, 0

            # Settings frame
            settings_frame = ttk.LabelFrame(dialog, text="Notification Channels", padding=20)
            settings_frame.pack(fill='both', expand=True, padx=10, pady=10)

            enabled_var = tk.BooleanVar(value=bool(enabled))
            email_var = tk.BooleanVar(value=bool(email_enabled))
            push_var = tk.BooleanVar(value=bool(push_enabled))

            ttk.Checkbutton(settings_frame, text="Enable notifications for this type",
                           variable=enabled_var).pack(anchor='w', pady=5)

            ttk.Separator(settings_frame, orient='horizontal').pack(fill='x', pady=10)

            ttk.Label(settings_frame, text="Delivery Methods:", font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=(0, 10))

            ttk.Checkbutton(settings_frame, text="In-app notifications",
                           variable=enabled_var, state='disabled').pack(anchor='w', pady=2)

            ttk.Checkbutton(settings_frame, text="Email notifications",
                           variable=email_var).pack(anchor='w', pady=2)

            push_checkbox_text = "Push notifications (Desktop)" if DESKTOP_NOTIFICATIONS_AVAILABLE else "Push notifications (In-app popups)"
            ttk.Checkbutton(settings_frame, text=push_checkbox_text,
                           variable=push_var).pack(anchor='w', pady=2)

            # Description
            desc_frame = ttk.LabelFrame(dialog, text="Description", padding=10)
            desc_frame.pack(fill='x', padx=10, pady=(0, 10))

            descriptions = {
                'assignment_created': 'Notifications when new assignments are posted',
                'assignment_due': 'Reminders for upcoming assignment due dates',
                'grade_posted': 'Notifications when grades are posted',
                'extension_approved': 'Notifications for extension request decisions',
                'peer_review_assigned': 'Notifications for peer review assignments'
            }

            desc_text = descriptions.get(notification_type, 'Notification settings for this type')
            ttk.Label(desc_frame, text=desc_text, wraplength=450).pack()

            # Save button
            def save_notification_settings():
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    cursor.execute('''
                    INSERT OR REPLACE INTO notification_preferences
                    (user_id, notification_type, enabled, email_enabled, push_enabled, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, notification_type, 1 if enabled_var.get() else 0,
                          1 if email_var.get() else 0, 1 if push_var.get() else 0,
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Notification settings saved successfully!", parent=dialog)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save settings: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Save Settings", command=save_notification_settings,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to configure notifications: {e}")


    def _notify_new_assignment(self, assignment_id, assignment_title, module_code, due_date):
        """Send notification for new assignment to all enrolled students"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get all students enrolled in the module
            cursor.execute('''
            SELECT DISTINCT s.student_id, s.email_address, s.first_name
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = ?
            ''', (module_code,))

            students = cursor.fetchall()

            if not students:
                conn.close()
                return

            # Create notification for each student
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            notification_count = 0

            for student_id, email, first_name in students:
                # Insert notification
                cursor.execute('''
                INSERT INTO notifications
                (user_id, type, title, message, related_id, is_read, created_at)
                VALUES (?, 'assignment_created', ?, ?, ?, 0, ?)
                ''', (
                    student_id,
                    'New Assignment Posted',
                    f"A new assignment '{assignment_title}' has been posted for {module_code}. Due: {due_date}",
                    assignment_id,
                    timestamp
                ))

                notification_count += 1

                # Get notification preferences
                try:
                    cursor.execute('''
                    SELECT email_enabled, push_enabled FROM notification_preferences
                    WHERE user_id = ? AND notification_type = 'assignment_created'
                    ''', (student_id,))

                    pref = cursor.fetchone()
                    email_enabled = pref[0] if pref else True  # Default to enabled
                    push_enabled = pref[1] if pref else False

                    notification_title = 'New Assignment Posted'
                    notification_message = f"A new assignment '{assignment_title}' has been posted for {module_code}. Due: {due_date}"

                    # Send email if enabled
                    if email_enabled:
                        try:
                            from education_system.systems.university.infrastructure.email.email_service import send_email

                            # Render email template
                            subject, body = render_template('assignment_posted', {
                                'first_name': first_name,
                                'assignment_title': assignment_title,
                                'module_code': module_code,
                                'due_date': due_date
                            })

                            send_email(
                                recipient_email=email,
                                subject=subject,
                                body=body
                            )
                        except Exception as email_err:
                            print(f"Failed to send email to {email}: {email_err}")

                    # Send push notification if enabled
                    if push_enabled:
                        try:
                            send_push_notification(
                                title=notification_title,
                                message=notification_message,
                                app_name="University Assignments",
                                timeout=15,
                                root=self.root
                            )
                        except Exception as push_err:
                            print(f"Failed to send push notification for student {student_id}: {push_err}")

                except Exception as e:
                    print(f"Failed to process notification preferences for {student_id}: {e}")

            conn.commit()
            conn.close()

            print(f"Sent {notification_count} notifications for new assignment: {assignment_title}")

        except Exception as e:
            print(f"Failed to send new assignment notifications: {e}")


    def _launch_gui_feature(self, callback, feature_name):
        """Helper to launch GUI features with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")


