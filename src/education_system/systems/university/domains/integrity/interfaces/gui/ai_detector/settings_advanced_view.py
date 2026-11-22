"""Settings and the Advanced page.

* **Settings** — the integrity settings the detector uses (integrity
  officers change them): the strength at which a reading waits for review,
  the fewest words a reading needs, and whether submissions are read
  automatically. Module staff turn readings on or off for their own
  modules.
* **Advanced** — training the review-outcome model, its status, batch
  processing and exports.
"""

import logging
import threading

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.platform.delivery.gui.tk_threads import start_thread, ui

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


def _setting(key):
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    conn = common._connect()
    try:
        return integrity_access.setting(conn, key)
    finally:
        conn.close()


def create_settings_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Settings", style="Title.TLabel").pack(anchor="w", padx=15,
                                                               pady=(15, 6))
    box = ttk.LabelFrame(frame, text="For everyone (integrity officers change these)",
                         padding=10)
    box.pack(fill="x", padx=15, pady=6)

    row = ttk.Frame(box)
    row.pack(fill="x", pady=3)
    ttk.Label(row, text="Strength at which a reading waits for review:").pack(side="left")
    self.threshold_var = tk.DoubleVar(value=float(_setting("ai_review_threshold")))
    scale = ttk.Scale(row, from_=0.1, to=1.0, variable=self.threshold_var, orient="horizontal",
                      length=260)
    scale.pack(side="left", padx=8)
    self.threshold_label = ttk.Label(row, text=f"{self.threshold_var.get():.2f}")
    self.threshold_label.pack(side="left")
    self.threshold_var.trace_add("write", lambda *_a: self.threshold_label.config(
        text=f"{self.threshold_var.get():.2f}"))

    row = ttk.Frame(box)
    row.pack(fill="x", pady=3)
    ttk.Label(row, text="Fewest words of the student's own prose for a reading:").pack(
        side="left")
    self.min_words_var = tk.IntVar(value=int(float(_setting("ai_min_words"))))
    words = ttk.Spinbox(row, from_=50, to=2000, increment=50, width=6,
                        textvariable=self.min_words_var)
    words.pack(side="left", padx=8)

    self.auto_check_var = tk.BooleanVar(value=_setting("ai_auto_check") == "1")
    auto = ttk.Checkbutton(box, text="Take a reading automatically when a student submits",
                           variable=self.auto_check_var)
    auto.pack(anchor="w", pady=3)
    apply_btn = ttk.Button(box, text="Save", command=self.apply_settings)
    apply_btn.pack(anchor="e")
    common.officer_only(self, scale, words, auto, apply_btn)

    module_box = ttk.LabelFrame(frame, text="Your modules", padding=10)
    module_box.pack(fill="x", padx=15, pady=6)
    ttk.Label(module_box, text="Module").pack(side="left")
    self.settings_module = common.IdPicker(module_box, common.modules(self), width=34)
    self.settings_module.pack(side="left", padx=6)
    self.module_ai_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(module_box, text="AI-writing readings on",
                    variable=self.module_ai_var).pack(side="left", padx=6)
    ttk.Button(module_box, text="Save", command=lambda: _save_module(self)).pack(side="left")

    def chosen(_event=None):
        module = self.settings_module.value()
        if module:
            found = common.call(self, self.detector.get_course_ai_detection, module, quiet=True)
            self.module_ai_var.set(bool(found))

    self.settings_module.bind("<<ComboboxSelected>>", chosen)

    checks = ttk.LabelFrame(frame, text="Informational checks in a full reading (for you, this "
                                        "session)", padding=10)
    checks.pack(fill="x", padx=15, pady=6)
    ttk.Label(checks, wraplength=850, text=(
        "These add context beside the indicators and never change a reading's strength. Turn "
        "off the slower ones while reading many texts.")).grid(row=0, column=0, columnspan=3,
                                                              sticky="w")
    methods = getattr(self.detector, "detection_methods", {}) or {}
    self.method_vars = {}
    for i, (key, label) in enumerate(METHOD_LABELS.items()):
        var = tk.BooleanVar(value=bool(methods.get(key, True)))
        self.method_vars[key] = var
        ttk.Checkbutton(checks, text=label, variable=var,
                        command=lambda k=key: _set_method(self, k)).grid(
            row=1 + i // 3, column=i % 3, sticky="w", padx=(0, 20), pady=3)


METHOD_LABELS = {
    "citation_verification": "Check citations",
    "disguised_characters": "Disguised characters",
    "paraphrase_tools": "Paraphrasing-tool patterns",
    "prompt_artifacts": "Leftover prompt text",
    "behavioral_analysis": "Editor behaviour (when supplied)",
    "temporal_analysis": "Writing time (when supplied)",
}


def _set_method(self, key):
    self.detector.detection_methods[key] = bool(self.method_vars[key].get())
    self.update_status(f"{METHOD_LABELS[key]}: {'on' if self.method_vars[key].get() else 'off'} "
                       "for this session")


def _save_module(self):
    module = self.settings_module.value()
    if not module:
        messagebox.showwarning(common.TITLE, "Choose the module.", parent=self.root)
        return
    out = common.call(self, self.detector.set_course_ai_detection, module,
                      bool(self.module_ai_var.get()))
    if out is not None and not common.result_failed(self, out):
        self.update_status(f"AI-writing readings {'on' if self.module_ai_var.get() else 'off'} "
                           f"for {module}")


def apply_settings(self):
    """Save the integrity settings (integrity officers)."""
    from education_system.systems.university.application.integrity import (
        access as integrity_access,
    )
    conn = common._connect()
    try:
        who = integrity_access.from_user(conn, self.user)
        if who is None:
            raise PermissionError("Sign in again")
        integrity_access.set_setting(conn, who, "ai_review_threshold",
                                     f"{float(self.threshold_var.get()):.2f}")
        integrity_access.set_setting(conn, who, "ai_min_words", str(int(self.min_words_var.get())))
        integrity_access.set_setting(conn, who, "ai_auto_check",
                                     "1" if self.auto_check_var.get() else "0")
        conn.commit()
    except (PermissionError, ValueError) as exc:
        conn.rollback()
        messagebox.showerror(common.TITLE, str(exc), parent=self.root)
        return
    finally:
        conn.close()
    messagebox.showinfo(common.TITLE, "Settings saved.", parent=self.root)
    self.update_status("Settings saved")


def create_advanced_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Advanced", style="Title.TLabel").pack(anchor="w", padx=15, pady=15)
    self.create_ml_section(frame)
    self.create_batch_processing_section(frame)
    self.create_export_section(frame)


def create_ml_section(self, parent):
    box = ttk.LabelFrame(parent, text="Review-outcome model", padding=10)
    box.pack(fill="x", padx=15, pady=(0, 10))
    ttk.Label(box, wraplength=850, text=(
        "Learns from what reviewers decided; advisory only (its estimate is shown beside a "
        "reading). Full controls are under Model Management.")).pack(anchor="w")
    row = ttk.Frame(box)
    row.pack(fill="x", pady=(6, 0))
    train = ttk.Button(row, text="Train a new version", command=self.train_models)
    train.pack(side="left", padx=(0, 6))
    ttk.Button(row, text="Model status", command=self.show_model_status).pack(side="left")
    common.officer_only(self, train)


def train_models(self):
    """Train the review-outcome model (integrity officers)."""
    self.update_status("Training…")
    self.show_progress(True)
    detector = self.detector

    def run():
        try:
            out = detector.retrain_detection_model()
        except Exception as e:
            logger.exception("Model retraining failed")
            ui(self.root, self.training_error, str(e))
            return
        ui(self.root, self.training_complete, out)

    start_thread(self.root, run)


def training_complete(self, result):
    self.show_progress(False)
    if isinstance(result, dict) and result.get("success") is False:
        self.training_error(result.get("error"))
        return
    self.update_status("Model trained")
    common.text_window(self, "New model version", result, 640, 460)


def training_error(self, error):
    self.show_progress(False)
    self.update_status("Training did not complete")
    messagebox.showerror(common.TITLE, f"Not trained: {error}", parent=self.root)


def show_model_status(self):
    summary = common.call(self, self.detector.training_data_summary, quiet=True) or {}
    versions = (common.call(self, self.detector.list_model_versions, quiet=True) or {}).get(
        "versions", [])
    active = next((v for v in versions if v.get("is_active")), None)
    common.text_window(self, "Model status", {
        "active version": active or "none — no estimate is shown beside readings",
        "versions held": len(versions),
        "training data": summary,
        "components that did not start": self.detector.component_errors or "none",
    }, 680, 480)
