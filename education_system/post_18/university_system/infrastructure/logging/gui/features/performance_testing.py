import tkinter as tk
from tkinter import ttk, messagebox
import time
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.infrastructure.logging.gui.helpers import _t, initialize_database


class PerformanceTestingMixin:
    """Mixin providing performance testing functionality."""

    def test_database_response_times_gui(self):
        """GUI version of database response time testing"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.testing_response"))

        try:
            # Test different operations
            tests = [
                ("Connection", self._test_db_connection),
                ("Simple Query", self._test_simple_query),
                ("Complex Query", self._test_complex_query),
            ]

            output = "Database Response Time Test Results\n"
            output += "="*40 + "\n\n"
            output += f"{'Test':<20} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10}\n"
            output += "-" * 55 + "\n"

            for test_name, test_func in tests:
                times = []

                # Run each test 5 times
                for _ in range(5):
                    start_time = time.time()
                    try:
                        test_func()
                        end_time = time.time()
                        times.append((end_time - start_time) * 1000)  # Convert to ms
                    except Exception as e:
                        print(f"Error in {test_name}: {e}")
                        times.append(float('inf'))

                # Calculate statistics
                if times and all(t != float('inf') for t in times):
                    avg_time = sum(times) / len(times)
                    min_time = min(times)
                    max_time = max(times)

                    output += f"{test_name:<20} {avg_time:<9.2f} {min_time:<9.2f} {max_time:<9.2f}\n"

            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.response_test_completed"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.response_time", error=str(e)))
            self.update_status(_t("log_management.messages.response_test_failed"))

    def _test_db_connection(self):
        """Helper for connection test"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.close()

    def _test_simple_query(self):
        """Helper for simple query test"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        # First check if logs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM activity_log LIMIT 1")
            cursor.fetchone()
        else:
            # Initialize database if tables don't exist
            initialize_database()
        conn.close()

    def _test_complex_query(self):
        """Helper for complex query test"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, COUNT(*) as count
            FROM activity_log
            WHERE date(timestamp) >= date('now', '-7 days')
            GROUP BY username
            ORDER BY count DESC
            LIMIT 10
        """)
        cursor.fetchall()
        conn.close()

    def _test_insert_operation(self):
        """Helper for insert operation test"""
        test_log = {
            'timestamp': datetime.now().isoformat(),
            'user_id': 'perf_test',
            'username': 'performance_test',
            'action': 'test',
            'module': 'test',
            'details': 'Performance test entry',
            'status': 'success'
        }

        self.log_manager.db.insert_log(test_log)

        # Clean up immediately
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM activity_log WHERE username = 'performance_test'")
        conn.commit()
        conn.close()

    def test_query_performance(self):
        """Test database query performance"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.query_perf_test"))

        try:
            queries = [
                ("Simple count", "SELECT COUNT(*) FROM activity_log"),
                ("Date filter", "SELECT COUNT(*) FROM activity_log WHERE date(timestamp) >= date('now', '-7 days')"),
                ("User filter", "SELECT COUNT(*) FROM activity_log WHERE user_id = 'admin'"),
                ("Complex filter", "SELECT COUNT(*) FROM activity_log WHERE action = 'login' AND status = 'success'")
            ]

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))

            output = "Query Performance Test Results\n"
            output += "="*40 + "\n\n"
            output += f"{'Query':<20} {'Time (ms)':<12} {'Result':<10}\n"
            output += "-" * 45 + "\n"

            for name, query in queries:
                start_time = time.time()

                try:
                    cursor = conn.cursor()
                    cursor.execute(query)
                    result = cursor.fetchone()[0]

                    end_time = time.time()
                    duration_ms = (end_time - start_time) * 1000

                    output += f"{name:<20} {duration_ms:<11.2f} {result:<10}\n"

                except Exception as e:
                    output += f"{name:<20} ERROR: {str(e)}\n"

            conn.close()

            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.query_perf_completed"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.query_perf", error=str(e)))
            self.update_status(_t("log_management.messages.query_perf_failed"))

    def test_insert_performance(self):
        """Test database insert performance"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        test_count = tk.simpledialog.askinteger(_t("log_management.maintenance.insert_perf_title"),
                                              _t("log_management.maintenance.insert_count_prompt"),
                                              initialvalue=100, minvalue=10, maxvalue=1000)
        if not test_count:
            return

        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_insert_test", count=test_count)):
            self.update_status(f"Running insert performance test with {test_count} entries...")

            try:
                start_time = time.time()

                for i in range(test_count):
                    test_log = {
                        'timestamp': datetime.now().isoformat(),
                        'user_id': f'test_user_{i}',
                        'username': f'testuser{i}',
                        'action': 'test_action',
                        'module': 'performance_test',
                        'details': f'Test entry {i}',
                        'status': 'success'
                    }

                    self.log_manager.db.insert_log(test_log)

                end_time = time.time()
                duration = end_time - start_time

                output = f"""Insert Performance Test Results
===================================

Test entries: {test_count:,}
Total time: {duration:.2f} seconds
Average per insert: {(duration/test_count)*1000:.2f} ms
Inserts per second: {test_count/duration:.1f}

Test completed successfully!
"""

                # Cleanup test entries
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute("DELETE FROM activity_log WHERE action = 'performance_test'")
                deleted = cursor.rowcount
                conn.commit()
                conn.close()

                output += f"\nCleaned up {deleted} test entries."

                self.maintenance_text.delete("1.0", tk.END)
                self.maintenance_text.insert("1.0", output)

                self.update_status(_t("log_management.messages.insert_perf_completed"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.insert_perf", error=str(e)))
                self.update_status(_t("log_management.messages.insert_perf_failed"))

    def show_system_resources(self):
        """Show system resource usage"""
        try:
            import psutil

            # Get system info
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Get process info
            process = psutil.Process()

            output = f"""System Resource Usage
======================

CPU Usage: {cpu_percent}%
Memory Usage: {memory.percent}%
Available Memory: {memory.available / (1024**3):.2f} GB
Total Memory: {memory.total / (1024**3):.2f} GB

Disk Usage: {(disk.used / disk.total) * 100:.1f}%
Free Disk Space: {disk.free / (1024**3):.2f} GB
Total Disk Space: {disk.total / (1024**3):.2f} GB

Current Process:
Memory Usage: {process.memory_info().rss / (1024**2):.2f} MB
CPU Usage: {process.cpu_percent()}%
"""

        except ImportError:
            output = """System Resource Usage
======================

psutil library not available.
Install with: pip install psutil

Basic system information not available.
"""
        except Exception as e:
            output = f"Error retrieving system information: {str(e)}"

        self.maintenance_text.delete("1.0", tk.END)
        self.maintenance_text.insert("1.0", output)
