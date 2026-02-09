import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

try:
    from university_system.utils.ai.ai_detector.detector import AIDetector
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
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from university_system.modules.shared.utils.i18n import get_text, _

def create_settings_view(self, parent):
    """Create settings and configuration tab"""
    settings_frame = ttk.Frame(parent)

    settings_frame.pack(fill="both", expand=True)

    # Settings card
    settings_card = ttk.Frame(settings_frame, style='Card.TFrame')
    settings_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(settings_card, text=get_text("ai_detector.settings.title"), style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Detection threshold
    threshold_frame = ttk.Frame(settings_card)
    threshold_frame.pack(fill='x', padx=15, pady=(0, 20))

    ttk.Label(threshold_frame, text=get_text("ai_detector.settings.detection_threshold")).pack(side='left')
    self.threshold_var = tk.DoubleVar(value=getattr(self.detector, 'detection_threshold', 0.7))
    threshold_scale = ttk.Scale(threshold_frame, from_=0.1, to=1.0, variable=self.threshold_var,
                              orient='horizontal', length=300)
    threshold_scale.pack(side='left', padx=(10, 10))

    self.threshold_label = ttk.Label(threshold_frame, text=f"{self.threshold_var.get():.2f}")
    self.threshold_label.pack(side='left')

    # Update threshold label
    def update_threshold_label(*args):
        self.threshold_label.config(text=f"{self.threshold_var.get():.2f}")

    self.threshold_var.trace('w', update_threshold_label)

    # Detection methods
    methods_frame = ttk.LabelFrame(settings_card, text=get_text("ai_detector.settings.detection_methods"), padding=15)
    methods_frame.pack(fill='x', padx=15, pady=(0, 20))

    # Create checkboxes for detection methods
    self.method_vars = {}
    methods = [get_text("ai_detector.settings.method_pattern"), get_text("ai_detector.settings.method_statistical"),
               get_text("ai_detector.settings.method_behavioral"), get_text("ai_detector.settings.method_temporal"),
               get_text("ai_detector.settings.method_citation")]

    for i, method in enumerate(methods):
        var = tk.BooleanVar(value=True)
        self.method_vars[method] = var
        ttk.Checkbutton(methods_frame, text=method, variable=var).grid(
            row=i//2, column=i%2, sticky='w', padx=(0, 20), pady=5)

    # Apply settings button
    ttk.Button(settings_card, text=get_text("ai_detector.settings.apply_settings"),
              command=self.apply_settings, style='Accent.TButton').pack(pady=20)


def apply_settings(self):
    """Apply detection settings"""
    try:
        # Update detection threshold
        new_threshold = self.threshold_var.get()
        self.detector.detection_threshold = new_threshold

        # Update detection methods
        detection_methods = {}
        for method, var in self.method_vars.items():
            detection_methods[method.lower().replace(' ', '_')] = var.get()

        if hasattr(self.detector, 'detection_methods'):
            self.detector.detection_methods.update(detection_methods)

        messagebox.showinfo(get_text("ai_detector.settings.settings_title"), get_text("ai_detector.settings.applied_success"))
        self.update_status(get_text("ai_detector.settings.updated"))

    except Exception as e:
        messagebox.showerror(get_text("common.error"), get_text("ai_detector.settings.apply_failed", error=str(e)))


def create_advanced_view(self, parent):
    """Create advanced features tab"""
    advanced_frame = ttk.Frame(parent)

    advanced_frame.pack(fill="both", expand=True)

    # Advanced features card
    advanced_card = ttk.Frame(advanced_frame, style='Card.TFrame')
    advanced_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(advanced_card, text=get_text("ai_detector.advanced.title"), style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Feature sections
    self.create_ml_section(advanced_card)
    self.create_batch_processing_section(advanced_card)
    self.create_export_section(advanced_card)


def create_ml_section(self, parent):
    """Create machine learning section"""
    ml_frame = ttk.LabelFrame(parent, text=get_text("ai_detector.ml.title"), padding=15)
    ml_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(ml_frame, text=get_text("ai_detector.ml.description")).pack(anchor='w')

    ml_buttons = ttk.Frame(ml_frame)
    ml_buttons.pack(fill='x', pady=(10, 0))

    ttk.Button(ml_buttons, text=get_text("ai_detector.ml.train_models"), command=self.train_models).pack(side='left', padx=(0, 10))
    ttk.Button(ml_buttons, text=get_text("ai_detector.ml.model_status"), command=self.show_model_status).pack(side='left')


def train_models(self):
    """Train ML models"""
    if not hasattr(self.detector, 'train_advanced_models'):
        messagebox.showwarning(get_text("common.warning"), get_text("ai_detector.ml.training_not_available"))
        return

    # Show progress
    self.update_status(get_text("ai_detector.ml.training_in_progress"))
    self.show_progress(True)

    def train_thread():
        try:
            result = self.detector.train_advanced_models()
            self.root.after(0, lambda: self.training_complete(result))
        except Exception as e:
            self.root.after(0, lambda: self.training_error(str(e)))

    threading.Thread(target=train_thread, daemon=True).start()


def training_complete(self, result):
    """Handle training completion"""
    self.show_progress(False)
    self.update_status(get_text("ai_detector.ml.training_complete"))
    messagebox.showinfo(get_text("ai_detector.ml.training_complete"), get_text("ai_detector.ml.training_success"))


def training_error(self, error):
    """Handle training error"""
    self.show_progress(False)
    self.update_status(get_text("ai_detector.ml.training_failed"))
    messagebox.showerror(get_text("ai_detector.ml.training_error"), get_text("ai_detector.ml.training_failed_msg", error=error))


def show_model_status(self):
    """Show ML model status"""
    status_window = tk.Toplevel(self.root)
    status_window.title(get_text("ai_detector.ml.status_title"))
    status_window.geometry("600x400")
    status_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(status_window, text=get_text("ai_detector.ml.status_header"), style='Title.TLabel').pack(pady=20)

    # Model status info
    status_frame = ttk.Frame(status_window, style='Card.TFrame')
    status_frame.pack(fill='both', expand=True, padx=20, pady=20)

    # Check model availability
    model_info = []

    if hasattr(self.detector, 'advanced_ml_trainer'):
        if hasattr(self.detector.advanced_ml_trainer, 'models') and self.detector.advanced_ml_trainer.models:
            model_info.append(get_text("ai_detector.ml.ensemble_trained", count=len(self.detector.advanced_ml_trainer.models)))
        else:
            model_info.append(get_text("ai_detector.ml.ensemble_not_trained"))

    if hasattr(self.detector, 'predictive_analytics'):
        if hasattr(self.detector.predictive_analytics, 'risk_model') and self.detector.predictive_analytics.risk_model:
            model_info.append(get_text("ai_detector.ml.risk_model_trained"))
        else:
            model_info.append(get_text("ai_detector.ml.risk_model_not_trained"))

    if not model_info:
        model_info.append(get_text("ai_detector.ml.no_models_available"))

    for info in model_info:
        ttk.Label(status_frame, text=info, style='Subtitle.TLabel').pack(anchor='w', padx=20, pady=5)


