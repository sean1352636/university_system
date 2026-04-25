import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import threading
import pandas as pd

# Import internationalization support
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.analytics_tab")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.analytics_tab")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import path constants
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

# Import main database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("analytics_tab.py:33 %s", 'except ImportError')
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        get_modules
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    logger.exception("analytics_tab.py:42 %s", 'except ImportError')
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Import window classes
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.misc_windows import GamificationWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.alerts_predictive_windows import PredictiveAnalyticsWindow, SinglePredictionDialog


def batch_risk_analysis(self):
        """Perform batch risk analysis"""
        if not self.analytics:
            messagebox.showerror(_("common.error"), _("attendance.messages.analytics_not_available"))
            return

        self.update_status(_("attendance.messages.performing_batch_analysis"))

        # Clear predictions tree
        for item in self.predictions_tree.get_children():
            self.predictions_tree.delete(item)

        # Add sample data for demonstration
        sample_predictions = [
            ("S001", "John Doe", "CS101", "Low Risk", "0.850", "Consecutive: 0, Days: 1"),
            ("S003", "Bob Wilson", "CS101", "High Risk", "0.920", "Consecutive: 3, Days: 7"),
            ("S007", "Alice Brown", "CS102", "Medium Risk", "0.750", "Consecutive: 1, Days: 3"),
        ]

        for prediction in sample_predictions:
            self.predictions_tree.insert('', 'end', values=prediction)

        # Switch to analytics tab
        self.notebook.select(4)  # Analytics tab index

        self.update_status(_("attendance.messages.batch_analysis_complete"), "success")
        messagebox.showinfo(_("attendance.messages.analysis_complete"), _("attendance.messages.batch_analysis_message"))

