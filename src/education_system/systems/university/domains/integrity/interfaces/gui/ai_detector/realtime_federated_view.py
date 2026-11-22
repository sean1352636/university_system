"""Real-time monitor and federated learning.

* **Real-time monitor** — the detector's processing queue
  (``processing_queue``): start and stop its workers, queue a text for a
  student on a module, look for submissions with no reading yet ("sweep"),
  and see waiting / processing / done / failed counts and throughput,
  refreshed every five seconds while the view is open.
* **Federated learning** — share what the reviewed-outcome model learned
  with partner institutions without sharing any student data: set this
  institution's id, export the active model as a noised update file (the
  privacy budget ε sets the noise), import a partner's file (checked
  against its checksum), and average imported updates with the local model
  into a new, inactive version (evaluate and activate it under Model
  Management). Integrity officers only.
"""

import logging

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


# ── real-time monitor ───────────────────────────────────────────────────


def create_real_time_monitoring_view(self, parent):
    """The processing queue: controls, live status and recent failures."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)

    controls = ttk.LabelFrame(frame, text="Processor", padding=10)
    controls.pack(fill="x", padx=15, pady=(15, 8))
    self.start_monitoring_btn = ttk.Button(controls, text="▶ Start workers",
                                           command=self.start_real_time_monitoring)
    self.start_monitoring_btn.pack(side="left", padx=(0, 6))
    self.stop_monitoring_btn = ttk.Button(controls, text="⏹ Stop workers",
                                          command=self.stop_real_time_monitoring)
    self.stop_monitoring_btn.pack(side="left", padx=(0, 6))
    ttk.Label(controls, text="Workers:").pack(side="left", padx=(12, 2))
    self.worker_count_var = tk.IntVar(value=2)
    ttk.Spinbox(controls, from_=1, to=8, width=4,
                textvariable=self.worker_count_var).pack(side="left")
    ttk.Button(controls, text="🔎 Queue submissions without a reading",
               command=self.sweep_missing_readings).pack(side="left", padx=(12, 6))
    ttk.Button(controls, text="➕ Queue a text…",
               command=self.queue_text_for_reading).pack(side="left")

    status = ttk.LabelFrame(frame, text="Status", padding=10)
    status.pack(fill="x", padx=15, pady=8)
    self.monitoring_status_label = ttk.Label(status, text="Status: —")
    self.monitoring_status_label.pack(anchor="w")
    self.queue_size_label = ttk.Label(status, text="Queue: —")
    self.queue_size_label.pack(anchor="w")
    self.active_workers_label = ttk.Label(status, text="Throughput: —")
    self.active_workers_label.pack(anchor="w")

    failures = ttk.LabelFrame(frame, text="Recent failures", padding=6)
    failures.pack(fill="both", expand=True, padx=15, pady=(8, 15))
    self.queue_failures_tree = ttk.Treeview(failures, columns=("id", "at", "error"),
                                            show="headings", height=8)
    for col, label, width in (("id", "Item", 230), ("at", "When", 150),
                              ("error", "Error", 520)):
        self.queue_failures_tree.heading(col, text=label)
        self.queue_failures_tree.column(col, width=width, anchor="w")
    self.queue_failures_tree.pack(fill="both", expand=True)
    self.update_queue_status()


def _processor(self):
    processor = getattr(self.detector, "realtime_processor", None)
    if processor is None:
        error = self.detector.component_errors.get("realtime_processor", "not available")
        raise ValueError(f"The processor did not start: {error}")
    return processor


def start_real_time_monitoring(self):
    """Start the processor's workers (staff)."""
    processor = common.call(self, _processor, self)
    if processor is None or common.call(self, self.detector.require_staff) is None:
        return
    count = max(1, min(8, int(self.worker_count_var.get() or 2)))
    if not common.call(self, lambda: processor.start_real_time_processing(count) or True):
        return
    self.update_status(f"Processor running with {count} worker(s)")
    self.update_queue_status()


def stop_real_time_monitoring(self):
    """Stop the processor's workers."""
    processor = common.call(self, _processor, self)
    if processor is None:
        return
    common.call(self, processor.stop_real_time_processing)
    self.update_status("Processor stopped")
    self.update_queue_status()


def sweep_missing_readings(self):
    """Queue assignment submissions that have no reading yet."""
    processor = common.call(self, _processor, self)
    if processor is None:
        return
    queued = common.call(self, processor.sweep_now)
    if queued is not None:
        messagebox.showinfo(common.TITLE, f"{queued} submission(s) queued for a reading.",
                            parent=self.root)
        self.update_queue_status()


