"""System maintenance and backup"""

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
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.core.sql_safety import validate_table_name
from collections import deque



class MaintenanceManager:
    """System maintenance and backup"""

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

    def _calculate_file_hash(self, file_path):
        """Calculate file hash for integrity checking"""
        try:
            import hashlib

            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)

            return hash_md5.hexdigest()
        except Exception as e:
            print(f"Error calculating file hash: {e}")
            return None

    def system_maintenance(self):
        """System maintenance interface"""
        if not self._check_permission('manage_assignments'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="System Maintenance", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Maintenance options
        maintenance_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Maintenance Options", padding=20)
        maintenance_frame.pack(fill='x', pady=(0, 20))
        
        # Database maintenance
        db_frame = ttk.LabelFrame(maintenance_frame, text="Database Maintenance", padding=10)
        db_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(db_frame, text="Optimize Database", command=self.optimize_database).pack(side='left', padx=(0, 10))
        ttk.Button(db_frame, text="Check Database Integrity", command=self.check_db_integrity).pack(side='left', padx=(0, 10))
        ttk.Button(db_frame, text="View Database Stats", command=self.show_db_stats).pack(side='left')
        
        # File maintenance
        file_frame = ttk.LabelFrame(maintenance_frame, text="File System Maintenance", padding=10)
        file_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(file_frame, text="Clean Temporary Files", command=self.clean_temp_files).pack(side='left', padx=(0, 10))
        ttk.Button(file_frame, text="Verify File Integrity", command=self.verify_file_integrity).pack(side='left', padx=(0, 10))
        ttk.Button(file_frame, text="Archive Old Files", command=self.archive_old_files).pack(side='left')
        
        # System monitoring
        monitor_frame = ttk.LabelFrame(maintenance_frame, text="System Monitoring", padding=10)
        monitor_frame.pack(fill='x')
        
        ttk.Button(monitor_frame, text="View System Logs", command=self.view_system_logs).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_frame, text="Check Disk Usage", command=self.check_disk_usage).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_frame, text="Generate Health Report", command=self.generate_health_report).pack(side='left')
        
        # Status display
        self.maintenance_status_frame = ttk.Frame(self.gui.layout.content_area)
        self.maintenance_status_frame.pack(fill='both', expand=True, pady=(20, 0))
    

    def optimize_database(self):
        """Optimize database performance"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), isolation_level=None)
            cursor = conn.cursor()

            # Run VACUUM outside of a transaction (requires isolation_level=None)
            cursor.execute('VACUUM')

            # Update statistics
            cursor.execute('ANALYZE')

            conn.close()

            self.show_maintenance_status("Database optimization completed successfully", "success")

        except Exception as e:
            self.show_maintenance_status(f"Database optimization failed: {e}", "error")
    

    def check_db_integrity(self):
        """Check database integrity"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('PRAGMA integrity_check')
            result = cursor.fetchone()
            
            conn.close()
            
            if result[0] == 'ok':
                self.show_maintenance_status("Database integrity check passed", "success")
            else:
                self.show_maintenance_status(f"Database integrity issues found: {result[0]}", "error")
                
        except Exception as e:
            self.show_maintenance_status(f"Integrity check failed: {e}", "error")
    

    def show_db_stats(self):
        """Show database statistics"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Get table sizes
            tables = ['assignments', 'assignment_submissions', 'students', 'users', 'modules']
            stats = []
            
            for table in tables:
                safe_table = validate_table_name(table)
                cursor.execute('SELECT COUNT(*) FROM [' + safe_table + ']')
                count = cursor.fetchone()[0]
                stats.append(f"{table}: {count} records")
            
            # Get database size
            import os
            db_size = os.path.getsize(str(DEFAULT_DB_PATH))
            stats.append(f"Database size: {db_size / (1024*1024):.2f} MB")
            
            conn.close()
            
            stats_text = "\n".join(stats)
            self.show_maintenance_status(f"Database Statistics:\n{stats_text}", "info")
            
        except Exception as e:
            self.show_maintenance_status(f"Failed to get database stats: {e}", "error")
    

    def clean_temp_files(self):
        """Clean temporary files"""
        try:
            import tempfile
            import glob
            
            temp_dir = tempfile.gettempdir()
            temp_files = glob.glob(os.path.join(temp_dir, "assignment_*"))
            
            deleted_count = 0
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    deleted_count += 1
                except (OSError, IOError):
                    pass
            
            self.show_maintenance_status(f"Cleaned {deleted_count} temporary files", "success")
            
        except Exception as e:
            self.show_maintenance_status(f"Failed to clean temp files: {e}", "error")
    

    def verify_file_integrity(self):
        """Verify file integrity"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute(
                "SELECT file_path, file_hash FROM assignment_submissions "
                "WHERE file_path IS NOT NULL AND file_path != ''"
            )
            files = cursor.fetchall()
            conn.close()

            missing_files = 0
            corrupted_files = 0
            checked_files = 0

            for file_path, stored_hash in files:
                if not file_path or not isinstance(file_path, str) or not file_path.strip():
                    continue

                checked_files += 1
                if not os.path.exists(file_path):
                    missing_files += 1
                elif stored_hash:
                    current_hash = self._calculate_file_hash(file_path)
                    if current_hash and current_hash != stored_hash:
                        corrupted_files += 1

            status_msg = f"File integrity check: {checked_files} files checked, {missing_files} missing, {corrupted_files} corrupted"
            msg_type = "success" if (missing_files == 0 and corrupted_files == 0) else "warning"
            self.show_maintenance_status(status_msg, msg_type)

        except Exception as e:
            self.show_maintenance_status(f"File integrity check failed: {e}", "error")
    

    def archive_old_files(self):
        """Archive old files"""
        try:
            cutoff_date = datetime.now() - timedelta(days=365)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')

            # Use proper path from shared constants with fallback
            submission_dir = getattr(self.assignment_system, 'submission_dir', None)
            if submission_dir is None:
                base_dir = paths.SUBMISSIONS_DIR
            else:
                base_dir = Path(submission_dir).resolve()

            submitted_dir = base_dir / 'submitted'
            archive_dir = base_dir / 'archive'
            archive_dir.mkdir(parents=True, exist_ok=True)
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT id, file_path
                    FROM assignment_submissions
                    WHERE submission_date < ? AND file_path IS NOT NULL AND file_path != ''
                    ''',
                    (cutoff_str,)
                )
                rows = cursor.fetchall()

                archived_count = 0
                for submission_id, file_path in rows:
                    # Skip if file_path is None or empty
                    if not file_path or not isinstance(file_path, str) or not file_path.strip():
                        continue

                    src = Path(file_path)
                    if not src.exists():
                        continue

                    try:
                        relative_path = src.relative_to(submitted_dir)
                    except ValueError:
                        relative_path = src.name

                    dest = archive_dir / str(relative_path)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dest))

                    cursor.execute(
                        '''
                        UPDATE assignment_submissions
                        SET file_path = ?, status = CASE WHEN status = 'graded' THEN status ELSE 'archived' END
                        WHERE id = ?
                        ''', (str(dest), submission_id)
                    )
                    archived_count += 1

                conn.commit()
            finally:
                conn.close()
    
            self.show_maintenance_status(f"Archived {archived_count} submission file(s) older than one year.", "success")
        except Exception as e:
            self.show_maintenance_status(f"File archiving failed: {e}", "error")
    

    def view_system_logs(self):
        """View system logs"""
        log_window = tk.Toplevel(self.root)
        log_window.title("System Logs")
        log_window.geometry("800x600")
    
        controls_frame = ttk.Frame(log_window, padding=10)
        controls_frame.pack(fill='x')
    
        ttk.Label(controls_frame, text="Select log file:").pack(side='left')
    
        self.log_file_var = tk.StringVar()
        log_combo = ttk.Combobox(controls_frame, textvariable=self.log_file_var, width=40, state='readonly')
        log_combo.pack(side='left', padx=(10, 0))
    
        ttk.Button(controls_frame, text="Refresh", command=lambda: self._populate_log_files(log_combo)).pack(side='left', padx=10)
        ttk.Button(controls_frame, text="Open", command=lambda: self._load_log_contents(log_text)).pack(side='left')
    
        log_text = scrolledtext.ScrolledText(log_window, wrap=tk.WORD)
        log_text.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        log_text.config(state='disabled')
    
        self._populate_log_files(log_combo)
        if self.log_file_var.get():
            self._load_log_contents(log_text)
    

    def _populate_log_files(self, combo):
        log_dir = Path(paths.LOG_DIR)
        if not log_dir.exists():
            combo['values'] = []
            self.log_file_var.set('')
            return
    
        log_files = sorted([p.name for p in log_dir.glob('*.log')])
        combo['values'] = log_files
        if log_files and not self.log_file_var.get():
            self.log_file_var.set(log_files[0])
    

    def _load_log_contents(self, text_widget):
        log_dir = Path(paths.LOG_DIR)
        log_name = self.log_file_var.get()
        text_widget.config(state='normal')
        text_widget.delete('1.0', tk.END)
    
        if not log_name:
            text_widget.insert(tk.END, "No log file selected.")
            text_widget.config(state='disabled')
            return
    
        log_path = log_dir / log_name
        if not log_path.exists():
            text_widget.insert(tk.END, f"Log file '{log_name}' not found.")
            text_widget.config(state='disabled')
            return
    
        try:
            with log_path.open('r', encoding='utf-8', errors='ignore') as handle:
                last_lines = deque(handle, maxlen=500)
            for line in last_lines:
                text_widget.insert(tk.END, line.rstrip() + '\n')
            text_widget.config(state='disabled')
        except Exception as exc:
            text_widget.insert(tk.END, f"Failed to read log file: {exc}")
            text_widget.config(state='disabled')
    

    def check_disk_usage(self):
        """Check disk usage"""
        try:
            import shutil
    
            # Use the directory containing the database as the base path
            base_dir = os.path.dirname(DEFAULT_DB_PATH)
            total, used, free = shutil.disk_usage(base_dir)
            
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            used_percent = (used / total) * 100
            
            usage_msg = f"Disk Usage:\nTotal: {total_gb:.2f} GB\nUsed: {used_gb:.2f} GB ({used_percent:.1f}%)\nFree: {free_gb:.2f} GB"
            
            msg_type = "warning" if used_percent > 90 else "success"
            self.show_maintenance_status(usage_msg, msg_type)
            
        except Exception as e:
            self.show_maintenance_status(f"Failed to check disk usage: {e}", "error")
    

    def generate_health_report(self):
        """Generate comprehensive system health report and email to admin"""
        try:
            # Collect various system metrics
            health_items = []
            health_details = []
            report_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            health_items.append(f"=== ASSIGNMENT SYSTEM HEALTH REPORT ===")
            health_items.append(f"Generated: {report_timestamp}\n")

            # Check database connectivity and stats
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                conn.execute('SELECT 1')
                health_items.append("✓ Database: OK")

                # Get database statistics
                cursor.execute('SELECT COUNT(*) FROM assignments WHERE is_active = 1')
                active_assignments = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM assignment_submissions')
                total_submissions = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(DISTINCT student_id) FROM assignment_submissions')
                active_students = cursor.fetchone()[0]

                health_details.append(f"  - Active Assignments: {active_assignments}")
                health_details.append(f"  - Total Submissions: {total_submissions}")
                health_details.append(f"  - Active Students: {active_students}")

                # Database size
                db_size_mb = os.path.getsize(str(DEFAULT_DB_PATH)) / (1024 * 1024)
                health_details.append(f"  - Database Size: {db_size_mb:.2f} MB")

                conn.close()
            except Exception as e:
                health_items.append(f"✗ Database: ERROR - {str(e)}")

            if health_details:
                health_items.extend(health_details)
                health_details = []

            # Check file system
            data_dir = os.path.dirname(DEFAULT_DB_PATH)
            if os.path.exists(data_dir):
                health_items.append("\n✓ File System: OK")

                # Check submission directories
                submission_dir = paths.SUBMISSIONS_DIR
                if submission_dir.exists():
                    health_details.append(f"  - Submission Directory: {submission_dir}")
                    try:
                        # Count files
                        file_count = sum(1 for _ in submission_dir.rglob('*') if _.is_file())
                        health_details.append(f"  - Total Files: {file_count}")
                    except (OSError, PermissionError):
                        pass
            else:
                health_items.append("\n✗ File System: ERROR - Data directory not found")

            if health_details:
                health_items.extend(health_details)
                health_details = []

            # Check permissions
            if os.access(str(DEFAULT_DB_PATH), os.R_OK | os.W_OK):
                health_items.append("\n✓ Permissions: OK")
            else:
                health_items.append("\n✗ Permissions: ERROR - Insufficient database permissions")

            # Check disk usage
            try:
                import shutil
                total, used, free = shutil.disk_usage(data_dir)
                used_percent = (used / total) * 100
                free_gb = free / (1024**3)

                if used_percent > 90:
                    health_items.append(f"\n⚠ Disk Usage: WARNING - {used_percent:.1f}% used ({free_gb:.2f} GB free)")
                else:
                    health_items.append(f"\n✓ Disk Usage: OK - {used_percent:.1f}% used ({free_gb:.2f} GB free)")
            except (OSError, AttributeError):
                health_items.append("\n⚠ Disk Usage: Unable to check")

            health_report = "\n".join(health_items)

            # Display report
            self.show_maintenance_status(health_report, "info")

            # Send email to admin
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Get admin email
                cursor.execute('''
                    SELECT email FROM users WHERE role = 'admin' LIMIT 1
                ''')
                admin_result = cursor.fetchone()
                conn.close()

                if admin_result:
                    admin_email = admin_result[0]
                    from education_system.university_system.infrastructure.email.email_service import send_email

                    email_body = health_report.replace("✓", "[OK]").replace("✗", "[ERROR]").replace("⚠", "[WARNING]")

                    send_email(
                        recipient_email=admin_email,
                        subject=f"Assignment System Health Report - {datetime.now().strftime('%Y-%m-%d')}",
                        body=email_body
                    )

                    messagebox.showinfo("Success", f"Health report generated and emailed to admin ({admin_email})")
                else:
                    messagebox.showwarning("Warning", "Health report generated but no admin email found")
            except Exception as email_error:
                messagebox.showwarning("Warning", f"Health report generated but email failed: {email_error}")

        except Exception as e:
            self.show_maintenance_status(f"Failed to generate health report: {e}", "error")
    

    def show_maintenance_status(self, message, msg_type):
        """Show maintenance status message"""
        # Clear previous status
        for widget in self.maintenance_status_frame.winfo_children():
            widget.destroy()
        
        status_frame = ttk.LabelFrame(self.maintenance_status_frame, text="Status", padding=10)
        status_frame.pack(fill='both', expand=True)
        
        if msg_type == "success":
            style = 'Success.TLabel'
        elif msg_type == "error":
            style = 'Error.TLabel'
        else:
            style = 'Warning.TLabel'
        
        status_label = ttk.Label(status_frame, text=message, style=style, justify='left')
        status_label.pack(anchor='w')
    

    def cleanup_old_data(self):
        """Enhanced cleanup with GUI progress"""
        if not self._check_permission('manage_assignments'):
            return
        
        # Create progress window
        cleanup_window = tk.Toplevel(self.root)
        cleanup_window.title("Data Cleanup")
        cleanup_window.geometry("400x300")
        cleanup_window.transient(self.root)
        
        ttk.Label(cleanup_window, text="Data Cleanup Progress", font=('Arial', 14, 'bold')).pack(pady=10)
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(cleanup_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill='x', padx=20, pady=10)
        
        status_label = ttk.Label(cleanup_window, text="Starting cleanup...")
        status_label.pack(pady=10)
        
        results_text = scrolledtext.ScrolledText(cleanup_window, height=8, width=50)
        results_text.pack(fill='both', expand=True, padx=20, pady=10)
        
        def run_cleanup():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
    
                # Clean old notifications
                progress_var.set(20)
                status_label.config(text="Cleaning old notifications...")
                cleanup_window.update()
    
                cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
                try:
                    cursor.execute('PRAGMA table_info(notifications)')
                    notif_columns = {col[1] for col in cursor.fetchall()}
                    if 'created_at' in notif_columns:
                        cursor.execute('DELETE FROM notifications WHERE created_at < ? AND is_read = 1', (cutoff_date,))
                        deleted_notifications = cursor.rowcount
                        results_text.insert(tk.END, f"Deleted {deleted_notifications} old notifications\n")
                    else:
                        results_text.insert(tk.END, "Skipped notifications cleanup: missing created_at column\n")
                        deleted_notifications = 0
                except sqlite3.OperationalError as e:
                    results_text.insert(tk.END, f"Skipped notifications cleanup: {e}\n")
                    deleted_notifications = 0
    
                # Clean old analytics cache
                progress_var.set(40)
                status_label.config(text="Cleaning analytics cache...")
                cleanup_window.update()
    
                cache_cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                try:
                    cursor.execute('DELETE FROM analytics_cache WHERE expires_at < ?', (cache_cutoff,))
                    deleted_cache = cursor.rowcount
                    results_text.insert(tk.END, f"Deleted {deleted_cache} cache entries\n")
                except sqlite3.OperationalError as e:
                    results_text.insert(tk.END, f"Skipped analytics cache cleanup: {e}\n")
                    deleted_cache = 0
    
                # Clean old audit logs
                progress_var.set(60)
                status_label.config(text="Cleaning old audit logs...")
                cleanup_window.update()
    
                audit_cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')
                try:
                    cursor.execute('DELETE FROM audit_log WHERE timestamp < ?', (audit_cutoff,))
                    deleted_audit = cursor.rowcount
                    results_text.insert(tk.END, f"Deleted {deleted_audit} old audit logs\n")
                except sqlite3.OperationalError as e:
                    results_text.insert(tk.END, f"Skipped audit log cleanup: {e}\n")
                    deleted_audit = 0
                
                # Clean temporary files
                progress_var.set(80)
                status_label.config(text="Cleaning temporary files...")
                cleanup_window.update()

                temp_count = 0
                # Use proper path from shared constants with fallback
                submission_dir = getattr(self.assignment_system, 'submission_dir', None)
                if submission_dir is None:
                    temp_dir = str(paths.DATA_DIR / 'temp' / 'assignments')
                else:
                    temp_dir = os.path.join(submission_dir, 'temp')

                if os.path.exists(temp_dir):
                    for file in os.listdir(temp_dir):
                        try:
                            os.remove(os.path.join(temp_dir, file))
                            temp_count += 1
                        except (OSError, IOError):
                            pass

                results_text.insert(tk.END, f"Deleted {temp_count} temporary files\n")
                
                # Optimize database
                progress_var.set(90)
                status_label.config(text="Optimizing database...")
                cleanup_window.update()
                
                conn.commit()
                conn.close()
                # VACUUM must run outside a transaction
                vacuum_conn = sqlite3.connect(str(DEFAULT_DB_PATH), isolation_level=None)
                vacuum_conn.execute('VACUUM')
                vacuum_conn.close()
                results_text.insert(tk.END, "Database optimized\n")
                
                progress_var.set(100)
                status_label.config(text="Cleanup completed!")
                results_text.insert(tk.END, "\nCleanup completed successfully!")
                
            except Exception as e:
                results_text.insert(tk.END, f"\nError during cleanup: {e}")
                status_label.config(text="Cleanup failed")
        
        # Run cleanup in thread to prevent GUI freezing
        import threading
        cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
        cleanup_thread.start()
        
        ttk.Button(cleanup_window, text="Close", command=cleanup_window.destroy).pack(pady=10)
    
    # MESSAGING SYSTEM METHODS

    def show_system_backup(self):
        """Show system backup and recovery interface"""
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="System Backup & Recovery", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Backup section
        backup_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Create Backup", padding=20)
        backup_frame.pack(fill='x', pady=(0, 10))
        
        backup_options = ttk.Frame(backup_frame)
        backup_options.pack(fill='x')
        
        self.backup_type_var = tk.StringVar(value="full")
        ttk.Radiobutton(backup_options, text="Full Backup (Database + Files)", 
                       variable=self.backup_type_var, value="full").pack(anchor='w')
        ttk.Radiobutton(backup_options, text="Database Only", 
                       variable=self.backup_type_var, value="database").pack(anchor='w')
        ttk.Radiobutton(backup_options, text="Files Only", 
                       variable=self.backup_type_var, value="files").pack(anchor='w')
        
        ttk.Button(backup_frame, text="Create Backup Now", 
                  command=self.create_system_backup).pack(pady=10)
        
        # Backup history section
        history_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Backup History", padding=10)
        history_frame.pack(fill='both', expand=True)
        
        # Backup history tree
        columns = ('Date', 'Type', 'Size', 'Status', 'Location')
        backup_tree = ttk.Treeview(history_frame, columns=columns, show='headings')
        
        for col in columns:
            backup_tree.heading(col, text=col)
            backup_tree.column(col, width=120)
        
        backup_tree.pack(fill='both', expand=True)
        
        ttk.Label(history_frame, text="No backup history recorded yet. Create a backup to populate this list.").pack(pady=10)
    

    def create_system_backup(self):
        """Create system backup with progress"""
        backup_type = self.backup_type_var.get()
    
        # Create progress dialog
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Creating Backup")
        progress_window.geometry("500x200")
        progress_window.transient(self.root)
    
        ttk.Label(progress_window, text=f"Creating {backup_type} backup...").pack(pady=10)
    
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill='x', padx=20, pady=10)
    
        status_label = ttk.Label(progress_window, text="Initializing...")
        status_label.pack(pady=5)

        # Use canonical backup directories for organised storage
        db_backup_dir = str(paths.BACKUP_DATABASE_DIR)
        files_backup_dir = str(paths.BACKUP_FILES_DIR)
        os.makedirs(db_backup_dir, exist_ok=True)
        os.makedirs(files_backup_dir, exist_ok=True)
    
        # Generate backup filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
        def perform_backup():
            try:
                progress_var.set(10)
                status_label.config(text="Preparing backup...")
                progress_window.update()
    
                if backup_type in ['full', 'database']:
                    progress_var.set(30)
                    status_label.config(text="Backing up database...")
                    progress_window.update()
    
                    # Create database backup
                    backup_file = os.path.join(db_backup_dir, f"database_backup_{timestamp}.db")
                    import shutil
                    shutil.copy2(str(DEFAULT_DB_PATH), backup_file)
    
                    progress_var.set(60)
                    status_label.config(text="Database backup created...")
                    progress_window.update()
    
                if backup_type in ['full', 'files']:
                    progress_var.set(70)
                    status_label.config(text="Backing up files...")
                    progress_window.update()
    
                    # Create files backup (submission files, etc.)
                    data_dir = os.path.dirname(DEFAULT_DB_PATH)
                    files_backup = os.path.join(files_backup_dir, f"files_backup_{timestamp}.zip")
    
                    import zipfile
                    with zipfile.ZipFile(files_backup, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, dirs, files in os.walk(data_dir):
                            # Skip the backups directory to avoid recursion
                            if 'backups' in root:
                                continue
                            for file in files:
                                if file.endswith('.db') and backup_type == 'files':
                                    continue  # Skip database files if only backing up files
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, data_dir)
                                zipf.write(file_path, arcname)
    
                    progress_var.set(90)
                    status_label.config(text="Files backup created...")
                    progress_window.update()
    
                progress_var.set(100)
                status_label.config(text="Backup completed successfully!")
                progress_window.update()
    
                # Show success message with backup location
                backup_location = str(paths.BACKUP_DIR)
                self.root.after(1000, lambda: [
                    progress_window.destroy(),
                    messagebox.showinfo("Backup Complete",
                                      f"{backup_type.title()} backup created successfully!\n"
                                      f"Location: {backup_location}\n"
                                      f"Timestamp: {timestamp}")
                ])
    
            except Exception as e:
                progress_var.set(0)
                status_label.config(text="Backup failed!")
                progress_window.update()
                self.root.after(1000, lambda: [
                    progress_window.destroy(),
                    messagebox.showerror("Backup Error", f"Failed to create backup: {str(e)}")
                ])
    
        # Start backup in background
        progress_window.after(100, perform_backup)
    

    def backup_system_data(self, *args, **kwargs):
        """Launch the system backup interface from CLI integrations."""
        self._launch_gui_feature(self.show_system_backup, "system backup")
    
    
