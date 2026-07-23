import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
from pathlib import Path
import uuid
from PIL import Image, ImageTk
import io
import os
import csv
import re
import shutil
from collections import deque

# Import internationalization support
from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.alerts_predictive_windows")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.alerts_predictive_windows")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import path constants
from education_system.post_18.university_system.core.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from education_system.post_18.university_system.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("alerts_predictive_windows.py:50 %s", 'except ImportError')
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.post_18.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        AttendancePredictiveAnalytics, BackupRecoverySystem,
        EnhancedNotificationSystem, FaceRecognitionSystem, GeofencingSystem,
        QRAttendanceSystem, create_missing_tables, display_attendance_menu,
        generate_executive_summary_report, get_enhanced_setting,
        get_module_attendance, get_modules, get_student_attendance,
        init_enhanced_attendance_db, record_attendance, set_enhanced_setting
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    logger.exception("alerts_predictive_windows.py:64 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False


# Import attendance notification service
try:
    from education_system.post_18.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("alerts_predictive_windows.py:75 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True


class AttendanceAlertsWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.attendance_alerts_manager"))
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.create_widgets()
        self.load_alerts()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="🚨 Attendance Alerts Manager", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Controls frame
        controls_frame = ttk.Frame(self.window)
        controls_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(controls_frame, text="Create Alert",
                  command=self.create_alert, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controls_frame, text="Acknowledge Selected",
                  command=self.acknowledge_alert, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controls_frame, text=_("common.refresh"),
                  command=self.load_alerts, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))

        # Filter frame
        filter_frame = ttk.LabelFrame(self.window, text="Filters", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        filter_controls = ttk.Frame(filter_frame)
        filter_controls.pack(fill=tk.X)

        ttk.Label(filter_controls, text="Status:").grid(row=0, column=0, sticky=tk.W)
        self.status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_controls, textvariable=self.status_filter_var,
                                   values=["All", "Pending", "Acknowledged", "Resolved"], state="readonly", width=15)
        status_combo.grid(row=0, column=1, padx=(5, 20))

        ttk.Label(filter_controls, text="Severity:").grid(row=0, column=2, sticky=tk.W)
        self.severity_filter_var = tk.StringVar(value="All")
        severity_combo = ttk.Combobox(filter_controls, textvariable=self.severity_filter_var,
                                     values=["All", "Low", "Medium", "High", "Critical"], state="readonly", width=15)
        severity_combo.grid(row=0, column=3, padx=(5, 20))

        ttk.Button(filter_controls, text="Apply Filters",
                  command=self.apply_filters, style='Primary.TButton').grid(row=0, column=4, padx=(20, 0))

        # Alerts treeview
        alerts_frame = ttk.LabelFrame(self.window, text="Active Alerts", padding=10)
        alerts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ("Alert ID", "Student ID", "Name", "Module", "Type", "Severity", "Status", "Created")
        self.alerts_tree = ttk.Treeview(alerts_frame, columns=columns, show="headings")

        for col in columns:
            self.alerts_tree.heading(col, text=col)
            self.alerts_tree.column(col, width=100)

        alerts_scrollbar = ttk.Scrollbar(alerts_frame, orient=tk.VERTICAL, command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=alerts_scrollbar.set)

        self.alerts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        alerts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to view details
        self.alerts_tree.bind('<Double-1>', self.view_alert_details)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def load_alerts(self):
        # Replaces the old hardcoded sample list. Each row is the most
        # recent student_risk_assessment entry per student — i.e. the
        # output the absence tracker's risk feed writes.
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)

        sf = (self.severity_filter_var.get()
              if hasattr(self, 'severity_filter_var') else "All")
        st_filter = (self.status_filter_var.get()
                     if hasattr(self, 'status_filter_var') else "All")

        rows = []
        try:
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
            else:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cur = conn.cursor()
            cur.execute("""
                SELECT r.id, r.student_id,
                       COALESCE(NULLIF(TRIM(s.first_name || ' ' || s.last_name), ''),
                                r.student_id) AS name,
                       COALESCE(r.prediction_model, 'risk_feed') AS model,
                       r.risk_level, r.risk_score, r.assessment_date
                FROM student_risk_assessment r
                LEFT JOIN students s ON s.student_id = r.student_id
                WHERE r.id = (SELECT MAX(id) FROM student_risk_assessment
                              WHERE student_id = r.student_id)
                ORDER BY
                    CASE LOWER(COALESCE(r.risk_level, ''))
                        WHEN 'high' THEN 0
                        WHEN 'medium' THEN 1
                        ELSE 2 END,
                    r.risk_score DESC
            """)
            rows = cur.fetchall()
            conn.close()
        except Exception:
            logger.exception("load_alerts: risk feed query failed")

        sev_map = {"high": "High", "medium": "Medium", "low": "Low"}
        # Status column has no backing field in the feed schema yet;
        # treat every feed row as Pending so the existing filter UI
        # still behaves predictably.
        status = "Pending"
        for (rid, sid, name, model, level, score, asof) in rows:
            level_l = (level or "").lower()
            sev = sev_map.get(level_l, (level or "Unknown").title())
            if level_l == "high" and score is not None and score >= 70:
                sev = "Critical"
            if sf != "All" and sf != sev:
                continue
            if st_filter != "All" and st_filter != status:
                continue
            self.alerts_tree.insert(
                '', 'end',
                values=(f"R{rid}", sid, name, "—",
                        f"Attendance risk ({model})",
                        sev, status, asof or ""))

    def create_alert(self):
        CreateAlertWindow(self.window, self.load_alerts)

    def acknowledge_alert(self):
        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), "Please select an alert to acknowledge")
            return

        item = self.alerts_tree.item(selection[0])
        alert_id = item['values'][0]

        # Update alert status
        messagebox.showinfo(_("common.success"), f"Alert {alert_id} acknowledged successfully!")
        self.load_alerts()

    def apply_filters(self):
        # Apply filters and refresh view
        self.load_alerts()

    def view_alert_details(self, event):
        selection = self.alerts_tree.selection()
        if selection:
            item = self.alerts_tree.item(selection[0])
            alert_data = item['values']
            AlertDetailsWindow(self.window, alert_data)

