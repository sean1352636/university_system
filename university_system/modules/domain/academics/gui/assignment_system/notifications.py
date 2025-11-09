"""Notification management"""

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
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.constants import paths
from collections import deque



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
        except:
            return self.auth.user_role in ['Admin', 'Faculty']

    def show_notifications(self):
        """Show notifications window"""
        # Create notifications window
        notif_window = tk.Toplevel(self.root)
        notif_window.title("Notifications")
        notif_window.geometry("600x400")
        notif_window.configure(bg='#f0f0f0')
        
        # Notifications list
        notif_frame = ttk.LabelFrame(notif_window, text="Your Notifications", padding=10)
        notif_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Treeview for notifications
        notif_tree = ttk.Treeview(notif_frame, columns=('Title', 'Message', 'Date', 'Read'), show='headings')
        
        for col in ['Title', 'Message', 'Date', 'Read']:
            notif_tree.heading(col, text=col)
            if col == 'Message':
                notif_tree.column(col, width=300)
            else:
                notif_tree.column(col, width=100)
        
        notif_tree.pack(fill='both', expand=True)
        
        # Load notifications
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            user_id = self.auth.current_user['id']
            cursor.execute('''
            SELECT title, message, created_datetime, is_read
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_datetime DESC
            LIMIT 50
            ''', (user_id,))
            
            notifications = cursor.fetchall()
            
            for notif in notifications:
                read_status = "Yes" if notif[3] else "No"
                tags = [] if notif[3] else ['unread']
                notif_tree.insert('', 'end', values=(notif[0], notif[1], notif[2], read_status), tags=tags)
            
            notif_tree.tag_configure('unread', background='#fff3cd')
            
            conn.close()
            
        except Exception as e:
            ttk.Label(notif_frame, text=f"Error loading notifications: {e}").pack()
        
        # Buttons
        btn_frame = ttk.Frame(notif_window)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="Mark All Read", 
                  command=lambda: self.mark_notifications_read(notif_tree)).pack(side='left')
        ttk.Button(btn_frame, text="Close", command=notif_window.destroy).pack(side='right')
    

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
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Check if notifications table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
            if not cursor.fetchone():
                self.notification_count = 0
                self.notification_btn.configure(text="📧 Notifications (0)")
                conn.close()
                return
            
        except Exception as e:
            print(f"Error updating notifications: {e}")
            self.notification_count = 0
            self.notification_btn.configure(text="📧 Notifications (0)")
    

    def run_due_date_reminders(self, *args, **kwargs):
        """Trigger the due-date reminder runner from CLI."""
        self._launch_gui_feature(self.run_due_date_reminders_ui, "due date reminders")
    
    

    def _get_unread_notification_count(self, user_id):
        """Get count of unread notifications"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
                SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0
            ''', (user_id,))
    
            count = cursor.fetchone()[0]
            conn.close()
    
            return count
        except Exception as e:
            print(f"Error getting unread count: {e}")
            return 0
    

    def _refresh_notifications(self, tree, user_id, type_filter="all", status_filter="all", search_text=""):
        """Refresh notifications list"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Build query
            query = '''
                SELECT id, title, message, type, is_read, created_datetime
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
                params.extend([f"%{search_text}%", f"%{search_text}%"])

            query += " ORDER BY created_datetime DESC"

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
                except:
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
    
            cursor.execute('''
                SELECT * FROM notifications WHERE id = ?
            ''', (notif_id,))
    
            notification = cursor.fetchone()
    
            if not notification:
                messagebox.showerror("Error", "Notification not found")
                conn.close()
                return
    
            # Mark as read
            if not notification[5]:  # is_read
                cursor.execute('''
                    UPDATE notifications SET is_read = 1 WHERE id = ?
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
            except:
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
    
            cursor.execute('''
                UPDATE notifications SET is_read = ? WHERE id = ? AND user_id = ?
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
    
            cursor.execute('''
                DELETE FROM notifications WHERE id = ? AND user_id = ?
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
            cursor = conn.cursor()

            user_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None

            cursor.execute('''
            SELECT enabled, email_enabled, push_enabled FROM notification_preferences
            WHERE user_id = ? AND notification_type = ?
            ''', (user_id, notification_type))

            settings = cursor.fetchone()
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

            ttk.Checkbutton(settings_frame, text="Push notifications (coming soon)",
                           variable=push_var, state='disabled').pack(anchor='w', pady=2)

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

                # Send email if enabled
                try:
                    cursor.execute('''
                    SELECT email_enabled FROM notification_preferences
                    WHERE user_id = ? AND notification_type = 'assignment_created'
                    ''', (student_id,))

                    pref = cursor.fetchone()
                    if pref and pref[0]:  # Email enabled
                        from university_system.infrastructure.email.email_service import send_email
                        send_email(
                            to_email=email,
                            subject=f"New Assignment: {assignment_title}",
                            body=f"Hello {first_name},\n\nA new assignment has been posted:\n\n"
                                 f"Title: {assignment_title}\n"
                                 f"Module: {module_code}\n"
                                 f"Due Date: {due_date}\n\n"
                                 f"Please log in to view the full details and submit your work.\n\n"
                                 f"Best regards,\n"
                                 f"Assignment System"
                        )
                except Exception as e:
                    print(f"Failed to send email to {email}: {e}")

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


