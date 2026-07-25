"""Status bar mixin for LayoutManager."""

import tkinter as tk
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.auth import get_global_auth
from education_system.systems.university.infrastructure.i18n import get_text as _


class StatusBarMixin:
    """Status bar: create, update, time display, system status."""

    def create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = tk.Frame(self.root, bg='#34495e', height=30)
        self.status_bar.pack(side='bottom', fill='x')

        self.status_var = tk.StringVar(value=_("finance_gui.status_bar.ready"))
        self.status_label = tk.Label(self.status_bar, textvariable=self.status_var,
                               bg='#34495e', fg='white', font=('Arial', 10))
        self.status_label.pack(side='left', padx=10, pady=5)

        # Add Status_label property for backward compatibility
        self.Status_label = self.status_label

        # Connection status
        self.connection_label = tk.Label(self.status_bar, text=_("finance_gui.status_bar.connected"),
                                       bg='#34495e', fg='white', font=('Arial', 10))
        self.connection_label.pack(side='right', padx=10, pady=5)

        # Add timestamp
        self.time_var = tk.StringVar()
        time_label = tk.Label(self.status_bar, textvariable=self.time_var,
                             bg='#34495e', fg='white', font=('Arial', 10))
        time_label.pack(side='right', padx=10, pady=5)

        self._time_after_id = None
        self.status_bar.bind("<Destroy>", self._cancel_time_updates)
        self.update_time()

    def _cancel_time_updates(self, _event=None):
        """Stop the recurring after() when the status bar is destroyed.

        Without this the 1-second tick can fire after the Toplevel has
        been torn down and Tk logs `invalid command name ...update_time`.
        """
        if getattr(self, '_time_after_id', None) is not None:
            try:
                self.root.after_cancel(self._time_after_id)
            except Exception:
                pass
            self._time_after_id = None

    def update_status(self, message):
        """Update status bar message"""
        if hasattr(self, 'status_label') and self.status_label:
            try:
                self.status_label.config(text=message)
                self.root.update_idletasks()
            except Exception as e:
                # Status bar unavailable, silently ignore
                print(f"Debug: Status bar update failed: {e}")

    # ==================== ACTION METHODS ====================


    def update_time(self):
        """Update timestamp in status bar"""
        if hasattr(self, 'time_var') and self.time_var:
            try:
                # Check if root window still exists
                if not hasattr(self, 'root') or not self.root.winfo_exists():
                    return

                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.time_var.set(current_time)
                self._time_after_id = self.root.after(1000, self.update_time)
            except Exception:
                # Time display unavailable or window destroyed, silently ignore
                pass


    def update_system_status(self):
        """Update system status display"""
        try:
            status_info = f"System Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_info += "=" * 60 + "\n\n"

            # Database connection status
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM students')
                student_count = cursor.fetchone()[0]
                status_info += "\u2713 Database Connection: OK\n"
                status_info += f"  - Students in system: {student_count}\n"
                conn.close()
            except Exception as e:
                status_info += f"\u2717 Database Connection: FAILED ({e})\n"

            # Check tables
            essential_tables = [
                'students', 'student_fees', 'payments', 'payment_allocations',
                'scholarships', 'student_scholarships', 'payment_plan_templates',
                'student_payment_plans', 'late_fees', 'exchange_rates'
            ]

            try:
                conn = get_connection()
                cursor = conn.cursor()
                status_info += "\nTable Status:\n"

                for table in essential_tables:
                    try:
                        from education_system.systems.university.infrastructure.sql_safety import validate_table_name
                        validated_table = validate_table_name(table, conn=conn)
                        cursor.execute("SELECT COUNT(*) FROM [" + validated_table + "]")
                        count = cursor.fetchone()[0]
                        status_info += f"  \u2713 {table}: {count} records\n"
                    except Exception:
                        status_info += f"  \u2717 {table}: Missing or corrupted\n"

                conn.close()

            except Exception as e:
                status_info += f"\u2717 Table Check Failed: {e}\n"

            # System performance
            auth = get_global_auth()
            status_info += "\nSystem Performance:\n"
            status_info += "  - GUI Framework: Tkinter\n"
            status_info += "  - Database: SQLite\n"
            status_info += f"  - Current User: {auth.current_user.get('username', 'Unknown')}\n"

            # Recent activity
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT COUNT(*) FROM payments
                WHERE date(created_at) = date('now')
                ''')

                today_payments = cursor.fetchone()[0]

                cursor.execute('''
                SELECT COUNT(*) FROM student_fees
                WHERE date(created_at) = date('now')
                ''')
                today_fees = cursor.fetchone()[0]

                status_info += "\nToday's Activity:\n"
                status_info += f"  - Payments recorded: {today_payments}\n"
                status_info += f"  - Fees assigned: {today_fees}\n"

                conn.close()

            except Exception as e:
                status_info += f"\nActivity Check Failed: {e}\n"

            # Update display
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', status_info)

        except Exception as e:
            error_msg = f"Failed to update system status: {e}"
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', error_msg)