def queue_text_for_reading(self):
    """Queue pasted text for a student on a module."""
    processor = common.call(self, _processor, self)
    if processor is None:
        return
    win = tk.Toplevel(self.root)
    win.title("Queue a text for a reading")
    win.transient(self.root)
    form = ttk.Frame(win, padding=10)
    form.pack(fill="both", expand=True)
    ttk.Label(form, text="Module").grid(row=0, column=0, sticky="w")
    module = common.IdPicker(form, common.modules(self), width=40)
    module.grid(row=0, column=1, sticky="ew", pady=2)
    ttk.Label(form, text="Student").grid(row=1, column=0, sticky="w")
    student = common.IdPicker(form, (), width=40)
    student.grid(row=1, column=1, sticky="ew", pady=2)
    module.bind("<<ComboboxSelected>>",
                lambda _e: student.set_choices(common.students(module.value())))
    buttons = ttk.Frame(form)
    buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))
    text = tk.Text(form, height=12, width=70, wrap="word")
    text.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=4)
    form.rowconfigure(2, weight=1)
    form.columnconfigure(1, weight=1)

    def queue():
        if not module.value() or not student.value():
            messagebox.showwarning(common.TITLE, "Choose the module and the student.", parent=win)
            return
        body = text.get("1.0", "end").strip()
        if not body:
            messagebox.showwarning(common.TITLE, "Paste the text first.", parent=win)
            return
        task_id = common.call(self, processor.queue_submission,
                              {"text": body, "student_id": student.value(),
                               "module_code": module.value(), "title": "Queued text"})
        if task_id:
            win.destroy()
            self.update_status(f"Queued as {task_id}")
            self.update_queue_status()

    ttk.Button(buttons, text="Queue", command=queue).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right", padx=4)


def update_queue_status(self):
    """Refresh the counts; repeats every 5 s while the view is open."""
    label = getattr(self, "queue_size_label", None)
    if label is None or not label.winfo_exists():
        return
    processor = getattr(self.detector, "realtime_processor", None)
    if processor is None:
        label.config(text="The processor is not available: "
                          + self.detector.component_errors.get("realtime_processor", ""))
        return
    try:
        status = processor.get_status()
    except Exception as exc:
        logger.warning("Processor status failed: %s", exc)
        label.config(text=f"Status unavailable: {exc}")
        return
    running = status.get("running")
    self.monitoring_status_label.config(
        text=f"Status: {'running' if running else 'stopped'} — {status.get('workers', 0)} "
             f"worker(s), since {status.get('started_at') or '—'}")
    label.config(text=f"Queue: {status.get('waiting', 0)} waiting, "
                      f"{status.get('processing', 0)} processing, {status.get('done', 0)} done, "
                      f"{status.get('failed', 0)} failed")
    speed = status.get("seconds_per_item")
    self.active_workers_label.config(
        text=f"Throughput: {status.get('done_last_hour', 0)} in the last hour"
             + (f", {speed:.2f} s each" if speed is not None else "")
             + f"; this session {status.get('processed_this_session', 0)} done, "
               f"{status.get('failed_this_session', 0)} failed")
    self.start_monitoring_btn.config(state="disabled" if running else "normal")
    self.stop_monitoring_btn.config(state="normal" if running else "disabled")
    tree = self.queue_failures_tree
    tree.delete(*tree.get_children())
    for item in status.get("recent_failures", []):
        tree.insert("", "end", values=(item.get("id"), item.get("at"), item.get("error")))
    self.root.after(5000, self.update_queue_status)


# ── federated learning ──────────────────────────────────────────────────


