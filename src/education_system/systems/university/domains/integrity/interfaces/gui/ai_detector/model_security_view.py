"""Model management, security and audit.

* **Model management** — the optional model trained only on human review
  outcomes (staff decided "no concern", or the integrity case was upheld /
  dismissed). It is advisory: its estimate is shown beside a reading and
  never sets a flag. Training needs at least 20 reviewed readings with at
  least 5 of each outcome. Versions can be activated, rolled back (with a
  reason), evaluated on the current outcomes, compared, exported and
  imported (checked against their checksum). Training, activation and
  import are for integrity officers.
* **Security & audit** — the detector's activity log and an anonymised
  research extract (integrity officers), a chain-of-custody record for one
  reading (the reviewing staff or an officer), and a subject access (GDPR)
  export for a student (officers). Files are written owner-only under the
  university's exports folder.
"""

import logging
import threading

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.platform.delivery.gui.tk_threads import start_thread, ui

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


# ── model management ────────────────────────────────────────────────────


def create_model_management_view(self, parent):
    """Training data, training, versions, export/import and the cache."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Model management", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                       pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "The model learns only from what reviewers decided. It is advisory: its estimate is "
        "shown beside a reading and never sets a flag or changes the strength.")).pack(
        anchor="w", padx=15)

    training = ttk.LabelFrame(frame, text="Training", padding=10)
    training.pack(fill="x", padx=15, pady=8)
    self.training_status_var = tk.StringVar(value="—")
    ttk.Label(training, textvariable=self.training_status_var, wraplength=850).pack(anchor="w")
    row = ttk.Frame(training)
    row.pack(fill="x", pady=(6, 0))
    ttk.Button(row, text="📋 Training data", command=self._view_training_progress).pack(
        side="left", padx=(0, 6))
    self.activate_after_training_var = tk.BooleanVar(value=False)
    train_btn = ttk.Button(row, text="🧠 Train a new version",
                           command=self.retrain_detection_model)
    train_btn.pack(side="left", padx=(0, 6))
    ttk.Checkbutton(row, text="activate it", variable=self.activate_after_training_var).pack(
        side="left")

    versions = ttk.LabelFrame(frame, text="Versions", padding=6)
    versions.pack(fill="both", expand=True, padx=15, pady=8)
    head = ttk.Frame(versions)
    head.pack(fill="x")
    ttk.Label(head, text="Active:").pack(side="left")
    self.current_version_var = tk.StringVar(value="—")
    ttk.Label(head, textvariable=self.current_version_var, font=("Segoe UI", 10, "bold")).pack(
        side="left", padx=5)
    buttons = ttk.Frame(versions)
    buttons.pack(side="bottom", fill="x", pady=(6, 0))
    cols = (("version", "Version", 170), ("source", "Source", 80), ("active", "Active", 55),
            ("training_samples", "Readings", 70), ("created_at", "Created", 140),
            ("trained_by", "By", 90), ("metrics", "Results", 420))
    self.model_versions_tree = ttk.Treeview(versions, columns=[c[0] for c in cols],
                                            show="headings", height=7, selectmode="extended")
    for col, label, width in cols:
        self.model_versions_tree.heading(col, text=label)
        self.model_versions_tree.column(col, width=width, anchor="w")
    self.model_versions_tree.pack(fill="both", expand=True)
    activate_btn = ttk.Button(buttons, text="✔ Activate selected",
                              command=lambda: _activate_selected(self))
    activate_btn.pack(side="left", padx=(0, 6))
    rollback_btn = ttk.Button(buttons, text="↩ Roll back…", command=self.rollback_model_version)
    rollback_btn.pack(side="left", padx=(0, 6))
    deactivate_btn = ttk.Button(buttons, text="⏸ Use no model…",
                                command=lambda: _deactivate(self))
    deactivate_btn.pack(side="left", padx=(0, 6))
    evaluate_btn = ttk.Button(buttons, text="🧪 Evaluate selected",
                              command=lambda: _evaluate_selected(self))
    evaluate_btn.pack(side="left", padx=(0, 6))
    ttk.Button(buttons, text="⚖ Compare two selected",
               command=self.compare_model_versions).pack(side="left", padx=(0, 6))
    ttk.Button(buttons, text="✍ Try a text on selected…",
               command=self.try_text_on_versions).pack(side="left", padx=(0, 6))
    ttk.Button(buttons, text="📤 Export selected…", command=self.export_model_weights).pack(
        side="left", padx=(0, 6))
    import_btn = ttk.Button(buttons, text="📥 Import…", command=self.import_model_weights)
    import_btn.pack(side="left")

    cache = ttk.LabelFrame(frame, text="Cache", padding=10)
    cache.pack(fill="x", padx=15, pady=(8, 15))
    self.cache_size_var = tk.StringVar(value="Cache: —")
    ttk.Label(cache, textvariable=self.cache_size_var).pack(side="left")
    ttk.Button(cache, text="Clear", command=self.clear_analysis_cache).pack(side="right")
    ttk.Button(cache, text="Refresh", command=self._refresh_cache_info).pack(side="right", padx=6)

    common.officer_only(self, train_btn, activate_btn, rollback_btn, deactivate_btn,
                        evaluate_btn, import_btn)
    self._load_model_version()
    self._refresh_cache_info()


def _selected_versions(self):
    return [self.model_versions_tree.item(i)["values"][0]
            for i in self.model_versions_tree.selection()]


def _load_model_version(self):
    """Fill the versions list and the active version."""
    tree = self.__dict__.get("model_versions_tree")
    out = common.call(self, self.detector.list_model_versions, quiet=True) or {}
    active = common.call(self, self.detector.get_model_version, quiet=True)
    self.current_version_var.set(active or "none (no model estimate is shown)")
    summary = common.call(self, self.detector.training_data_summary, quiet=True) or {}
    if summary.get("success"):
        self.training_status_var.set(
            f"{summary.get('labelled', 0)} reviewed reading(s) with a settled outcome: "
            f"{summary.get('confirmed', 0)} upheld, {summary.get('not_confirmed', 0)} not. "
            + ("Enough to train." if summary.get("enough") else
               f"Training needs at least {summary.get('needed', 20)} with "
               f"{summary.get('needed_per_outcome', 5)} of each."))
    if tree is None:
        return
    tree.delete(*tree.get_children())
    if out.get("error"):
        self.training_status_var.set(out["error"])
    for v in out.get("versions", []):
        metrics = v.get("metrics") or {}
        shown = ", ".join(f"{k} {metrics[k]:.2f}" for k in ("accuracy", "precision", "recall",
                                                           "false_positive_rate", "auc")
                          if isinstance(metrics.get(k), (int, float)))
        tree.insert("", "end", values=(v.get("version"), v.get("source"),
                                       "yes" if v.get("is_active") or v.get("active") else "",
                                       v.get("training_samples"), v.get("created_at"),
                                       v.get("trained_by"), shown or "not evaluated"))


def _view_training_progress(self):
    """What the model can learn from today."""
    summary = common.call(self, self.detector.training_data_summary)
    if summary and not common.result_failed(self, summary):
        common.text_window(self, "Training data", summary, 600, 420)


def _refresh_cache_info(self):
    stats = common.call(self, self.detector.get_cache_statistics, quiet=True) or {}
    size = common.call(self, self.detector.get_cache_size, quiet=True) or 0
    self.cache_size_var.set(f"Cache: {stats.get('total_entries', 0)} entr(ies), "
                            f"{size / 1024:.1f} KB of models loaded")


def retrain_detection_model(self):
    """Train a new version on the settled review outcomes (officers)."""
    if not messagebox.askyesno(common.TITLE, "Train a new version on the reviewed outcomes?",
                               parent=self.root):
        return
    activate = bool(self.activate_after_training_var.get())
    self.training_status_var.set("Training…")
    detector = self.detector

    def train():
        try:
            out = detector.retrain_detection_model(activate=activate)
        except Exception as e:
            logger.exception("Model retraining failed")
            out = {"success": False, "error": str(e)}
        ui(self.root, _training_done, self, out)

    start_thread(self.root, train)


def _training_done(self, out):
    if common.result_failed(self, out):
        self.training_status_var.set(f"Not trained: {out.get('error')}")
        return
    self.training_status_var.set(f"Trained {out.get('model_version')} in "
                                 f"{out.get('training_time')} s"
                                 + (" and activated" if out.get("active") else ""))
    common.text_window(self, "New model version", out, 640, 460)
    self._load_model_version()


def _activate_selected(self):
    chosen = _selected_versions(self)
    if len(chosen) != 1:
        messagebox.showwarning(common.TITLE, "Select one version.", parent=self.root)
        return
    reason = simpledialog.askstring(common.TITLE, f"Why activate {chosen[0]}?",
                                    parent=self.root)
    if not reason:
        return
    out = common.call(self, self.detector.activate_model_version, chosen[0], reason)
    if out and not common.result_failed(self, out):
        self.update_status(f"{chosen[0]} is now active")
        self._load_model_version()


def _deactivate(self):
    reason = simpledialog.askstring(common.TITLE, "Why stop using the model?", parent=self.root)
    if not reason:
        return
    out = common.call(self, self.detector.deactivate_model, reason)
    if out and not common.result_failed(self, out):
        self._load_model_version()


def _evaluate_selected(self):
    chosen = _selected_versions(self)
    if len(chosen) != 1:
        messagebox.showwarning(common.TITLE, "Select one version.", parent=self.root)
        return
    out = common.call(self, self.detector.evaluate_model_version, chosen[0])
    if out and not common.result_failed(self, out):
        common.text_window(self, f"Evaluation of {chosen[0]}", out, 600, 420)
        self._load_model_version()


def rollback_model_version(self):
    """Go back to an earlier version, with the reason."""
    out = common.call(self, self.detector.list_model_versions) or {}
    earlier = [v["version"] for v in out.get("versions", [])
               if not (v.get("is_active") or v.get("active"))]
    if not earlier:
        messagebox.showinfo(common.TITLE, "There is no earlier version to go back to.",
                            parent=self.root)
        return
    win = tk.Toplevel(self.root)
    win.title("Roll back the model")
    win.transient(self.root)
    form = ttk.Frame(win, padding=10)
    form.pack(fill="both", expand=True)
    ttk.Label(form, text="Version").grid(row=0, column=0, sticky="w")
    choice = ttk.Combobox(form, values=earlier, state="readonly", width=30)
    choice.grid(row=0, column=1, pady=3)
    ttk.Label(form, text="Reason").grid(row=1, column=0, sticky="w")
    reason = ttk.Entry(form, width=40)
    reason.grid(row=1, column=1, pady=3)

    def go():
        if not choice.get() or not reason.get().strip():
            messagebox.showwarning(common.TITLE, "Choose the version and give the reason.",
                                   parent=win)
            return
        done = common.call(self, self.detector.rollback_model_version, choice.get(),
                           reason.get().strip())
        if done and not common.result_failed(self, done):
            win.destroy()
            self.update_status(f"Rolled back to {choice.get()}")
            self._load_model_version()

    ttk.Button(form, text="Roll back", command=go).grid(row=2, column=1, sticky="e", pady=6)


def compare_model_versions(self):
    """Both selected versions on the same current outcomes."""
    chosen = _selected_versions(self) if self.__dict__.get("model_versions_tree") else []
    if len(chosen) != 2:
        messagebox.showwarning(common.TITLE, "Select two versions to compare.", parent=self.root)
        return
    out = common.call(self, self.detector.compare_model_versions, chosen[0], chosen[1])
    if out and not common.result_failed(self, out):
        common.text_window(self, f"{chosen[0]} against {chosen[1]}", out, 700, 480)


def try_text_on_versions(self):
    """Paste a text and see each selected version's estimate for it side by
    side (the text is read, not stored)."""
    chosen = _selected_versions(self) if self.__dict__.get("model_versions_tree") else []
    if not chosen:
        messagebox.showwarning(common.TITLE, "Select one or more versions first.",
                               parent=self.root)
        return
    win = tk.Toplevel(self.root)
    win.title("Try a text on " + ", ".join(chosen))
    win.geometry(f"{min(760, win.winfo_screenwidth() - 60)}x{min(560, win.winfo_screenheight() - 100)}")
    win.transient(self.root)
    bar = ttk.Frame(win, padding=6)
    bar.pack(side="bottom", fill="x")
    result_box = scrolledtext.ScrolledText(win, height=8, wrap="word", state="disabled")
    result_box.pack(side="bottom", fill="x", padx=8)
    ttk.Label(win, text="Text to try (it is read, not stored). An estimate is how often "
                        "readings like it were confirmed by a person under that version — "
                        "context for choosing a version, not a judgement on the text.",
              wraplength=700).pack(anchor="w", padx=8, pady=(8, 2))
    text_box = scrolledtext.ScrolledText(win, height=10, wrap="word")
    text_box.pack(fill="both", expand=True, padx=8)

    def run():
        text = text_box.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning(common.TITLE, "Paste a text first.", parent=win)
            return
        out = common.call(self, self.detector.estimate_text_with_versions, text, chosen)
        if not out or common.result_failed(self, out):
            return
        lines = [f"Reading: {out.get('level')}", ""]
        for name in chosen:
            value = out.get(name)
            lines.append(f"{name}: " + (f"{value:.0%}" if isinstance(value, float)
                                        else str(value)))
        result_box.configure(state="normal")
        result_box.delete("1.0", "end")
        result_box.insert("1.0", "\n".join(lines))
        result_box.configure(state="disabled")

    ttk.Button(bar, text="Try it", command=run).pack(side="left")
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")


def export_model_weights(self):
    """Export the selected (or active) version's weights as a JSON file."""
    chosen = _selected_versions(self) if self.__dict__.get("model_versions_tree") else []
    path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                        filetypes=[("Model files", "*.json")],
                                        title="Save the model weights")
    if not path:
        return
    out = common.call(self, self.detector.export_weights, path,
                      chosen[0] if len(chosen) == 1 else None)
    if out and not common.result_failed(self, out):
        messagebox.showinfo(common.TITLE, f"Saved {out.get('version')} to {out.get('path')}\n"
                                          f"Checksum {str(out.get('sha256'))[:16]}…",
                            parent=self.root)