def predict_student_risk(self):
        """Predict risk for a specific student"""
        if not self.analytics:
            messagebox.showerror(_("common.error"), _("attendance.messages.analytics_not_available"))
            return

        student_id = simpledialog.askstring(_("attendance.dialogs.student_risk_prediction"), _("attendance.messages.enter_student_id"))
        if not student_id:
            return

        # Get module selection
        modules = self.module_combo['values']
        if not modules:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.no_modules_available"))
            return

        module_code = modules[0].split(' - ')[0]  # Use first module for demo

        try:
            prediction = self.analytics.predict_student_risk(student_id, module_code)

            if prediction:
                # Clear predictions tree and add result
                for item in self.predictions_tree.get_children():
                    self.predictions_tree.delete(item)

                factors_text = f"Consecutive absences: {prediction['factors']['consecutive_absences']}, " \
                              f"Days since last: {prediction['factors']['days_since_last_attendance']}"

                self.predictions_tree.insert('', 'end', values=(
                    student_id,
                    _("attendance.analytics.student_name_placeholder"),  # Would get from database
                    module_code,
                    prediction['risk_level'],
                    f"{prediction['confidence']:.3f}",
                    factors_text
                ))

                # Switch to analytics tab
                self.notebook.select(4)  # Analytics tab index

                messagebox.showinfo(_("attendance.messages.prediction_complete"),
                    _("attendance.messages.prediction_result").format(
                        risk_level=prediction['risk_level'],
                        confidence=f"{prediction['confidence']:.3f}",
                        rate=f"{prediction['current_attendance_rate']:.1f}"
                    ))
            else:
                messagebox.showwarning(_("common.warning"), _("attendance.messages.prediction_failed"))

        except Exception as e:
            logger.exception("analytics_tab.py:128 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), _("attendance.messages.prediction_error", error=str(e)))

def on_model_trained(self, success):
        """Handle model training completion"""
        if success:
            self.update_status(_("attendance.messages.model_trained_success"), "success")
            messagebox.showinfo(_("common.success"), _("attendance.messages.model_trained_success"))
        else:
            self.update_status(_("attendance.messages.model_training_failed"), "error")
            messagebox.showerror(_("common.error"), _("attendance.messages.model_training_failed"))

def create_analytics_tab(self):
        """Create analytics tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text=_("attendance.tabs.analytics"))

        # Analytics controls
        controls_frame = ttk.LabelFrame(analytics_frame, text=_("attendance.analytics.controls"), padding=10)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        controls_grid = ttk.Frame(controls_frame)
        controls_grid.pack(fill=tk.X)

        ttk.Button(controls_grid, text=_("attendance.analytics.train_model"),
                  command=self.train_prediction_model, style='Primary.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(controls_grid, text=_("attendance.analytics.predict_risk"),
                  command=self.predict_student_risk, style='Warning.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(controls_grid, text=_("attendance.analytics.batch_analysis"),
                  command=self.batch_risk_analysis, style='Success.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(controls_grid, text=_("attendance.analytics.gamification"),
                  command=self.open_gamification, style='Primary.TButton').grid(row=0, column=3, padx=5)

        # Analytics display
        display_frame = ttk.LabelFrame(analytics_frame, text=_("attendance.analytics.results"), padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True)

        # Results notebook
        self.analytics_notebook = ttk.Notebook(display_frame)
        self.analytics_notebook.pack(fill=tk.BOTH, expand=True)

        # Predictions tab
        predictions_frame = ttk.Frame(self.analytics_notebook)
        self.analytics_notebook.add(predictions_frame, text=_("attendance.analytics.risk_predictions"))

        # Predictions treeview
        pred_columns = (_("attendance.columns.student_id"), _("attendance.columns.name"), _("attendance.columns.module"), _("attendance.analytics.risk_level"), _("attendance.analytics.confidence"), _("attendance.analytics.factors"))
        self.predictions_tree = ttk.Treeview(predictions_frame, columns=pred_columns, show="headings")

        for col in pred_columns:
            self.predictions_tree.heading(col, text=col)
            self.predictions_tree.column(col, width=120)

        pred_scrollbar = ttk.Scrollbar(predictions_frame, orient=tk.VERTICAL, command=self.predictions_tree.yview)
        self.predictions_tree.configure(yscrollcommand=pred_scrollbar.set)

        self.predictions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pred_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Gamification tab
        gamification_frame = ttk.Frame(self.analytics_notebook)
        self.analytics_notebook.add(gamification_frame, text=_("attendance.analytics.gamification_tab"))

        # Leaderboard
        leader_columns = (_("attendance.columns.rank"), _("attendance.columns.student_id"), _("attendance.columns.name"), _("attendance.columns.points"), _("attendance.columns.level"), _("attendance.columns.streak"))
        self.leaderboard_tree = ttk.Treeview(gamification_frame, columns=leader_columns, show="headings")

        for col in leader_columns:
            self.leaderboard_tree.heading(col, text=col)
            self.leaderboard_tree.column(col, width=100)

        leader_scrollbar = ttk.Scrollbar(gamification_frame, orient=tk.VERTICAL, command=self.leaderboard_tree.yview)
        self.leaderboard_tree.configure(yscrollcommand=leader_scrollbar.set)

        self.leaderboard_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        leader_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

def open_gamification(self):
        """Open gamification window"""
        GamificationWindow(self.root)

def train_prediction_model(self):
        """Train the predictive analytics model"""
        if not self.analytics:
            messagebox.showerror(_("common.error"), _("attendance.messages.analytics_not_available"))
            return

        self.update_status(_("attendance.messages.training_model"))

        def train_model():
            try:
                success = self.analytics.train_model()
                self.root.after(0, lambda: self.on_model_trained(success))
            except Exception as e:
                logger.exception("analytics_tab.py:221 %s", 'except Exception as e')
                self.root.after(0, lambda _e=e: messagebox.showerror(_("common.error"), _("attendance.messages.model_training_error", error=str(_e))))

        threading.Thread(target=train_model, daemon=True).start()

