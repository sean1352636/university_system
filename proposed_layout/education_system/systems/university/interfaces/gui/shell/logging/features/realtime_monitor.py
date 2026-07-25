import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import logging
from datetime import datetime, timedelta

from education_system.systems.university.interfaces.gui.shell.logging.helpers import _t

logger = logging.getLogger(__name__)


class RealtimeMonitorMixin:
    """Mixin providing real-time monitoring functionality."""

    def open_realtime_monitor(self):
        """Open real-time monitoring window"""
        monitor_window = tk.Toplevel(self.root)
        monitor_window.title(_t("log_management.dialogs.realtime_monitor"))
        monitor_window.geometry("800x600")

        ttk.Label(monitor_window, text="Real-time Activity Monitor",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Control frame
        control_frame = ttk.Frame(monitor_window)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Status labels
        self.monitor_status_label = ttk.Label(control_frame, text="Status: Stopped")
        self.monitor_status_label.pack(side=tk.LEFT)

        self.monitor_count_label = ttk.Label(control_frame, text="Events: 0")
        self.monitor_count_label.pack(side=tk.RIGHT)

        # Log display
        log_frame = ttk.LabelFrame(monitor_window, text="Live Activity Feed")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.monitor_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD,
                                                     font=("Courier", 9),
                                                     fg="#000000", bg="#FFFFFF")
        self.monitor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Control buttons
        button_frame = ttk.Frame(monitor_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        self.monitor_running = False
        self.monitor_event_count = 0

        def start_monitoring():
            if not self.log_manager:
                messagebox.showerror("Error", "Log manager not available")
                return

            self.monitor_running = True
            self.monitor_status_label.config(text="Status: Running")
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)

            # Start monitoring in background thread
            def monitor_thread():
                def log_callback(log_entry):
                    if self.monitor_running:
                        timestamp = log_entry.get('timestamp', '')[:19]
                        user = log_entry.get('username', '')
                        action = log_entry.get('action', '')
                        module = log_entry.get('module', '')
                        status = log_entry.get('status', '')

                        status_symbol = "✅" if status == "success" else "❌"
                        log_line = f"{timestamp} | {status_symbol} {user} - {action} on {module}\n"

                        # Update UI in main thread
                        monitor_window.after(0, lambda: self.update_monitor_display(log_line))

                # Subscribe to real-time updates
                self.log_manager.monitor.subscribe(log_callback)

                # Show recent activity
                try:
                    recent_filters = {
                        'date_from': (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d')
                    }
                    recent_logs = self.log_manager.db.search_logs(recent_filters, limit=20)

                    for log in reversed(recent_logs):  # Show oldest first
                        if self.monitor_running:
                            log_callback(log)

                except Exception as e:
                    print(f"Error loading recent logs: {e}")

            threading.Thread(target=monitor_thread, daemon=True).start()

        def stop_monitoring():
            self.monitor_running = False
            self.monitor_status_label.config(text="Status: Stopped")
            start_btn.config(state=tk.NORMAL)
            stop_btn.config(state=tk.DISABLED)

        def clear_monitor():
            self.monitor_text.delete("1.0", tk.END)
            self.monitor_event_count = 0
            self.monitor_count_label.config(text="Events: 0")

        start_btn = ttk.Button(button_frame, text="▶️ Start", command=start_monitoring)
        start_btn.pack(side=tk.LEFT, padx=(0, 5))

        stop_btn = ttk.Button(button_frame, text="⏹️ Stop", command=stop_monitoring, state=tk.DISABLED)
        stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="🗑️ Clear", command=clear_monitor).pack(side=tk.LEFT)

        # Auto-start if real-time monitoring is enabled
        if self.log_manager and self.log_manager.monitor.running:
            start_monitoring()

    def update_monitor_display(self, log_line):
        """Update the monitor display with new log entry"""
        try:
            self.monitor_text.insert(tk.END, log_line)
            self.monitor_text.see(tk.END)

            # Keep only last 1000 lines
            lines = self.monitor_text.get("1.0", tk.END).split('\n')
            if len(lines) > 1000:
                self.monitor_text.delete("1.0", f"{len(lines)-1000}.0")

            self.monitor_event_count += 1
            self.monitor_count_label.config(text=f"Events: {self.monitor_event_count}")

        except tk.TclError as e:
            # Window was closed
            logger.debug(f"Monitor update failed (window likely closed): {e}")