def import_model_weights(self):
    """Import a version from a weights file (checked; starts inactive)."""
    path = filedialog.askopenfilename(parent=self.root, filetypes=[("Model files", "*.json")],
                                      title="Choose a model weights file")
    if not path:
        return
    out = common.call(self, self.detector.import_weights, path, False)
    if out and not common.result_failed(self, out):
        messagebox.showinfo(common.TITLE, f"Imported as {out.get('version')}. Evaluate it on "
                                          "your own outcomes before activating it.",
                            parent=self.root)
        self._load_model_version()


def clear_analysis_cache(self):
    out = common.call(self, self.detector.clear_cache)
    if out is not None:
        self.analysis_results = {}
        self._refresh_cache_info()
        self.update_status("Cache cleared")


# ── security & audit ────────────────────────────────────────────────────


def create_security_audit_view(self, parent):
    """Activity log, chain of custody, anonymised extract and GDPR export."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Security & audit", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                       pady=(15, 5))
    activity = ttk.LabelFrame(frame, text="Activity log (integrity officers)", padding=8)
    activity.pack(fill="both", expand=True, padx=15, pady=(0, 8))
    controls = ttk.Frame(activity)
    controls.pack(fill="x", pady=(0, 6))
    ttk.Label(controls, text="User:").pack(side="left")
    self.audit_user_var = tk.StringVar()
    ttk.Entry(controls, textvariable=self.audit_user_var, width=16).pack(side="left", padx=4)
    ttk.Label(controls, text="Days:").pack(side="left")
    self.audit_days_var = tk.IntVar(value=30)
    ttk.Spinbox(controls, from_=1, to=3650, width=6, textvariable=self.audit_days_var).pack(
        side="left", padx=4)
    view_btn = ttk.Button(controls, text="Show", command=self.view_user_activity_log)
    view_btn.pack(side="left", padx=4)
    export_btn = ttk.Button(controls, text="Export…", command=self._export_activity_log)
    export_btn.pack(side="left")
    self.activity_summary_var = tk.StringVar()
    ttk.Label(controls, textvariable=self.activity_summary_var).pack(side="left", padx=10)
    cols = (("timestamp", "When", 150), ("user_id", "Who", 100), ("action", "Action", 160),
            ("target_id", "About", 110), ("details", "Details", 360))
    self.activity_tree = ttk.Treeview(activity, columns=[c[0] for c in cols], show="headings",
                                      height=8)
    for col, label, width in cols:
        self.activity_tree.heading(col, text=label)
        self.activity_tree.column(col, width=width, anchor="w")
    self.activity_tree.pack(fill="both", expand=True)

    custody = ttk.LabelFrame(frame, text="Chain of custody for one reading", padding=8)
    custody.pack(fill="x", padx=15, pady=8)
    ttk.Label(custody, text="Reading's submission id:").pack(side="left")
    self.custody_submission_var = tk.StringVar()
    ttk.Entry(custody, textvariable=self.custody_submission_var, width=12).pack(side="left",
                                                                               padx=5)
    ttk.Label(custody, text="Case reference (optional):").pack(side="left")
    self.custody_case_var = tk.StringVar()
    ttk.Entry(custody, textvariable=self.custody_case_var, width=14).pack(side="left", padx=5)
    ttk.Button(custody, text="Export record", command=self.export_chain_of_custody).pack(
        side="left", padx=6)

    privacy = ttk.LabelFrame(frame, text="Data protection (integrity officers)", padding=8)
    privacy.pack(fill="x", padx=15, pady=(8, 15))
    ttk.Label(privacy, text="Student number:").pack(side="left")
    self.privacy_student_var = tk.StringVar()
    ttk.Entry(privacy, textvariable=self.privacy_student_var, width=14).pack(side="left", padx=5)
    gdpr_btn = ttk.Button(privacy, text="Subject access export",
                          command=self.generate_gdpr_data_export)
    gdpr_btn.pack(side="left", padx=4)
    anon_btn = ttk.Button(privacy, text="Anonymised research extract…",
                          command=self.anonymize_student_data)
    anon_btn.pack(side="left", padx=4)
    common.officer_only(self, view_btn, export_btn, gdpr_btn, anon_btn)


def view_user_activity_log(self):
    out = common.call(self, self.detector.view_user_activity_log,
                      self.audit_user_var.get().strip() or None, None,
                      int(self.audit_days_var.get() or 30))
    if out is None:
        return
    tree = self.activity_tree
    tree.delete(*tree.get_children())
    for a in out.get("activities", []):
        tree.insert("", "end", values=(a.get("timestamp"), a.get("user_id"), a.get("action"),
                                       a.get("target_id"), a.get("details")))
    summary = out.get("summary", {})
    self.activity_summary_var.set(f"{summary.get('total', 0)} action(s) by "
                                  f"{summary.get('unique_users', 0)} people; most active "
                                  f"{summary.get('most_active_user', '—')}")


def _export_activity_log(self):
    """Save the shown log as CSV (owner-only)."""
    import csv
    import os
    if not self.activity_tree.get_children():
        messagebox.showinfo(common.TITLE, "Show the log first.", parent=self.root)
        return
    path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                        filetypes=[("CSV files", "*.csv")])
    if not path:
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["When", "Who", "Action", "About", "Details"])
        for item in self.activity_tree.get_children():
            writer.writerow(self.activity_tree.item(item)["values"])
    os.chmod(path, 0o600)
    self.update_status(f"Activity log saved to {path}")


def export_chain_of_custody(self):
    """The custody record of one reading, saved owner-only."""
    submission_id = self.custody_submission_var.get().strip()
    if not submission_id.isdigit():
        messagebox.showwarning(common.TITLE, "Enter the reading's submission id (a number; it "
                                             "is shown in History).", parent=self.root)
        return
    out = common.call(self, self.detector.export_chain_of_custody, int(submission_id),
                      case_reference=self.custody_case_var.get().strip() or None)
    if out and not common.result_failed(self, out):
        messagebox.showinfo(common.TITLE, f"Record {out['document_id']} saved to\n"
                                          f"{out['export_path']}\n{out['custody_entries']} "
                                          f"entries, {out['time_span']}", parent=self.root)


def anonymize_student_data(self):
    """An anonymised extract of readings for research (the key file is kept
    apart). Scope: one student, one module, or everything."""
    student = self.privacy_student_var.get().strip()
    choice = simpledialog.askstring(
        common.TITLE, "Extract which readings? Type 'student' (the number above), a module "
                      "code, or 'all'.", parent=self.root)
    if not choice:
        return
    choice = choice.strip()
    if choice.lower() == "student":
        if not student:
            messagebox.showwarning(common.TITLE, "Enter the student number first.",
                                   parent=self.root)
            return
        scope = {"type": "student", "student_id": student}
    elif choice.lower() == "all":
        scope = {"type": "all"}
    else:
        scope = {"type": "course", "course_code": choice}
    out = common.call(self, self.detector.anonymize_student_data, scope)
    if out and not common.result_failed(self, out):
        messagebox.showinfo(common.TITLE, f"{out['records_processed']} reading(s) extracted to\n"
                                          f"{out['output_path']}\nKey file (keep it separate):\n"
                                          f"{out['key_file']}", parent=self.root)


def generate_gdpr_data_export(self):
    """Everything the detector holds about one student."""
    student = self.privacy_student_var.get().strip()
    if not student:
        messagebox.showwarning(common.TITLE, "Enter the student number.", parent=self.root)
        return
    reference = simpledialog.askstring(common.TITLE, "Request reference (optional)",
                                       parent=self.root)
    out = common.call(self, self.detector.generate_gdpr_data_export, student,
                      request_reference=reference or None)
    if out and not common.result_failed(self, out):
        summary = out.get("data_summary", {})
        messagebox.showinfo(common.TITLE, f"Export {out['export_id']} saved to\n"
                                          f"{out['export_path']}\n"
                                          + ", ".join(f"{k}: {v}" for k, v in summary.items()),
                            parent=self.root)
