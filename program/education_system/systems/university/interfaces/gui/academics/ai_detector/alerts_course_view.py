import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

try:
    from education_system.systems.university.infrastructure.ai.ai_detector.detector import AIDetector
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

from education_system.systems.university.infrastructure.i18n import get_text, _

def create_alerts_notifications_view(self, parent):
    """Create alerts and notifications management view"""
    alerts_frame = ttk.Frame(parent)
    alerts_frame.pack(fill="both", expand=True)

    # Main card
    alerts_card = ttk.Frame(alerts_frame, style='Card.TFrame')
    alerts_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(alerts_card, text="Alerts & Notifications", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Alert Thresholds Section
    thresholds_frame = ttk.LabelFrame(alerts_card, text="Alert Thresholds", padding=15)
    thresholds_frame.pack(fill='x', padx=15, pady=(0, 15))

    # Low Risk Threshold
    low_frame = ttk.Frame(thresholds_frame)
    low_frame.pack(fill='x', pady=2)
    ttk.Label(low_frame, text="Low Risk Threshold (%):").pack(side='left')
    self.low_threshold_var = tk.StringVar(value="30")
    ttk.Entry(low_frame, textvariable=self.low_threshold_var, width=10).pack(side='left', padx=(5, 0))

    # Medium Risk Threshold
    med_frame = ttk.Frame(thresholds_frame)
    med_frame.pack(fill='x', pady=2)
    ttk.Label(med_frame, text="Medium Risk Threshold (%):").pack(side='left')
    self.med_threshold_var = tk.StringVar(value="60")
    ttk.Entry(med_frame, textvariable=self.med_threshold_var, width=10).pack(side='left', padx=(5, 0))

    # High Risk Threshold
    high_frame = ttk.Frame(thresholds_frame)
    high_frame.pack(fill='x', pady=2)
    ttk.Label(high_frame, text="High Risk Threshold (%):").pack(side='left')
    self.high_threshold_var = tk.StringVar(value="80")
    ttk.Entry(high_frame, textvariable=self.high_threshold_var, width=10).pack(side='left', padx=(5, 0))

    ttk.Button(thresholds_frame, text="Save Thresholds",
              command=self.configure_alert_thresholds).pack(anchor='e', pady=(10, 0))

    # Email Alerts Section
    email_frame = ttk.LabelFrame(alerts_card, text="Email Alerts", padding=15)
    email_frame.pack(fill='x', padx=15, pady=(0, 15))

    self.email_alerts_enabled = tk.BooleanVar(value=False)
    ttk.Checkbutton(email_frame, text="Enable automatic email alerts for high-risk submissions",
                   variable=self.email_alerts_enabled).pack(anchor='w')

    email_input_frame = ttk.Frame(email_frame)
    email_input_frame.pack(fill='x', pady=(10, 0))
    ttk.Label(email_input_frame, text="Notification Email:").pack(side='left')
    self.alert_email_var = tk.StringVar()
    ttk.Entry(email_input_frame, textvariable=self.alert_email_var, width=30).pack(side='left', padx=(5, 10))
    ttk.Button(email_input_frame, text="Setup Email Alerts",
              command=self.setup_email_alerts).pack(side='left')

    # Alert Queue Section
    queue_frame = ttk.LabelFrame(alerts_card, text="Alert Queue", padding=15)
    queue_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    # Queue controls
    queue_controls = ttk.Frame(queue_frame)
    queue_controls.pack(fill='x', pady=(0, 10))
    ttk.Button(queue_controls, text="Refresh Queue",
              command=self.view_alert_queue).pack(side='left', padx=(0, 10))
    ttk.Button(queue_controls, text="Dismiss Selected",
              command=self.dismiss_alert).pack(side='left', padx=(0, 10))
    ttk.Button(queue_controls, text="Escalate to Dean",
              command=self.escalate_to_dean).pack(side='left')

    # Alert queue treeview
    columns = ('id', 'student', 'assignment', 'risk_level', 'score', 'date')
    self.alert_tree = ttk.Treeview(queue_frame, columns=columns, show='headings', height=8)
    self.alert_tree.heading('id', text='ID')
    self.alert_tree.heading('student', text='Student')
    self.alert_tree.heading('assignment', text='Assignment')
    self.alert_tree.heading('risk_level', text='Risk Level')
    self.alert_tree.heading('score', text='AI Score')
    self.alert_tree.heading('date', text='Date')

    self.alert_tree.column('id', width=50)
    self.alert_tree.column('student', width=120)
    self.alert_tree.column('assignment', width=150)
    self.alert_tree.column('risk_level', width=80)
    self.alert_tree.column('score', width=80)
    self.alert_tree.column('date', width=100)

    alert_scroll = ttk.Scrollbar(queue_frame, orient='vertical', command=self.alert_tree.yview)
    self.alert_tree.configure(yscrollcommand=alert_scroll.set)
    self.alert_tree.pack(side='left', fill='both', expand=True)
    alert_scroll.pack(side='right', fill='y')


def configure_alert_thresholds(self):
    """Set custom alert thresholds for different risk levels"""
    try:
        low = int(self.low_threshold_var.get())
        med = int(self.med_threshold_var.get())
        high = int(self.high_threshold_var.get())

        if not (0 <= low < med < high <= 100):
            messagebox.showerror("Error", "Thresholds must be in order: Low < Medium < High (0-100)")
            return

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_alert_settings (
                    id INTEGER PRIMARY KEY,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            for name, value in [('low_threshold', low), ('med_threshold', med), ('high_threshold', high)]:
                cursor.execute('''
                    INSERT OR REPLACE INTO ai_alert_settings (setting_name, setting_value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (name, str(value)))

            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo("Success", f"Alert thresholds updated:\nLow: {low}%\nMedium: {med}%\nHigh: {high}%")
        self.update_status("Alert thresholds configured")
    except ValueError:
        messagebox.showerror("Error", "Please enter valid numbers for thresholds")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to configure thresholds: {str(e)}")


def setup_email_alerts(self):
    """Configure automatic email alerts for high-risk submissions"""
    try:
        email = self.alert_email_var.get().strip()
        enabled = self.email_alerts_enabled.get()

        if enabled and not email:
            messagebox.showerror("Error", "Please enter a notification email address")
            return

        if enabled and '@' not in email:
            messagebox.showerror("Error", "Please enter a valid email address")
            return

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_alert_settings (
                    id INTEGER PRIMARY KEY,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                INSERT OR REPLACE INTO ai_alert_settings (setting_name, setting_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', ('email_alerts_enabled', '1' if enabled else '0'))

            cursor.execute('''
                INSERT OR REPLACE INTO ai_alert_settings (setting_name, setting_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', ('notification_email', email))

            conn.commit()
        finally:
            conn.close()

        status = "enabled" if enabled else "disabled"
        messagebox.showinfo("Success", f"Email alerts {status}" + (f" for {email}" if enabled else ""))
        self.update_status(f"Email alerts {status}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to setup email alerts: {str(e)}")


def view_alert_queue(self):
    """View pending alerts awaiting instructor review"""
    try:
        # Clear existing items
        for item in self.alert_tree.get_children():
            self.alert_tree.delete(item)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='ai_alert_queue'
            ''')

            if not cursor.fetchone():
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ai_alert_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        student_name TEXT,
                        assignment_name TEXT,
                        risk_level TEXT,
                        ai_score REAL,
                        submission_id TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        dismissed_at TIMESTAMP,
                        dismiss_reason TEXT
                    )
                ''')
                conn.commit()

            cursor.execute('''
                SELECT id, student_name, assignment_name, risk_level, ai_score,
                       date(created_at) as date
                FROM ai_alert_queue
                WHERE status = 'pending'
                ORDER BY ai_score DESC, created_at DESC
            ''')

            alerts = cursor.fetchall()
        finally:
            conn.close()

        for alert in alerts:
            self.alert_tree.insert('', 'end', values=alert)

        self.update_status(f"Loaded {len(alerts)} pending alerts")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load alert queue: {str(e)}")


def dismiss_alert(self):
    """Dismiss false positive alerts with reason logging"""
    selected = self.alert_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select an alert to dismiss")
        return

    # Ask for dismiss reason
    reason = simpledialog.askstring("Dismiss Alert",
                                    "Enter reason for dismissing this alert:",
                                    parent=self.root)
    if not reason:
        return

    try:
        alert_id = self.alert_tree.item(selected[0])['values'][0]

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE ai_alert_queue
            SET status = 'dismissed',
                dismissed_at = CURRENT_TIMESTAMP,
                dismiss_reason = ?
            WHERE id = ?
        ''', (reason, alert_id))

        conn.commit()
        conn.close()

        self.alert_tree.delete(selected[0])
        messagebox.showinfo("Success", "Alert dismissed successfully")
        self.update_status("Alert dismissed")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to dismiss alert: {str(e)}")


def escalate_to_dean(self):
    """Escalate serious cases directly to academic dean's queue"""
    selected = self.alert_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select an alert to escalate")
        return

    if not messagebox.askyesno("Confirm Escalation",
                               "Are you sure you want to escalate this case to the Academic Dean?\n\n"
                               "This action will flag the case for immediate review by university administration."):
        return

    try:
        alert_values = self.alert_tree.item(selected[0])['values']
        alert_id = alert_values[0]
        student_name = alert_values[1]
        assignment = alert_values[2]

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            # Create escalation table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_dean_escalations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id INTEGER,
                    student_name TEXT,
                    assignment_name TEXT,
                    escalated_by TEXT,
                    escalation_notes TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Get current user
            escalated_by = "Unknown"
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                escalated_by = self.auth.current_user.get('username', 'Unknown')

            cursor.execute('''
                INSERT INTO ai_dean_escalations (alert_id, student_name, assignment_name, escalated_by)
                VALUES (?, ?, ?, ?)
            ''', (alert_id, student_name, assignment, escalated_by))

            # Update alert status
            cursor.execute('''
                UPDATE ai_alert_queue SET status = 'escalated' WHERE id = ?
            ''', (alert_id,))

            conn.commit()
        finally:
            conn.close()

        self.alert_tree.delete(selected[0])
        messagebox.showinfo("Success",
                          f"Case escalated to Academic Dean's review queue.\n\n"
                          f"Student: {student_name}\nAssignment: {assignment}")
        self.update_status("Case escalated to dean")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to escalate case: {str(e)}")


def create_course_management_view(self, parent):
    """Create course and assignment management view"""
    course_frame = ttk.Frame(parent)
    course_frame.pack(fill="both", expand=True)

    # Main card
    course_card = ttk.Frame(course_frame, style='Card.TFrame')
    course_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(course_card, text="Course & Assignment Management", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Assignment Profile Section
    profile_frame = ttk.LabelFrame(course_card, text="Assignment Profile", padding=15)
    profile_frame.pack(fill='x', padx=15, pady=(0, 15))

    profile_row1 = ttk.Frame(profile_frame)
    profile_row1.pack(fill='x', pady=2)
    ttk.Label(profile_row1, text="Assignment Name:").pack(side='left')
    self.profile_name_var = tk.StringVar()
    ttk.Entry(profile_row1, textvariable=self.profile_name_var, width=30).pack(side='left', padx=(5, 15))
    ttk.Label(profile_row1, text="Course:").pack(side='left')
    self.profile_course_var = tk.StringVar()
    ttk.Entry(profile_row1, textvariable=self.profile_course_var, width=20).pack(side='left', padx=(5, 0))

    profile_row2 = ttk.Frame(profile_frame)
    profile_row2.pack(fill='x', pady=2)
    ttk.Label(profile_row2, text="Expected Word Count:").pack(side='left')
    self.profile_words_var = tk.StringVar(value="1000")
    ttk.Entry(profile_row2, textvariable=self.profile_words_var, width=10).pack(side='left', padx=(5, 15))
    ttk.Label(profile_row2, text="Assignment Type:").pack(side='left')
    self.profile_type_var = tk.StringVar(value="Essay")
    ttk.Combobox(profile_row2, textvariable=self.profile_type_var,
                values=["Essay", "Research Paper", "Lab Report", "Code", "Creative Writing"],
                width=15, state='readonly').pack(side='left', padx=(5, 0))

    ttk.Button(profile_frame, text="Create Assignment Profile",
              command=self.create_assignment_profile).pack(anchor='e', pady=(10, 0))

    # Baseline Section
    baseline_frame = ttk.LabelFrame(course_card, text="Assignment Baseline", padding=15)
    baseline_frame.pack(fill='x', padx=15, pady=(0, 15))

    baseline_row = ttk.Frame(baseline_frame)
    baseline_row.pack(fill='x', pady=2)
    ttk.Label(baseline_row, text="Select Assignment:").pack(side='left')
    self.baseline_assignment_var = tk.StringVar()
    self.baseline_combo = ttk.Combobox(baseline_row, textvariable=self.baseline_assignment_var,
                                      width=30, state='readonly')
    self.baseline_combo.pack(side='left', padx=(5, 10))
    ttk.Button(baseline_row, text="Refresh", command=self._load_assignment_profiles).pack(side='left')

    baseline_controls = ttk.Frame(baseline_frame)
    baseline_controls.pack(fill='x', pady=(10, 0))
    ttk.Button(baseline_controls, text="Set Baseline from Sample",
              command=self.set_assignment_baseline).pack(side='left', padx=(0, 10))
    ttk.Button(baseline_controls, text="Compare Against Baseline",
              command=self.compare_against_assignment_baseline).pack(side='left')

    # Course Dashboard Section
    dashboard_frame = ttk.LabelFrame(course_card, text="Course Integrity Dashboard", padding=15)
    dashboard_frame.pack(fill='x', padx=15, pady=(0, 15))

    dash_row = ttk.Frame(dashboard_frame)
    dash_row.pack(fill='x', pady=2)
    ttk.Label(dash_row, text="Select Course:").pack(side='left')
    self.dash_course_var = tk.StringVar()
    self.dash_course_combo = ttk.Combobox(dash_row, textvariable=self.dash_course_var,
                                         width=30, state='readonly')
    self.dash_course_combo.pack(side='left', padx=(5, 10))
    ttk.Button(dash_row, text="View Dashboard",
              command=self.view_course_integrity_dashboard).pack(side='left')

    # End of Semester Report
    report_frame = ttk.LabelFrame(course_card, text="Semester Reports", padding=15)
    report_frame.pack(fill='x', padx=15, pady=(0, 15))

    report_row = ttk.Frame(report_frame)
    report_row.pack(fill='x')
    ttk.Label(report_row, text="Semester:").pack(side='left')
    self.report_semester_var = tk.StringVar(value="Fall 2025")
    ttk.Combobox(report_row, textvariable=self.report_semester_var,
                values=["Fall 2025", "Spring 2025", "Summer 2025", "Fall 2024"],
                width=15, state='readonly').pack(side='left', padx=(5, 10))
    ttk.Button(report_row, text="Generate Course End Report",
              command=self.generate_course_end_report).pack(side='left')

    # Load initial data
    self._load_assignment_profiles()
    self._load_courses_for_dashboard()


def _load_assignment_profiles(self):
    """Load assignment profiles for dropdown"""
    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='ai_assignment_profiles'
        ''')

        if cursor.fetchone():
            cursor.execute('SELECT name FROM ai_assignment_profiles ORDER BY name')
            profiles = [row[0] for row in cursor.fetchall()]
            self.baseline_combo['values'] = profiles

        conn.close()
    except Exception:
        pass


def _load_courses_for_dashboard(self):
    """Load courses for dashboard dropdown"""
    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT course_name FROM courses ORDER BY course_name')
        courses = [row[0] for row in cursor.fetchall()]
        self.dash_course_combo['values'] = courses
        conn.close()
    except Exception:
        pass


def create_assignment_profile(self):
    """Define expected characteristics for an assignment"""
    try:
        name = self.profile_name_var.get().strip()
        course = self.profile_course_var.get().strip()
        words = int(self.profile_words_var.get())
        assignment_type = self.profile_type_var.get()

        if not name or not course:
            messagebox.showerror("Error", "Please enter assignment name and course")
            return

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_assignment_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    course TEXT,
                    expected_word_count INTEGER,
                    assignment_type TEXT,
                    baseline_ai_score REAL,
                    baseline_vocab_diversity REAL,
                    baseline_sentence_complexity REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                INSERT INTO ai_assignment_profiles (name, course, expected_word_count, assignment_type)
                VALUES (?, ?, ?, ?)
            ''', (name, course, words, assignment_type))

            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo("Success", f"Assignment profile '{name}' created")
        self._load_assignment_profiles()
        self.update_status(f"Assignment profile created: {name}")
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", "An assignment with this name already exists")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create profile: {str(e)}")


def set_assignment_baseline(self):
    """Establish baseline metrics for a specific assignment"""
    assignment = self.baseline_assignment_var.get()
    if not assignment:
        messagebox.showwarning("Warning", "Please select an assignment")
        return

    # Ask user to select sample submissions
    files = filedialog.askopenfilenames(
        title="Select Sample Submissions for Baseline",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )

    if not files:
        return

    try:
        total_ai_score = 0
        total_vocab = 0
        total_complexity = 0
        count = 0

        for file_path in files:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

            if hasattr(self.detector, 'analyze_text'):
                result = self.detector.analyze_text(text)
                if result:
                    total_ai_score += result.get('ai_probability', 0)
                    total_vocab += result.get('vocabulary_diversity', 0.5)
                    total_complexity += result.get('sentence_complexity', 0.5)
                    count += 1

        if count == 0:
            messagebox.showwarning("Warning", "Could not analyze any files")
            return

        avg_ai = total_ai_score / count
        avg_vocab = total_vocab / count
        avg_complexity = total_complexity / count

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE ai_assignment_profiles
                SET baseline_ai_score = ?, baseline_vocab_diversity = ?, baseline_sentence_complexity = ?
                WHERE name = ?
            ''', (avg_ai, avg_vocab, avg_complexity, assignment))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo("Success",
                          f"Baseline established from {count} samples:\n\n"
                          f"Avg AI Score: {avg_ai:.1f}%\n"
                          f"Avg Vocabulary Diversity: {avg_vocab:.2f}\n"
                          f"Avg Sentence Complexity: {avg_complexity:.2f}")
        self.update_status(f"Baseline set for {assignment}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to set baseline: {str(e)}")


def compare_against_assignment_baseline(self):
    """Compare submission against assignment expectations"""
    assignment = self.baseline_assignment_var.get()
    if not assignment:
        messagebox.showwarning("Warning", "Please select an assignment")
        return

    # Get current text
    text = self.text_input.get('1.0', tk.END).strip() if hasattr(self, 'text_input') else ""
    if not text:
        messagebox.showwarning("Warning", "Please enter text to compare in the Text Analysis view")
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT baseline_ai_score, baseline_vocab_diversity, baseline_sentence_complexity
            FROM ai_assignment_profiles WHERE name = ?
        ''', (assignment,))
        baseline = cursor.fetchone()
        conn.close()

        if not baseline or baseline[0] is None:
            messagebox.showwarning("Warning", "No baseline set for this assignment. Please set baseline first.")
            return

        # Analyze current text
        if hasattr(self.detector, 'analyze_text'):
            result = self.detector.analyze_text(text)
            if result:
                current_ai = result.get('ai_probability', 0)
                current_vocab = result.get('vocabulary_diversity', 0.5)
                current_complexity = result.get('sentence_complexity', 0.5)

                ai_diff = current_ai - baseline[0]
                vocab_diff = current_vocab - baseline[1]
                complexity_diff = current_complexity - baseline[2]

                report = "Comparison to Assignment Baseline\n"
                report += f"{'='*40}\n\n"
                report += f"AI Score: {current_ai:.1f}% (Baseline: {baseline[0]:.1f}%, Diff: {ai_diff:+.1f}%)\n"
                report += f"Vocabulary: {current_vocab:.2f} (Baseline: {baseline[1]:.2f}, Diff: {vocab_diff:+.2f})\n"
                report += f"Complexity: {current_complexity:.2f} (Baseline: {baseline[2]:.2f}, Diff: {complexity_diff:+.2f})\n\n"

                if abs(ai_diff) > 20:
                    report += "WARNING: AI score significantly differs from baseline\n"

                messagebox.showinfo("Baseline Comparison", report)
                self.update_status("Baseline comparison complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to compare: {str(e)}")


def view_course_integrity_dashboard(self):
    """Course-level integrity metrics dashboard"""
    course = self.dash_course_var.get()
    if not course:
        messagebox.showwarning("Warning", "Please select a course")
        return

    # Create dashboard window
    dash_window = tk.Toplevel(self.root)
    dash_window.title(f"Integrity Dashboard - {course}")
    dash_window.geometry("800x600")

    ttk.Label(dash_window, text=f"Academic Integrity Dashboard: {course}",
             font=('Segoe UI', 14, 'bold')).pack(pady=15)

    # Stats frame
    stats_frame = ttk.LabelFrame(dash_window, text="Overview Statistics", padding=15)
    stats_frame.pack(fill='x', padx=20, pady=10)

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Get statistics (simulated if no data)
        cursor.execute('''
            SELECT COUNT(*), AVG(ai_probability),
                   SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END)
            FROM ai_analysis_history
            WHERE course_name = ?
        ''', (course,))
        stats = cursor.fetchone()
        conn.close()

        total = stats[0] if stats[0] else 0
        avg_score = stats[1] if stats[1] else 0
        high_risk = stats[2] if stats[2] else 0

        ttk.Label(stats_frame, text=f"Total Submissions Analyzed: {total}").pack(anchor='w')
        ttk.Label(stats_frame, text=f"Average AI Detection Score: {avg_score:.1f}%").pack(anchor='w')
        ttk.Label(stats_frame, text=f"High Risk Submissions: {high_risk}").pack(anchor='w')
        ttk.Label(stats_frame, text=f"Risk Rate: {(high_risk/total*100) if total > 0 else 0:.1f}%").pack(anchor='w')
    except Exception as e:
        ttk.Label(stats_frame, text=f"Error loading statistics: {e}").pack(anchor='w')

    self.update_status(f"Viewing dashboard for {course}")


def generate_course_end_report(self):
    """End-of-semester academic integrity summary"""
    semester = self.report_semester_var.get()

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Generate report data
        cursor.execute('''
            SELECT course_name, COUNT(*) as submissions,
                   AVG(ai_probability) as avg_score,
                   SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
            FROM ai_analysis_history
            GROUP BY course_name
        ''')
        courses = cursor.fetchall()
        conn.close()

        # Create report
        report = f"Academic Integrity Report - {semester}\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        report += "="*60 + "\n\n"

        if courses:
            for course_name, submissions, avg_score, high_risk in courses:
                report += f"Course: {course_name}\n"
                report += f"  Total Submissions: {submissions}\n"
                report += f"  Average AI Score: {avg_score:.1f}%\n"
                report += f"  High Risk Cases: {high_risk}\n\n"
        else:
            report += "No analysis data available for this period.\n"

        # Save report
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"integrity_report_{semester.replace(' ', '_')}.txt"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            messagebox.showinfo("Success", f"Report saved to {file_path}")
            self.update_status("Course end report generated")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate report: {str(e)}")


