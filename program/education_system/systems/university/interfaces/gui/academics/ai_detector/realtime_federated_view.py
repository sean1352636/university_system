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

def create_real_time_monitoring_view(self, parent):
    """Create real-time monitoring tab"""
    monitoring_frame = ttk.Frame(parent)

    monitoring_frame.pack(fill="both", expand=True)

    # Status section
    status_frame = ttk.LabelFrame(monitoring_frame, text=get_text("ai_detector.monitoring.system_status"), padding="10")
    status_frame.pack(fill='x', padx=15, pady=15)

    self.status_label = ttk.Label(status_frame, text=get_text("ai_detector.monitoring.status_ready"))
    self.status_label.pack(anchor='w')

    # Queue monitoring
    queue_frame = ttk.LabelFrame(monitoring_frame, text=get_text("ai_detector.monitoring.processing_queue"), padding="10")
    queue_frame.pack(fill='x', padx=15, pady=(0, 15))

    self.queue_size_label = ttk.Label(queue_frame, text=get_text("ai_detector.monitoring.queue_size", count=0))
    self.queue_size_label.pack(anchor='w')

    self.active_workers_label = ttk.Label(queue_frame, text=get_text("ai_detector.monitoring.active_workers", count=0))
    self.active_workers_label.pack(anchor='w')


def start_real_time_monitoring(self):
    """Start real-time monitoring"""
    try:
        if hasattr(self.detector, 'start_real_time_monitoring'):
            self.detector.start_real_time_monitoring()
            self.start_monitoring_btn.config(state='disabled')
            self.stop_monitoring_btn.config(state='normal')
            self.monitoring_status_label.config(text=get_text("ai_detector.monitoring.status_running"))
            self.update_status(get_text("ai_detector.monitoring.started"))

            # Start periodic queue status updates
            self.update_queue_status()
        else:
            messagebox.showwarning(get_text("common.warning"), get_text("ai_detector.monitoring.not_available"))
    except Exception as e:
        messagebox.showerror(get_text("common.error"), get_text("ai_detector.monitoring.start_failed", error=str(e)))


def stop_real_time_monitoring(self):
    """Stop real-time monitoring"""
    try:
        if hasattr(self.detector, 'stop_real_time_monitoring'):
            self.detector.stop_real_time_monitoring()
            self.start_monitoring_btn.config(state='normal')
            self.stop_monitoring_btn.config(state='disabled')
            self.monitoring_status_label.config(text=get_text("ai_detector.monitoring.status_stopped"))
            self.update_status(get_text("ai_detector.monitoring.stopped"))
        else:
            messagebox.showwarning(get_text("common.warning"), get_text("ai_detector.monitoring.not_available"))
    except Exception as e:
        messagebox.showerror(get_text("common.error"), get_text("ai_detector.monitoring.stop_failed", error=str(e)))


def update_queue_status(self):
    """Update queue status display"""
    try:
        if hasattr(self.detector, 'realtime_processor'):
            queue_size = len(self.detector.realtime_processor.processing_queue)
            active_workers = len(self.detector.realtime_processor.workers)

            self.queue_size_label.config(text=get_text("ai_detector.monitoring.queue_size", count=queue_size))
            self.active_workers_label.config(text=get_text("ai_detector.monitoring.active_workers", count=active_workers))

            # Schedule next update if monitoring is running
            if self.detector.realtime_processor.is_running:
                self.root.after(5000, self.update_queue_status)  # Update every 5 seconds
    except Exception:
        pass


def create_federated_learning_view(self, parent):
    """Create federated learning tab - MISSING"""
    federated_frame = ttk.Frame(parent)

    federated_frame.pack(fill="both", expand=True)

    # Federated learning card
    federated_card = ttk.Frame(federated_frame, style='Card.TFrame')
    federated_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(federated_card, text=get_text("ai_detector.federated.title"), style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Institution setup
    setup_frame = ttk.LabelFrame(federated_card, text=get_text("ai_detector.federated.institution_setup"), padding=15)
    setup_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(setup_frame, text=get_text("ai_detector.federated.institution_id")).pack(side='left')
    self.institution_id_var = tk.StringVar()
    ttk.Entry(setup_frame, textvariable=self.institution_id_var, width=20).pack(side='left', padx=(5, 15))

    ttk.Button(setup_frame, text=get_text("ai_detector.federated.initialize"),
              command=self.initialize_federation).pack(side='right')

    # Model contribution
    contrib_frame = ttk.LabelFrame(federated_card, text=get_text("ai_detector.federated.model_contribution"), padding=15)
    contrib_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(contrib_frame, text=get_text("ai_detector.federated.contribute_update"),
              command=self.contribute_model_update).pack(side='left', padx=(0, 10))
    ttk.Button(contrib_frame, text=get_text("ai_detector.federated.download_global"),
              command=self.download_global_model).pack(side='left')


def initialize_federation(self):
    """Initialize federated learning"""
    institution_id = self.institution_id_var.get()
    if not institution_id:
        messagebox.showwarning(get_text("common.warning"), get_text("ai_detector.federated.enter_institution_id"))
        return

    try:
        federation_config = {
            'privacy_budget': 1.0,
            'aggregation_method': 'federated_avg'
        }

        if hasattr(self.detector, 'configure_federated_learning'):
            self.detector.configure_federated_learning(institution_id, federation_config)
            messagebox.showinfo(get_text("common.success"), get_text("ai_detector.federated.initialized", institution_id=institution_id))
            self.update_status(get_text("ai_detector.federated.configured"))
        else:
            messagebox.showwarning(get_text("common.warning"), get_text("ai_detector.federated.not_available"))
    except Exception as e:
        messagebox.showerror(get_text("common.error"), get_text("ai_detector.federated.init_failed", error=str(e)))


def contribute_model_update(self):
    """Contribute model update to federation"""
    try:
        if hasattr(self.detector, 'federated_learning'):
            # This would require actual model weights - simplified for demo
            messagebox.showinfo(get_text("common.info"), get_text("ai_detector.federated.requires_trained_models"))
        else:
            messagebox.showwarning(get_text("common.warning"), get_text("ai_detector.federated.not_available"))
    except Exception as e:
        messagebox.showerror(get_text("common.error"), get_text("ai_detector.federated.contribute_failed", error=str(e)))


def download_global_model(self):
    """Download global federated model"""
    try:
        if hasattr(self.detector, 'federated_learning'):
            # This would download and integrate global model weights
            messagebox.showinfo(get_text("common.info"), get_text("ai_detector.federated.requires_federation_setup"))
        else:
            messagebox.showwarning(get_text("common.warning"), get_text("ai_detector.federated.not_available"))
    except Exception as e:
        messagebox.showerror(get_text("common.error"), get_text("ai_detector.federated.download_failed", error=str(e)))


