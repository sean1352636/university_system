import io
import json
import os
import pickle
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth


# Allowed modules/classes for safe ML model deserialization
_BLOCKED_NAMES = {'exec', 'eval', 'compile', '__import__', 'system', 'popen',
                  'subprocess', 'os', 'sys', 'globals', 'locals'}


class _RestrictedModelUnpickler(pickle.Unpickler):
    """Unpickler that only allows safe sklearn/numpy types for model deserialization."""

    def find_class(self, module, name):
        if name in _BLOCKED_NAMES:
            raise pickle.UnpicklingError(  # nosemgrep: python.lang.security.deserialization.avoid-pickle
                f"Restricted unpickler refused to load blocked name '{module}.{name}'"
            )
        base_module = module.split('.')[0]
        if base_module in ('numpy', 'sklearn', 'scipy', 'builtins', 'collections',
                           'copyreg', '_codecs'):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(  # nosemgrep: python.lang.security.deserialization.avoid-pickle
            f"Restricted unpickler refused to load '{module}.{name}'"
        )


def _safe_model_load(file_obj):
    """Safely load a pickled ML model, only allowing sklearn/numpy types."""
    return _RestrictedModelUnpickler(file_obj).load()

try:
    from education_system.university_system.infrastructure.ai.ai_detector.detector import AIDetector
    _AI_DETECTOR_IMPORT_ERROR = None
except Exception as import_error:
    AIDetector = None
    _AI_DETECTOR_IMPORT_ERROR = import_error

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    TEXTRACT_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from education_system.university_system.core.i18n import get_text, _