def create_federated_learning_view(self, parent):
    """Institution id, export / import / aggregate updates, and the list."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Federated learning", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                         pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "Partners share model updates, never student data: each update holds only the weights "
        "of a model trained on reviewed outcomes, with noise added for privacy (smaller ε = more "
        "noise). An aggregated model starts inactive; evaluate it on your own outcomes and "
        "activate it under Model Management. Integrity officers only.")).pack(anchor="w",
                                                                              padx=15)

    setup = ttk.LabelFrame(frame, text="This institution", padding=10)
    setup.pack(fill="x", padx=15, pady=8)
    ttk.Label(setup, text="Institution id:").pack(side="left")
    self.institution_id_var = tk.StringVar()
    ttk.Entry(setup, textvariable=self.institution_id_var, width=24).pack(side="left", padx=5)
    init_btn = ttk.Button(setup, text="Save", command=self.initialize_federation)
    init_btn.pack(side="left")

    actions = ttk.LabelFrame(frame, text="Updates", padding=10)
    actions.pack(fill="x", padx=15, pady=8)
    ttk.Label(actions, text="Privacy budget ε:").pack(side="left")
    self.federated_epsilon_var = tk.DoubleVar(value=1.0)
    ttk.Spinbox(actions, from_=0.1, to=10.0, increment=0.1, width=6,
                textvariable=self.federated_epsilon_var).pack(side="left", padx=(4, 12))
    export_btn = ttk.Button(actions, text="📤 Export update…", command=self.contribute_model_update)
    export_btn.pack(side="left", padx=4)
    import_btn = ttk.Button(actions, text="📥 Import partner update…",
                            command=self.import_federated_update)
    import_btn.pack(side="left", padx=4)
    aggregate_btn = ttk.Button(actions, text="🔀 Aggregate selected",
                               command=self.download_global_model)
    aggregate_btn.pack(side="left", padx=4)
    global_btn = ttk.Button(actions, text="🌐 Import a shared global model…",
                            command=self.import_model_weights)
    global_btn.pack(side="left", padx=4)
    common.officer_only(self, init_btn, export_btn, import_btn, aggregate_btn, global_btn)

    listing = ttk.LabelFrame(frame, text="Updates exported and imported", padding=6)
    listing.pack(fill="both", expand=True, padx=15, pady=(8, 15))
    cols = (("update_id", "Id", 50), ("direction", "Direction", 80),
            ("institution_id", "Institution", 130), ("model_version", "Model", 150),
            ("n_samples", "Readings", 80), ("epsilon", "ε", 50),
            ("used_in_version", "Used in", 150), ("created_at", "When", 150))
    self.federated_tree = ttk.Treeview(listing, columns=[c[0] for c in cols], show="headings",
                                       height=10, selectmode="extended")
    for col, label, width in cols:
        self.federated_tree.heading(col, text=label)
        self.federated_tree.column(col, width=width, anchor="w")
    self.federated_tree.pack(fill="both", expand=True)
    _refresh_federated(self)


def _refresh_federated(self):
    fl = getattr(self.detector, "federated_learning", None)
    if fl is None:
        return
    current = common.call(self, lambda: fl.institution_id, quiet=True)
    self.institution_id_var.set(current or "")
    rows = common.call(self, lambda: fl.model_updates) or []
    tree = self.federated_tree
    tree.delete(*tree.get_children())
    for r in rows:
        tree.insert("", "end", iid=str(r["update_id"]),
                    values=[r.get(k) for k in ("update_id", "direction", "institution_id",
                                               "model_version", "n_samples", "epsilon",
                                               "used_in_version", "created_at")])


def _federation(self):
    fl = getattr(self.detector, "federated_learning", None)
    if fl is None:
        raise ValueError("Federated learning is not available: "
                         + self.detector.component_errors.get("federated_learning", ""))
    self.detector.require_officer()
    return fl


def initialize_federation(self):
    """Save this institution's id (it names our update files)."""
    institution_id = self.institution_id_var.get().strip()
    if not institution_id:
        messagebox.showwarning(common.TITLE, "Enter this institution's id.", parent=self.root)
        return
    fl = common.call(self, _federation, self)
    if fl is None:
        return
    if common.call(self, lambda: fl.initialize_federation(institution_id) or True):
        self.update_status(f"Institution id set to {institution_id}")
        _refresh_federated(self)


def contribute_model_update(self):
    """Export the active model as a noised update file."""
    fl = common.call(self, _federation, self)
    if fl is None:
        return
    path = filedialog.asksaveasfilename(parent=self.root, title="Save the update file",
                                        defaultextension=".json",
                                        filetypes=[("Update files", "*.json")])
    if not path:
        return
    out = common.call(self, fl.contribute_model_update,
                      privacy_budget=float(self.federated_epsilon_var.get()), path=path)
    if out:
        messagebox.showinfo(common.TITLE, f"Update saved to {out['path']}\n"
                                          f"Trained on {out['n_samples']} readings, ε = "
                                          f"{out['epsilon']}, noise scale {out['noise_scale']:.4g}"
                                          f"\nChecksum {out['sha256'][:16]}…", parent=self.root)
        _refresh_federated(self)


def import_federated_update(self):
    """Import a partner's update file (checked against its checksum)."""
    fl = common.call(self, _federation, self)
    if fl is None:
        return
    path = filedialog.askopenfilename(parent=self.root, title="Choose a partner's update",
                                      filetypes=[("Update files", "*.json")])
    if not path:
        return
    out = common.call(self, fl.import_model_update, path)
    if out:
        messagebox.showinfo(common.TITLE, f"Imported update {out['update_id']} from "
                                          f"{out.get('institution_id')} ({out['n_samples']} "
                                          "readings).", parent=self.root)
        _refresh_federated(self)


def download_global_model(self):
    """Average the selected imported updates (or every unused one) with the
    local model into a new, inactive version."""
    fl = common.call(self, _federation, self)
    if fl is None:
        return
    chosen = [int(i) for i in self.federated_tree.selection()]
    if chosen:
        rows = {str(r["update_id"]): r for r in (fl.model_updates or [])}
        chosen = [i for i in chosen if rows.get(str(i), {}).get("direction") == "imported"]
    out = common.call(self, fl.aggregate_model_updates, chosen or None)
    if out:
        common.text_window(self, "Aggregated model", out)
        _refresh_federated(self)