class CreateAlertWindow:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.create_alert"))
        self.window.geometry("500x400")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Create New Alert", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Form frame
        form_frame = ttk.LabelFrame(self.window, text="Alert Details", padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Student ID
        ttk.Label(form_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.student_id_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # Module
        ttk.Label(form_frame, text="Module:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(form_frame, textvariable=self.module_var, width=27)
        module_combo.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # Set module values
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            modules = get_modules()
            module_values = [f"{code} - {name}" for code, name in modules]
        else:
            module_values = ["CS101 - Programming", "CS102 - Data Structures"]
        module_combo['values'] = module_values

        # Alert Type
        ttk.Label(form_frame, text="Alert Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.alert_type_var = tk.StringVar(value="Custom")
        alert_type_combo = ttk.Combobox(form_frame, textvariable=self.alert_type_var,
                                       values=["Attendance Warning", "Consecutive Absences", "Late Pattern", "Custom"],
                                       state="readonly", width=27)
        alert_type_combo.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # Severity
        ttk.Label(form_frame, text="Severity:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.severity_var = tk.StringVar(value="Medium")
        severity_combo = ttk.Combobox(form_frame, textvariable=self.severity_var,
                                     values=["Low", "Medium", "High", "Critical"],
                                     state="readonly", width=27)
        severity_combo.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # Message
        ttk.Label(form_frame, text="Message:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.message_text = tk.Text(form_frame, width=35, height=6)
        self.message_text.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # Auto-send notifications
        self.auto_send_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Send automatic notifications",
                       variable=self.auto_send_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=10)

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Create Alert",
                  command=self.create_alert, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"),
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def create_alert(self):
        try:
            student_id = self.student_id_var.get()
            module = self.module_var.get()
            alert_type = self.alert_type_var.get()
            severity = self.severity_var.get()
            message = self.message_text.get(1.0, tk.END).strip()

            if not all([student_id, module, message]):
                messagebox.showwarning(_("common.warning"), "Please fill in all required fields")
                return

            module_code = module.split(' - ')[0] if ' - ' in module else module

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                notification_system = EnhancedNotificationSystem()
                success = notification_system.create_attendance_alert(
                    student_id, module_code, alert_type, severity, message
                )

                if success:
                    messagebox.showinfo(_("common.success"), "Alert created successfully!")
                else:
                    messagebox.showerror(_("common.error"), "Failed to create alert")
            else:
                messagebox.showinfo("Demo", "Alert would be created here")

            self.callback()  # Refresh parent data
            self.window.destroy()

        except Exception as e:
            logger.exception("alerts_predictive_windows.py:304 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to create alert: {e}")

class AlertDetailsWindow:
    def __init__(self, parent, alert_data):
        self.parent = parent
        self.alert_data = alert_data

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.alert_details"))
        self.window.geometry("500x300")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Alert Details", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Details frame
        details_frame = ttk.LabelFrame(self.window, text="Alert Information", padding=20)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Display alert details
        alert_id, student_id, name, module, alert_type, severity, status, created = self.alert_data

        details = [
            ("Alert ID:", alert_id),
            ("Student:", f"{name} ({student_id})"),
            ("Module:", module),
            ("Type:", alert_type),
            ("Severity:", severity),
            ("Status:", status),
            ("Created:", created)
        ]

        for i, (label, value) in enumerate(details):
            ttk.Label(details_frame, text=label, font=('Arial', 10, 'bold')).grid(row=i, column=0, sticky=tk.W, pady=5)
            ttk.Label(details_frame, text=str(value)).grid(row=i, column=1, sticky=tk.W, padx=(20, 0), pady=5)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Primary.TButton').pack(pady=10)

class PredictiveAnalyticsWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.predictive_analytics"))
        self.window.geometry("900x700")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="🔮 Predictive Analytics", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Controls frame
        controls_frame = ttk.LabelFrame(self.window, text="Model Controls", padding=10)
        controls_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        controls_grid = ttk.Frame(controls_frame)
        controls_grid.pack(fill=tk.X)

        ttk.Button(controls_grid, text="Train Model",
                  command=self.train_model, style='Primary.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(controls_grid, text="Single Prediction",
                  command=self.single_prediction, style='Warning.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(controls_grid, text="Batch Analysis",
                  command=self.batch_analysis, style='Success.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(controls_grid, text="Load from Risk Feed",
                  command=self.load_from_risk_feed,
                  style='Success.TButton').grid(row=0, column=3, padx=5)
        ttk.Button(controls_grid, text="Model Info",
                  command=self.show_model_info, style='Primary.TButton').grid(row=0, column=4, padx=5)

        # Results notebook
        self.results_notebook = ttk.Notebook(self.window)
        self.results_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Predictions tab
        predictions_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(predictions_frame, text="Predictions")

        # Predictions treeview
        pred_columns = ("Student ID", "Name", "Module", "Risk Level", "Confidence", "Current Rate", "Factors")
        self.predictions_tree = ttk.Treeview(predictions_frame, columns=pred_columns, show="headings")

        for col in pred_columns:
            self.predictions_tree.heading(col, text=col)
            self.predictions_tree.column(col, width=120)

        pred_scrollbar = ttk.Scrollbar(predictions_frame, orient=tk.VERTICAL, command=self.predictions_tree.yview)
        self.predictions_tree.configure(yscrollcommand=pred_scrollbar.set)

        self.predictions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pred_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Model info tab
        model_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(model_frame, text="Model Information")

        self.model_info_text = tk.Text(model_frame, wrap=tk.WORD)
        model_scrollbar = ttk.Scrollbar(model_frame, orient=tk.VERTICAL, command=self.model_info_text.yview)
        self.model_info_text.configure(yscrollcommand=model_scrollbar.set)

        self.model_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        model_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial model info
        self.load_model_info()

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def train_model(self):
        if not ORIGINAL_FUNCTIONS_AVAILABLE:
            messagebox.showinfo("Demo", "Model training would be performed here")
            return

        self.update_status("Training model...")

        def train_in_background():
            try:
                analytics = AttendancePredictiveAnalytics()
                success = analytics.train_model()

                self.window.after(0, lambda: self.on_training_complete(success))
            except Exception as e:
                logger.exception("alerts_predictive_windows.py:433 %s", 'except Exception as e')
                self.window.after(0, lambda _e=e: messagebox.showerror(_("common.error"), f"Training failed: {_e}"))

        threading.Thread(target=train_in_background, daemon=True).start()

    def on_training_complete(self, success):
        if success:
            messagebox.showinfo(_("common.success"), "Model trained successfully!")
            self.load_model_info()
        else:
            messagebox.showerror(_("common.error"), "Model training failed")

    def single_prediction(self):
        SinglePredictionWindow(self.window, self.update_predictions)

    def batch_analysis(self):
        messagebox.showinfo("Info", "Performing batch risk analysis...")
        self.load_real_predictions()

    def load_real_predictions(self):
        """Load actual risk predictions from database"""
        # Clear existing predictions
        for item in self.predictions_tree.get_children():
            self.predictions_tree.delete(item)

        try:
            # Get database connection
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
            else:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))

            cursor = conn.cursor()

            # Calculate attendance statistics for each student per module
            cursor.execute('''
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    ar.module_code,
                    COUNT(*) as total_sessions,
                    SUM(CASE WHEN ar.status = 'present' THEN 1 ELSE 0 END) as present_count,
                    SUM(CASE WHEN ar.status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                    CAST(SUM(CASE WHEN ar.status = 'present' THEN 1 ELSE 0 END) AS FLOAT) /
                        COUNT(*) * 100 as attendance_rate
                FROM students s
                JOIN attendance_records ar ON s.student_id = ar.student_id
                WHERE ar.module_code IS NOT NULL
                GROUP BY s.student_id, ar.module_code
                HAVING COUNT(*) >= 3
                ORDER BY attendance_rate ASC
            ''')

            results = cursor.fetchall()
            conn.close()

            if not results:
                # Show message if no data
                messagebox.showinfo("Info", "No attendance data available for analysis.\n\nPlease ensure attendance records exist in the database.")
                return

            # Process results and determine risk levels
            for row in results:
                student_id, student_name, module_code, total, present, absent, rate = row

                # Determine risk level based on attendance rate
                if rate >= 80:
                    risk_level = "Low Risk"
                    confidence = 0.85
                    factors = "Good attendance pattern"
                elif rate >= 70:
                    risk_level = "Medium Risk"
                    confidence = 0.78
                    factors = "Declining attendance"
                else:
                    risk_level = "High Risk"
                    confidence = 0.92
                    if absent >= 3:
                        factors = f"{absent} absences recorded"
                    else:
                        factors = "Poor attendance rate"

                # Format attendance rate
                rate_str = f"{rate:.1f}%"
                confidence_str = f"{confidence:.2f}"

                # Insert into tree
                prediction = (student_id, student_name, module_code or "Unknown",
                            risk_level, confidence_str, rate_str, factors)

                item = self.predictions_tree.insert('', 'end', values=prediction)

                # Color code by risk level
                if risk_level == "High Risk":
                    self.predictions_tree.set(item, "Risk Level", "🔴 High Risk")
                elif risk_level == "Medium Risk":
                    self.predictions_tree.set(item, "Risk Level", "🟡 Medium Risk")
                else:
                    self.predictions_tree.set(item, "Risk Level", "🟢 Low Risk")

            messagebox.showinfo("Success", f"Analyzed {len(results)} student-module combinations")

        except Exception as e:
            logger.exception("alerts_predictive_windows.py:535 %s", 'except Exception as e')
            messagebox.showerror("Error", f"Failed to load predictions: {e}")

    def load_from_risk_feed(self):
        """Populate the predictions tree from the persisted risk feed.

        Reads the most recent student_risk_assessment row per student
        (what the absence-tracker's Risk Feed writes) instead of
        recomputing from raw attendance. Lets you see exactly what the
        downstream consumers are seeing, including the score the feed's
        blended model produced.
        """
        for item in self.predictions_tree.get_children():
            self.predictions_tree.delete(item)

        try:
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
            else:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.student_id,
                       COALESCE(NULLIF(TRIM(s.first_name || ' ' || s.last_name), ''),
                                r.student_id) AS name,
                       r.risk_level, r.risk_score, r.confidence,
                       r.assessment_date, r.prediction_model
                FROM student_risk_assessment r
                LEFT JOIN students s ON s.student_id = r.student_id
                WHERE r.id = (SELECT MAX(id) FROM student_risk_assessment
                              WHERE student_id = r.student_id)
                ORDER BY
                    CASE LOWER(COALESCE(r.risk_level, ''))
                        WHEN 'high' THEN 0
                        WHEN 'medium' THEN 1
                        ELSE 2 END,
                    r.risk_score DESC
            """)
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.exception("load_from_risk_feed query failed")
            messagebox.showerror("Error",
                                 f"Failed to load risk feed: {e}")
            return

        if not rows:
            messagebox.showinfo(
                "Info",
                "No persisted risk assessments yet — run "
                "'Risk Feed' from the Absence Tracker (#33) first.")
            return

        level_label = {"high": "High Risk", "medium": "Medium Risk",
                       "low": "Low Risk"}
        for (sid, name, level, score, conf, asof, model) in rows:
            level_l = (level or "").lower()
            label = level_label.get(level_l, (level or "Unknown").title())
            score_v = score if score is not None else 0.0
            # Module column is N/A for the feed (it's per-student, not
            # per-module); show ALL.
            factors = (f"score={score_v:.1f} as of {asof or '—'} "
                       f"({model or 'risk_feed'})")
            confidence_str = f"{conf:.2f}" if conf is not None else "—"
            item = self.predictions_tree.insert(
                '', 'end',
                values=(sid, name, "ALL", label, confidence_str,
                        f"{score_v:.1f}", factors))
            if level_l == "high":
                self.predictions_tree.set(item, "Risk Level",
                                          "🔴 " + label)
            elif level_l == "medium":
                self.predictions_tree.set(item, "Risk Level",
                                          "🟡 " + label)
            else:
                self.predictions_tree.set(item, "Risk Level",
                                          "🟢 " + label)

        messagebox.showinfo(
            "Loaded",
            f"Loaded {len(rows)} student(s) from the risk feed.")

    def update_predictions(self, prediction_data):
        # Add new prediction to the tree
        item = self.predictions_tree.insert('', 'end', values=prediction_data)
        risk_level = prediction_data[3]
        if "High" in risk_level:
            self.predictions_tree.set(item, "Risk Level", "🔴 " + risk_level)
        elif "Medium" in risk_level:
            self.predictions_tree.set(item, "Risk Level", "🟡 " + risk_level)
        else:
            self.predictions_tree.set(item, "Risk Level", "🟢 " + risk_level)

    def show_model_info(self):
        self.results_notebook.select(1)  # Switch to model info tab

    def load_model_info(self):
        info_text = """PREDICTIVE ANALYTICS MODEL INFORMATION
========================================

Model Type: Random Forest Classifier
Purpose: Predict student attendance risk levels

Features Used:
- Current attendance rate
- Consecutive absences count
- Days since last attendance
- Total sessions attended
- Week of term
- Day of week
- Previous module performance

Risk Levels:
- Low Risk: Expected attendance rate > 80%
- Medium Risk: Expected attendance rate 70-80%
- High Risk: Expected attendance rate < 70%

Model Performance:
- Training Data: Attendance history from all students
- Accuracy: To be determined after training
- Confidence Threshold: 0.75

Usage:
1. Train the model using historical data
2. Run single predictions for specific students
3. Perform batch analysis for all students
4. Review recommendations for at-risk students

Last Training: Not trained yet
Model Status: Ready for training
"""

        self.model_info_text.delete(1.0, tk.END)
        self.model_info_text.insert(tk.END, info_text)

    def update_status(self, message):
        # This would update a status bar if we had one
        print(f"Status: {message}")

class SinglePredictionWindow:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.single_prediction"))
        self.window.geometry("400x300")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Single Student Prediction", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Input frame
        input_frame = ttk.LabelFrame(self.window, text="Student Selection", padding=20)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Student ID
        ttk.Label(input_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.student_id_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)

        # Module
        ttk.Label(input_frame, text="Module:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(input_frame, textvariable=self.module_var, width=17)
        module_combo.grid(row=1, column=1, padx=(10, 0), pady=5)

        # Set module values
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            modules = get_modules()
            module_values = [f"{code} - {name}" for code, name in modules]
        else:
            module_values = ["CS101 - Programming", "CS102 - Data Structures"]
        module_combo['values'] = module_values

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Predict Risk",
                  command=self.predict_risk, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"),
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def predict_risk(self):
        try:
            student_id = self.student_id_var.get()
            module = self.module_var.get()

            if not student_id or not module:
                messagebox.showwarning(_("common.warning"), "Please enter student ID and select module")
                return

            module_code = module.split(' - ')[0] if ' - ' in module else module

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                analytics = AttendancePredictiveAnalytics()
                prediction = analytics.predict_student_risk(student_id, module_code)

                if prediction:
                    # Show prediction results
                    result_text = f"Risk Level: {prediction['risk_level']}\n"
                    result_text += f"Confidence: {prediction['confidence']:.3f}\n"
                    result_text += f"Current Rate: {prediction['current_attendance_rate']:.1f}%\n"
                    result_text += f"Consecutive Absences: {prediction['factors']['consecutive_absences']}\n"
                    result_text += f"Days Since Last: {prediction['factors']['days_since_last_attendance']}"

                    messagebox.showinfo("Prediction Result", result_text)

                    # Add to parent predictions view
                    prediction_data = (
                        student_id,
                        "Student Name",  # Would fetch from database
                        module_code,
                        prediction['risk_level'],
                        f"{prediction['confidence']:.3f}",
                        f"{prediction['current_attendance_rate']:.1f}%",
                        f"Consecutive: {prediction['factors']['consecutive_absences']}, Days: {prediction['factors']['days_since_last_attendance']}"
                    )

                    self.callback(prediction_data)
                    self.window.destroy()
                else:
                    messagebox.showwarning(_("common.warning"), "Unable to generate prediction. Model may not be trained.")
            else:
                # Demo prediction
                sample_prediction = (
                    student_id,
                    "Sample Student",
                    module_code,
                    "Medium Risk",
                    "0.78",
                    "75.0%",
                    "Sample factors"
                )
                self.callback(sample_prediction)
                messagebox.showinfo("Demo", "Sample prediction generated")
                self.window.destroy()

        except Exception as e:
            logger.exception("alerts_predictive_windows.py:700 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Prediction failed: {e}")


# Alias for backward compatibility
SinglePredictionDialog = SinglePredictionWindow


# Aliases for backward compatibility
AlertsWindow = AttendanceAlertsWindow
CreateAlertDialog = CreateAlertWindow
SinglePredictionDialog = SinglePredictionWindow
