import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.logging.gui.helpers import (
    _t, STUDENT_SYSTEM_AVAILABLE, get_student_db_connection,
)


class StudentIntegrationMixin:
    """Mixin providing student system integration functionality."""

    def create_student_integration_tab(self):
        """Create tab for student system integration"""
        if not STUDENT_SYSTEM_AVAILABLE:
            return

        self.student_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.student_frame, text=_t("log_management.tabs.student_system"))

        # Integration controls
        controls_frame = ttk.LabelFrame(self.student_frame, text=_t("log_management.student_system.integration"))
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(padx=10, pady=10)

        ttk.Button(button_frame, text=_t("log_management.student_system.view_logs"),
                   command=self.view_student_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text=_t("log_management.student_system.sync_data"),
                   command=self.sync_student_data).pack(side=tk.LEFT)

        # Quick stats frame
        stats_frame = ttk.LabelFrame(self.student_frame, text=_t("log_management.student_system.quick_stats"))
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.student_stats_text = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, height=20,
                                                             fg="#000000", bg="#FFFFFF")
        self.student_stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Load initial stats
        self.load_student_stats()

    def open_student_system(self):
        """Open student management system in new window"""
        if not STUDENT_SYSTEM_AVAILABLE:
            messagebox.showerror("Error", "Student management system not available")
            return

        try:
            # Create new window for student system
            student_window = tk.Toplevel(self.root)
            student_window.title(_t("log_management.dialogs.student_system"))
            student_window.geometry("1200x800")

            # Initialize student system (you'll need to adapt this based on student system's auth)
            from education_system.post_18.university_system.infrastructure.auth import UserAuth
            from education_system.post_18.university_system.infrastructure.shared_context import get_auth
            from education_system.post_18.university_system.modules.shared.gui.main.main_gui import UnifiedManagementGUI
            student_auth = get_auth()
            if student_auth is None:
                student_auth = UserAuth()

            # Create student GUI instance
            student_app = UnifiedManagementGUI(student_auth)
            student_app.root = student_window
            student_app.setup_main_layout()

            if not student_auth.current_user:
                student_app.show_login_screen()
            else:
                student_app.show_main_interface()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open student system: {str(e)}")

    def sync_student_data(self):
        """Sync data between student system and log system"""
        try:
            if not STUDENT_SYSTEM_AVAILABLE:
                messagebox.showerror("Error", "Student management system not available")
                return

            # Get student data
            conn = get_student_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id, email_address, first_name, last_name FROM students')
                students = cursor.fetchall()
                conn.close()

                # Log the sync operation
                if self.log_manager:
                    sync_log = {
                        'timestamp': datetime.now().isoformat(),
                        'user_id': 'system',
                        'username': 'log_system',
                        'action': 'sync',
                        'module': 'student_integration',
                        'details': f'Synced {len(students)} student records',
                        'status': 'success'
                    }
                    self.log_manager.db.insert_log(sync_log)

                messagebox.showinfo("Success", f"Synced {len(students)} student records")
                self.load_student_stats()

        except Exception as e:
            messagebox.showerror("Error", f"Sync failed: {str(e)}")

    def load_student_stats(self):
        """Load student system statistics"""
        try:
            if not STUDENT_SYSTEM_AVAILABLE:
                self.student_stats_text.delete("1.0", tk.END)
                self.student_stats_text.insert("1.0", "Student management system not available")
                return

            conn = get_student_db_connection()
            if not conn:  # Check if connection is None
                self.student_stats_text.delete("1.0", tk.END)
                self.student_stats_text.insert("1.0", "Unable to connect to student database")
                return

            cursor = conn.cursor()

            # Get basic stats with proper error handling
            try:
                cursor.execute('SELECT COUNT(*) FROM students')
                result = cursor.fetchone()
                total_students = result[0] if result else 0
            except Exception:
                total_students = 0

            try:
                cursor.execute('SELECT COUNT(*) FROM students WHERE course = "CS"')
                result = cursor.fetchone()
                cs_students = result[0] if result else 0
            except Exception:
                cs_students = 0

            try:
                cursor.execute('SELECT COUNT(*) FROM students WHERE course = "DS"')
                result = cursor.fetchone()
                ds_students = result[0] if result else 0
            except Exception:
                ds_students = 0

            conn.close()

            stats_text = f"""Student System Integration Status
    {'='*40}

    Connection Status: Active
    Total Students: {total_students}
    CS Students: {cs_students}
    DS Students: {ds_students}

    Recent Student Activities:
    {'='*40}
    """

            # Get recent student-related logs with error handling
            if self.log_manager:
                try:
                    filters = {
                        'module': 'student_management',
                        'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    }
                    recent_logs = self.log_manager.db.search_logs(filters, limit=10)

                    if recent_logs:
                        for log in recent_logs:
                            timestamp = log.get('timestamp', '')[:16]
                            action = log.get('action', '')
                            user = log.get('username', '')
                            stats_text += f"{timestamp} - {user}: {action}\n"
                    else:
                        stats_text += "No recent student activities found\n"
                except Exception as e:
                    stats_text += f"Error loading recent activities: {str(e)}\n"

            self.student_stats_text.delete("1.0", tk.END)
            self.student_stats_text.insert("1.0", stats_text)

        except Exception as e:
            error_text = f"Error loading student stats: {str(e)}"
            if hasattr(self, 'student_stats_text'):
                self.student_stats_text.delete("1.0", tk.END)
                self.student_stats_text.insert("1.0", error_text)
            else:
                print(error_text)

    def view_student_logs(self):
        """View logs related to student activities"""
        if not self.log_manager:
            messagebox.showerror("Error", "Log manager not available")
            return

        # Create filter for student-related activities
        student_filters = {
            'module': 'student_management',
            'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        }

        try:
            results = self.log_manager.db.search_logs(student_filters, limit=500)

            # Create new window to display results
            log_window = tk.Toplevel(self.root)
            log_window.title(_t("log_management.dialogs.student_logs"))
            log_window.geometry("800x600")

            # Create treeview for results
            columns = ("Time", "User", "Action", "Details", "Status")
            tree = ttk.Treeview(log_window, columns=columns, show="headings")

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            # Populate with results
            for log in results:
                timestamp = log.get('timestamp', '')[:19]
                user = log.get('username', '')
                action = log.get('action', '')
                details = log.get('details', '')[:50] + "..." if len(log.get('details', '')) > 50 else log.get('details', '')
                status = log.get('status', '')

                tree.insert("", "end", values=(timestamp, user, action, details, status))

            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Add info label
            info_label = ttk.Label(log_window, text=f"Found {len(results)} student-related log entries")
            info_label.pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load student logs: {str(e)}")
