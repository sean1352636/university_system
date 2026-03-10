"""Real-time log monitoring."""

import time
import queue
import threading

from .database import LogDatabase


class RealTimeMonitor:
    """Real-time log monitoring"""

    def __init__(self, db: LogDatabase):
        self.db = db
        self.subscribers = []
        self.running = False
        self.log_queue = queue.Queue()

    def subscribe(self, callback):
        """Subscribe to real-time log updates"""
        self.subscribers.append(callback)

    def unsubscribe(self, callback):
        """Unsubscribe from real-time log updates"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def notify_subscribers(self, log_entry):
        """Notify all subscribers of new log entry"""
        for callback in self.subscribers:
            try:
                callback(log_entry)
            except Exception as e:
                print(f"Error notifying subscriber: {e}")

    def add_log_entry(self, log_entry):
        """Add a new log entry for real-time processing"""
        self.log_queue.put(log_entry)
        self.notify_subscribers(log_entry)

    def start_monitoring(self):
        """Start real-time monitoring"""
        self.running = True
        monitor_thread = threading.Thread(target=self._monitor_loop)
        monitor_thread.daemon = True
        monitor_thread.start()
        print("Real-time monitoring started")

    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.running = False
        print("Real-time monitoring stopped")

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Process queued log entries
                while not self.log_queue.empty():
                    log_entry = self.log_queue.get_nowait()
                    # Process the log entry (store in DB, check alerts, etc.)
                    self.db.insert_log(log_entry)

                time.sleep(1)  # Check every second
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