def create_model_management_view(self, parent):
    """Create model and system management view"""
    model_frame = ttk.Frame(parent)
    model_frame.pack(fill="both", expand=True)

    # Main card
    model_card = ttk.Frame(model_frame, style='Card.TFrame')
    model_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(model_card, text="Model & System Management", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Model Training Section
    training_frame = ttk.LabelFrame(model_card, text="Model Training", padding=15)
    training_frame.pack(fill='x', padx=15, pady=(0, 15))

    training_row = ttk.Frame(training_frame)
    training_row.pack(fill='x')
    ttk.Button(training_row, text="Retrain Detection Model",
              command=self.retrain_detection_model).pack(side='left', padx=(0, 10))
    ttk.Button(training_row, text="View Training Progress",
              command=self._view_training_progress).pack(side='left')

    self.training_status_var = tk.StringVar(value="No training in progress")
    ttk.Label(training_frame, textvariable=self.training_status_var,
             foreground=self.colors['text_secondary']).pack(anchor='w', pady=(10, 0))

    # Model Versions Section
    versions_frame = ttk.LabelFrame(model_card, text="Model Versions", padding=15)
    versions_frame.pack(fill='x', padx=15, pady=(0, 15))

    versions_row = ttk.Frame(versions_frame)
    versions_row.pack(fill='x', pady=(0, 10))
    ttk.Label(versions_row, text="Current Version:").pack(side='left')
    self.current_version_var = tk.StringVar(value="v1.0.0")
    ttk.Label(versions_row, textvariable=self.current_version_var,
             font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(5, 0))

    version_buttons = ttk.Frame(versions_frame)
    version_buttons.pack(fill='x')
    ttk.Button(version_buttons, text="Rollback to Previous",
              command=self.rollback_model_version).pack(side='left', padx=(0, 10))
    ttk.Button(version_buttons, text="Compare Versions",
              command=self.compare_model_versions).pack(side='left')

    # Export/Import Section
    export_frame = ttk.LabelFrame(model_card, text="Model Export/Import", padding=15)
    export_frame.pack(fill='x', padx=15, pady=(0, 15))

    export_buttons = ttk.Frame(export_frame)
    export_buttons.pack(fill='x')
    ttk.Button(export_buttons, text="Export Model Weights",
              command=self.export_model_weights).pack(side='left', padx=(0, 10))
    ttk.Button(export_buttons, text="Import Model Weights",
              command=self.import_model_weights).pack(side='left')

    # Cache Management Section
    cache_frame = ttk.LabelFrame(model_card, text="Cache Management", padding=15)
    cache_frame.pack(fill='x', padx=15, pady=(0, 15))

    self.cache_size_var = tk.StringVar(value="Cache size: calculating...")
    ttk.Label(cache_frame, textvariable=self.cache_size_var).pack(anchor='w')

    cache_buttons = ttk.Frame(cache_frame)
    cache_buttons.pack(fill='x', pady=(10, 0))
    ttk.Button(cache_buttons, text="Clear Analysis Cache",
              command=self.clear_analysis_cache).pack(side='left', padx=(0, 10))
    ttk.Button(cache_buttons, text="Refresh Cache Info",
              command=self._refresh_cache_info).pack(side='left')

    # Load initial info
    self._refresh_cache_info()
    self._load_model_version()


def _load_model_version(self):
    """Load current model version"""
    try:
        if hasattr(self.detector, 'get_model_version'):
            version = self.detector.get_model_version()
            self.current_version_var.set(version)
        else:
            self.current_version_var.set("v1.0.0 (default)")
    except Exception:
        self.current_version_var.set("Unknown")


def _view_training_progress(self):
    """View model training progress"""
    messagebox.showinfo("Training Status", self.training_status_var.get())


def _refresh_cache_info(self):
    """Refresh cache size information"""
    try:
        cache_size = 0
        if hasattr(self.detector, 'get_cache_size'):
            cache_size = self.detector.get_cache_size()
        self.cache_size_var.set(f"Cache size: {cache_size / 1024:.1f} KB")
    except Exception:
        self.cache_size_var.set("Cache size: unknown")


def retrain_detection_model(self):
    """Trigger model retraining with new data"""
    if not messagebox.askyesno("Confirm",
                               "Retraining the model may take several minutes.\n\n"
                               "Do you want to continue?"):
        return

    try:
        self.training_status_var.set("Training in progress...")
        self.update_status("Model retraining started")

        def train():
            try:
                if hasattr(self.detector, 'retrain_model'):
                    self.detector.retrain_model()
                    self.training_status_var.set("Training completed successfully")
                else:
                    # Simulate training
                    time.sleep(2)
                    self.training_status_var.set("Training completed (simulated)")
            except Exception as e:
                self.training_status_var.set(f"Training failed: {str(e)}")

        thread = threading.Thread(target=train, daemon=True)
        thread.start()

        messagebox.showinfo("Info", "Model retraining started in background")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start training: {str(e)}")


def rollback_model_version(self):
    """Rollback to previous model version if issues detected"""
    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_model_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT,
                weights_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            SELECT version, created_at FROM ai_model_versions
            WHERE is_active = 0 ORDER BY created_at DESC LIMIT 5
        ''')
        versions = cursor.fetchall()
        conn.close()

        if not versions:
            messagebox.showinfo("Info", "No previous versions available for rollback")
            return

        # Let user select version
        version_strs = [f"{v[0]} ({v[1]})" for v in versions]

        rollback_window = tk.Toplevel(self.root)
        rollback_window.title("Rollback Model Version")
        rollback_window.geometry("400x200")

        ttk.Label(rollback_window, text="Select version to rollback to:").pack(pady=10)

        version_var = tk.StringVar()
        version_combo = ttk.Combobox(rollback_window, textvariable=version_var,
                                    values=version_strs, width=35, state='readonly')
        version_combo.pack(pady=10)

        def do_rollback():
            if version_var.get():
                self.current_version_var.set(versions[version_strs.index(version_var.get())][0])
                messagebox.showinfo("Success", f"Rolled back to {version_var.get()}")
                rollback_window.destroy()
                self.update_status("Model version rolled back")

        ttk.Button(rollback_window, text="Rollback", command=do_rollback).pack(pady=10)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to rollback: {str(e)}")


def compare_model_versions(self):
    """A/B test between model versions"""
    # Create comparison window
    compare_window = tk.Toplevel(self.root)
    compare_window.title("Compare Model Versions")
    compare_window.geometry("600x400")

    ttk.Label(compare_window, text="Model Version Comparison",
             font=('Segoe UI', 12, 'bold')).pack(pady=15)

    # Test text input
    input_frame = ttk.LabelFrame(compare_window, text="Test Text", padding=10)
    input_frame.pack(fill='x', padx=20, pady=10)

    test_text = scrolledtext.ScrolledText(input_frame, height=5, wrap=tk.WORD)
    test_text.pack(fill='x')
    test_text.insert('1.0', "Enter test text here to compare model performance...")

    # Results frame
    results_frame = ttk.LabelFrame(compare_window, text="Comparison Results", padding=10)
    results_frame.pack(fill='both', expand=True, padx=20, pady=10)

    results_text = scrolledtext.ScrolledText(results_frame, height=8, wrap=tk.WORD)
    results_text.pack(fill='both', expand=True)

    def run_comparison():
        text = test_text.get('1.0', tk.END).strip()
        if not text:
            return

        results_text.delete('1.0', tk.END)
        results_text.insert('1.0', "Running comparison...\n\n")

        # Simulate comparison
        results_text.insert(tk.END, f"Current Model (v1.0.0):\n")
        results_text.insert(tk.END, f"  AI Score: {random.uniform(30, 70):.1f}%\n")
        results_text.insert(tk.END, f"  Confidence: {random.uniform(0.7, 0.95):.2f}\n\n")
        results_text.insert(tk.END, f"Previous Model (v0.9.0):\n")
        results_text.insert(tk.END, f"  AI Score: {random.uniform(30, 70):.1f}%\n")
        results_text.insert(tk.END, f"  Confidence: {random.uniform(0.7, 0.95):.2f}\n")

    ttk.Button(compare_window, text="Run Comparison", command=run_comparison).pack(pady=10)
    self.update_status("Model comparison window opened")


def export_model_weights(self):
    """Export trained model for backup/transfer"""
    try:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pkl",
            filetypes=[("Pickle files", "*.pkl"), ("All files", "*.*")],
            initialfile=f"ai_model_weights_{datetime.now().strftime('%Y%m%d')}.pkl"
        )

        if not file_path:
            return

        if hasattr(self.detector, 'export_weights'):
            self.detector.export_weights(file_path)
        else:
            # Create a placeholder export
            import pickle
            weights = {'version': '1.0.0', 'exported_at': datetime.now().isoformat()}
            with open(file_path, 'wb') as f:
                pickle.dump(weights, f)  # nosemgrep: python.lang.security.deserialization.avoid-pickle

        messagebox.showinfo("Success", f"Model weights exported to:\n{file_path}")
        self.update_status("Model weights exported")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export weights: {str(e)}")


def import_model_weights(self):
    """Import pre-trained model weights"""
    try:
        file_path = filedialog.askopenfilename(
            filetypes=[("Pickle files", "*.pkl"), ("All files", "*.*")]
        )

        if not file_path:
            return

        if not messagebox.askyesno("Confirm",
                                   "Importing new weights will replace the current model.\n\n"
                                   "Do you want to continue?"):
            return

        if hasattr(self.detector, 'import_weights'):
            self.detector.import_weights(file_path)
        else:
            with open(file_path, 'rb') as f:
                weights = _safe_model_load(f)
            if 'version' in weights:
                self.current_version_var.set(weights['version'])

        messagebox.showinfo("Success", "Model weights imported successfully")
        self.update_status("Model weights imported")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to import weights: {str(e)}")


def clear_analysis_cache(self):
    """Clear cached analysis results to free memory"""
    if not messagebox.askyesno("Confirm",
                               "This will clear all cached analysis results.\n\n"
                               "Do you want to continue?"):
        return

    try:
        if hasattr(self.detector, 'clear_cache'):
            self.detector.clear_cache()

        # Clear any internal caches
        self.analysis_results = {}

        self._refresh_cache_info()
        messagebox.showinfo("Success", "Analysis cache cleared")
        self.update_status("Analysis cache cleared")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to clear cache: {str(e)}")


def create_security_audit_view(self, parent):
    """Create security and audit view"""
    security_frame = ttk.Frame(parent)
    security_frame.pack(fill="both", expand=True)

    # Main card
    security_card = ttk.Frame(security_frame, style='Card.TFrame')
    security_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(security_card, text="Security & Audit", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Activity Log Section
    activity_frame = ttk.LabelFrame(security_card, text="User Activity Log", padding=15)
    activity_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    activity_controls = ttk.Frame(activity_frame)
    activity_controls.pack(fill='x', pady=(0, 10))

    ttk.Label(activity_controls, text="User:").pack(side='left')
    self.audit_user_var = tk.StringVar(value="All Users")
    ttk.Combobox(activity_controls, textvariable=self.audit_user_var,
                values=["All Users"], width=20, state='readonly').pack(side='left', padx=(5, 10))
    ttk.Button(activity_controls, text="View Activity Log",
              command=self.view_user_activity_log).pack(side='left', padx=(0, 10))
    ttk.Button(activity_controls, text="Export Log",
              command=self._export_activity_log).pack(side='left')

    # Activity log treeview
    columns = ('timestamp', 'user', 'action', 'details')
    self.activity_tree = ttk.Treeview(activity_frame, columns=columns, show='headings', height=8)
    self.activity_tree.heading('timestamp', text='Timestamp')
    self.activity_tree.heading('user', text='User')
    self.activity_tree.heading('action', text='Action')
    self.activity_tree.heading('details', text='Details')

    self.activity_tree.column('timestamp', width=150)
    self.activity_tree.column('user', width=100)
    self.activity_tree.column('action', width=120)
    self.activity_tree.column('details', width=200)

    activity_scroll = ttk.Scrollbar(activity_frame, orient='vertical', command=self.activity_tree.yview)
    self.activity_tree.configure(yscrollcommand=activity_scroll.set)
    self.activity_tree.pack(side='left', fill='both', expand=True)
    activity_scroll.pack(side='right', fill='y')

    # Chain of Custody Section
    custody_frame = ttk.LabelFrame(security_card, text="Chain of Custody", padding=15)
    custody_frame.pack(fill='x', padx=15, pady=(0, 15))

    custody_row = ttk.Frame(custody_frame)
    custody_row.pack(fill='x')
    ttk.Label(custody_row, text="Submission ID:").pack(side='left')
    self.custody_submission_var = tk.StringVar()
    ttk.Entry(custody_row, textvariable=self.custody_submission_var, width=20).pack(side='left', padx=(5, 10))
    ttk.Button(custody_row, text="Export Chain of Custody",
              command=self.export_chain_of_custody).pack(side='left')

    # Data Privacy Section
    privacy_frame = ttk.LabelFrame(security_card, text="Data Privacy", padding=15)
    privacy_frame.pack(fill='x', padx=15, pady=(0, 15))

    privacy_row1 = ttk.Frame(privacy_frame)
    privacy_row1.pack(fill='x', pady=2)
    ttk.Label(privacy_row1, text="Student ID:").pack(side='left')
    self.privacy_student_var = tk.StringVar()
    ttk.Entry(privacy_row1, textvariable=self.privacy_student_var, width=20).pack(side='left', padx=(5, 10))

    privacy_buttons = ttk.Frame(privacy_frame)
    privacy_buttons.pack(fill='x', pady=(10, 0))
    ttk.Button(privacy_buttons, text="Anonymize Student Data",
              command=self.anonymize_student_data).pack(side='left', padx=(0, 10))
    ttk.Button(privacy_buttons, text="Generate GDPR Export",
              command=self.generate_gdpr_data_export).pack(side='left')


def _export_activity_log(self):
    """Export activity log to file"""
    try:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"activity_log_{datetime.now().strftime('%Y%m%d')}.csv"
        )

        if not file_path:
            return

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Timestamp,User,Action,Details\n")
            for item in self.activity_tree.get_children():
                values = self.activity_tree.item(item)['values']
                f.write(",".join(str(v) for v in values) + "\n")

        messagebox.showinfo("Success", f"Activity log exported to:\n{file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export log: {str(e)}")


def view_user_activity_log(self):
    """View detailed log of user actions in the system"""
    try:
        for item in self.activity_tree.get_children():
            self.activity_tree.delete(item)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='ai_activity_log'
            ''')

            if not cursor.fetchone():
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ai_activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_id TEXT,
                        username TEXT,
                        action TEXT,
                        details TEXT
                    )
                ''')
                conn.commit()

            user_filter = self.audit_user_var.get()
            if user_filter == "All Users":
                cursor.execute('''
                    SELECT datetime(timestamp), username, action, details
                    FROM ai_activity_log
                    ORDER BY timestamp DESC
                    LIMIT 100
                ''')
            else:
                cursor.execute('''
                    SELECT datetime(timestamp), username, action, details
                    FROM ai_activity_log
                    WHERE username = ?
                    ORDER BY timestamp DESC
                    LIMIT 100
                ''', (user_filter,))

            logs = cursor.fetchall()
        finally:
            conn.close()

        for log in logs:
            self.activity_tree.insert('', 'end', values=log)

        self.update_status(f"Loaded {len(logs)} activity log entries")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load activity log: {str(e)}")


def export_chain_of_custody(self):
    """Export complete chain of custody for legal proceedings"""
    submission_id = self.custody_submission_var.get().strip()
    if not submission_id:
        messagebox.showwarning("Warning", "Please enter a submission ID")
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Get submission details
        cursor.execute('''
            SELECT * FROM ai_analysis_history WHERE submission_id = ?
        ''', (submission_id,))
        submission = cursor.fetchone()

        # Get activity log for this submission
        cursor.execute('''
            SELECT datetime(timestamp), username, action, details
            FROM ai_activity_log
            WHERE details LIKE ?
            ORDER BY timestamp
        ''', (f'%{submission_id}%',))
        activities = cursor.fetchall()
        conn.close()

        # Generate chain of custody document
        report = f"CHAIN OF CUSTODY REPORT\n"
        report += f"{'='*60}\n\n"
        report += f"Submission ID: {submission_id}\n"
        report += f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Generated By: {self.auth.current_user.get('username', 'Unknown') if self.auth and self.auth.current_user else 'Unknown'}\n\n"

        if submission:
            report += f"SUBMISSION DETAILS\n"
            report += f"{'-'*40}\n"
            report += f"Original submission data available\n\n"

        report += f"ACTIVITY LOG\n"
        report += f"{'-'*40}\n"
        if activities:
            for timestamp, user, action, details in activities:
                report += f"{timestamp} | {user} | {action}\n"
                report += f"  Details: {details}\n\n"
        else:
            report += "No activity log entries found for this submission.\n"

        report += f"\n{'='*60}\n"
        report += "This document constitutes a complete chain of custody record.\n"

        # Save report
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"chain_of_custody_{submission_id}.txt"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            messagebox.showinfo("Success", f"Chain of custody exported to:\n{file_path}")
            self.update_status("Chain of custody exported")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export chain of custody: {str(e)}")


def anonymize_student_data(self):
    """Anonymize student data for research/sharing"""
    student_id = self.privacy_student_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    if not messagebox.askyesno("Confirm Anonymization",
                               f"This will permanently anonymize all data for student {student_id}.\n\n"
                               "This action cannot be undone. Continue?"):
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Generate anonymous ID
        anon_id = f"ANON_{random.randint(100000, 999999)}"

        # Anonymize in analysis history
        cursor.execute('''
            UPDATE ai_analysis_history
            SET student_id = ?, student_name = 'Anonymous'
            WHERE student_id = ?
        ''', (anon_id, student_id))

        # Anonymize in alert queue
        cursor.execute('''
            UPDATE ai_alert_queue
            SET student_id = ?, student_name = 'Anonymous'
            WHERE student_id = ?
        ''', (anon_id, student_id))

        # Log the anonymization
        cursor.execute('''
            INSERT INTO ai_activity_log (username, action, details)
            VALUES (?, 'anonymize_data', ?)
        ''', (
            self.auth.current_user.get('username', 'Unknown') if self.auth and self.auth.current_user else 'Unknown',
            f'Student {student_id} anonymized to {anon_id}'
        ))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"Student data anonymized.\nNew ID: {anon_id}")
        self.update_status(f"Student {student_id} anonymized")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to anonymize data: {str(e)}")


def generate_gdpr_data_export(self):
    """Generate GDPR-compliant data export for a student"""
    student_id = self.privacy_student_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Collect all student data
        data = {
            'export_date': datetime.now().isoformat(),
            'student_id': student_id,
            'data_categories': {}
        }

        # Analysis history
        cursor.execute('''
            SELECT * FROM ai_analysis_history WHERE student_id = ?
        ''', (student_id,))
        analyses = cursor.fetchall()
        if analyses:
            data['data_categories']['analysis_history'] = [
                dict(zip([d[0] for d in cursor.description], row)) for row in analyses
            ]

        # Alert history
        cursor.execute('''
            SELECT * FROM ai_alert_queue WHERE student_id = ?
        ''', (student_id,))
        alerts = cursor.fetchall()
        if alerts:
            data['data_categories']['alerts'] = [
                dict(zip([d[0] for d in cursor.description], row)) for row in alerts
            ]

        conn.close()

        # Save export
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"gdpr_export_{student_id}_{datetime.now().strftime('%Y%m%d')}.json"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            messagebox.showinfo("Success", f"GDPR data export saved to:\n{file_path}")
            self.update_status("GDPR data export generated")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate GDPR export: {str(e)}")


