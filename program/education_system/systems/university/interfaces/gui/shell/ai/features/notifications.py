import tkinter as tk
from tkinter import ttk


class NotificationsMixin:
    """Mixin for in-app notification system."""

    def create_notification_system(self):
        """Create in-app notification system"""
        self.notifications = []

        # Notification frame (initially hidden)
        self.notification_frame = ttk.Frame(self.root)

        def show_notification(message, level="info", duration=3000):
            """Show a notification message"""
            # Create notification widget
            notif_colors = {
                "info": "#2196F3",
                "success": "#4CAF50",
                "warning": "#FF9800",
                "error": "#F44336"
            }

            notif_widget = ttk.Label(self.notification_frame,
                                    text=message,
                                    background=notif_colors.get(level, "#2196F3"),
                                    foreground="white",
                                    padding=10)
            notif_widget.pack(fill=tk.X, pady=2)

            # Auto-hide after duration
            self.root.after(duration, lambda: notif_widget.destroy())

            # Show notification frame if hidden
            if not self.notification_frame.winfo_viewable():
                self.notification_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        return show_notification
