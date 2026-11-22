"""Compliance, bias, predictive analytics and the self-check preview.

* **Compliance** — the detector's processing record (legal basis, notice,
  retention), the retention policy and its runs (an integrity officer can
  apply it now), and a student's recorded consents.
* **Bias** — the aggregate disparity report (integrity officers): flag,
  referral and upheld rates by every characteristic held, groups under ten
  students suppressed, with a warning where a group is flagged
  disproportionately (ratio ≥ 1.25, p < 0.05). There is no automatic
  "correction"; a disparity is something to review.
* **Predictive analytics** — reviewer workload: readings expected to need
  review per module in the coming weeks; and, for one reading, how often
  similar readings were confirmed after review. Nothing predicts anything
  about an individual student.
* **Self-check** — what a student sees when they check a draft (staff
  preview: not counted, not stored).
"""

import logging

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


# ── compliance ──────────────────────────────────────────────────────────


def create_compliance_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Privacy & compliance", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                           pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "Readings are taken as part of the university's public task (academic integrity); "
        "students are told in the integrity notice. Readings' text is kept for the integrity "
        "retention period and then removed.")).pack(anchor="w", padx=15)
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", padx=15, pady=8)
    ttk.Button(buttons, text="📄 Processing record",
               command=self.generate_compliance_report).pack(side="left", padx=(0, 6))
    ttk.Button(buttons, text="🗓 Retention", command=self.show_data_retention_status).pack(
        side="left", padx=(0, 6))
    ttk.Button(buttons, text="✋ A student's consents",
               command=self.show_consent_management).pack(side="left")


def generate_compliance_report(self):
    manager = getattr(self.detector, "compliance_manager", None)
    if manager is None:
        messagebox.showerror(common.TITLE, "The compliance record is not available.",
                             parent=self.root)
        return
    report = common.call(self, manager.generate_compliance_report)
    if report is not None:
        self.show_compliance_report_window(report)


def show_compliance_report_window(self, report):
    common.text_window(self, "Processing record", report, 760, 560)


def show_data_retention_status(self):
    """The policy, recent runs, and (officers) apply it now."""
    pm = getattr(self.detector, "privacy_manager", None)
    if pm is None:
        messagebox.showerror(common.TITLE, "Retention is not available.", parent=self.root)
        return
    policy = common.call(self, pm.get_retention_policy) or {}
    runs = common.call(self, pm.get_retention_runs, 20) or []
    win = common.text_window(self, "Retention", {"policy": policy, "recent runs": runs},
                             700, 520)
    apply_btn = ttk.Button(win, text="Apply retention now", command=lambda: _apply(self, win))
    apply_btn.pack(side="bottom", pady=4)
    common.officer_only(self, apply_btn)


def _apply(self, win):
    if not messagebox.askyesno(common.TITLE, "Remove the text of readings past the retention "
                                             "period now?", parent=win):
        return
    if common.call(self, self.detector.require_officer) is None:
        return
    done = common.call(self, self.detector.privacy_manager.apply_retention)
    if done is not None:
        messagebox.showinfo(common.TITLE, f"Text removed from {done.get('readings_purged', 0)} "
                                          f"reading(s) older than {done.get('cutoff')}.",
                            parent=win)
        win.destroy()


def show_consent_management(self):
    """Look up (and, for officers, record) a student's consents."""
    pm = getattr(self.detector, "privacy_manager", None)
    if pm is None:
        messagebox.showerror(common.TITLE, "Consent records are not available.", parent=self.root)
        return
    win = tk.Toplevel(self.root)
    win.title("Consents")
    win.geometry("720x420")
    win.transient(self.root)
    top = ttk.Frame(win, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text="Student number").pack(side="left")
    student = ttk.Entry(top, width=14)
    student.pack(side="left", padx=4)
    cols = (("consent_type", "Consent", 160), ("granted", "Given", 60),
            ("version", "Notice", 80), ("granted_at", "Recorded", 150),
            ("expires_at", "Expires", 150))
    tree = ttk.Treeview(win, columns=[c[0] for c in cols], show="headings", height=10)
    for col, label, width in cols:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor="w")

    def show():
        rows = common.call(self, pm.get_consents, student.get().strip()) or []
        tree.delete(*tree.get_children())
        for r in rows:
            tree.insert("", "end", values=[r.get(c[0]) for c in cols])

    def record(granted):
        if not student.get().strip():
            return
        kind = consent_type.get()
        if common.call(self, self.detector.require_officer) is None:
            return
        if common.call(self, lambda: pm.record_consent(student.get().strip(), kind, granted)
                       or True):
            show()

    ttk.Button(top, text="Show", command=show).pack(side="left", padx=4)
    ttk.Label(top, text="Type").pack(side="left", padx=(12, 2))
    consent_type = ttk.Combobox(top, state="readonly", width=18,
                                values=["research_use", "federated_training",
                                        "self_check_history"])
    consent_type.set("research_use")
    consent_type.pack(side="left")
    give = ttk.Button(top, text="Record given", command=lambda: record(True))
    give.pack(side="left", padx=4)
    withdraw = ttk.Button(top, text="Record withdrawn", command=lambda: record(False))
    withdraw.pack(side="left")
    common.officer_only(self, give, withdraw)
    ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=6)
    tree.pack(fill="both", expand=True, padx=8, pady=4)


# ── bias ────────────────────────────────────────────────────────────────


def create_bias_detection_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Bias report", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                  pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "Flag, referral and upheld rates for each group of students by every characteristic "
        "the university holds, compared with everyone else. Groups with fewer than ten "
        "students are not shown. A warning means a group is flagged disproportionately: "
        "review the indicators before relying on them for that group. Integrity officers "
        "only.")).pack(anchor="w", padx=15)
    run_btn = ttk.Button(frame, text="Run the bias report", command=self.analyze_institutional_bias)
    run_btn.pack(anchor="w", padx=15, pady=8)
    common.officer_only(self, run_btn)
    self.bias_results_frame = ttk.Frame(frame)
    self.bias_results_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))


def analyze_institutional_bias(self):
    detector = getattr(self.detector, "bias_detector", None)
    if detector is None:
        messagebox.showerror(common.TITLE, "The bias report is not available.", parent=self.root)
        return
    report = common.call(self, detector.analyze_detection_bias)
    if report is not None:
        self.display_bias_analysis(report)


def display_bias_analysis(self, analysis):
    for widget in self.bias_results_frame.winfo_children():
        widget.destroy()
    if analysis.get("error"):
        ttk.Label(self.bias_results_frame, text=analysis["error"], foreground="red").pack(
            anchor="w")
        return
    ttk.Label(self.bias_results_frame, wraplength=900,
              text=f"{analysis.get('summary')} ({analysis.get('readings', 0)} readings; review "
                   f"level {analysis.get('threshold')}; groups under "
                   f"{analysis.get('minimum_group')} students suppressed)",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    for warning in analysis.get("warnings", []):
        ttk.Label(self.bias_results_frame, text=f"⚠ {warning}", foreground=self.colors["danger"],
                  wraplength=900).pack(anchor="w")
    cols = (("attribute", "Characteristic", 130), ("group", "Group", 140),
            ("students", "Students", 70), ("readings", "Readings", 70),
            ("flag_rate", "Flagged", 70), ("rest_flag_rate", "Others", 70),
            ("ratio", "Ratio", 60), ("p_value", "p", 70), ("referral_rate", "Referred", 70),
            ("upheld_rate", "Upheld", 70))
    tree = ttk.Treeview(self.bias_results_frame, columns=[c[0] for c in cols], show="headings",
                        height=12)
    for col, label, width in cols:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor="w")
    tree.tag_configure("warn", background="#fde2e2")
    for attribute in analysis.get("attributes", []):
        for g in attribute.get("groups", []):
            values = [attribute["attribute"]] + [g.get(c[0]) for c in cols[1:]]
            values = [f"{v:.3f}" if isinstance(v, float) else v for v in values]
            tree.insert("", "end", values=values, tags=("warn",) if g.get("warning") else ())
        if attribute.get("groups_suppressed"):
            tree.insert("", "end", values=[attribute["attribute"],
                                           f"({attribute['groups_suppressed']} small group(s) "
                                           "not shown)"] + [""] * (len(cols) - 2))
    tree.pack(fill="both", expand=True, pady=6)
    ttk.Label(self.bias_results_frame, text=analysis.get("correction", ""), wraplength=900).pack(
        anchor="w")


# ── predictive analytics ────────────────────────────────────────────────


def create_predictive_analytics_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Predictive analytics", style="Title.TLabel").pack(anchor="w",
                                                                           padx=15, pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "For planning review work and for context when reviewing. Nothing here predicts "
        "anything about an individual student.")).pack(anchor="w", padx=15)

    workload = ttk.LabelFrame(frame, text="Readings expected to need review", padding=8)
    workload.pack(fill="both", expand=True, padx=15, pady=8)
    row = ttk.Frame(workload)
    row.pack(fill="x")
    ttk.Label(row, text="Module").pack(side="left")
    self.forecast_module = common.IdPicker(row, common.modules(self), allow_blank=True,
                                           blank_label="(all my modules)", width=32)
    self.forecast_module.pack(side="left", padx=4)
    ttk.Label(row, text="Weeks ahead").pack(side="left", padx=(10, 2))
    self.forecast_weeks_var = tk.IntVar(value=4)
    ttk.Spinbox(row, from_=1, to=26, width=4, textvariable=self.forecast_weeks_var).pack(
        side="left")
    ttk.Button(row, text="Forecast", command=self.predict_student_risk).pack(side="left", padx=8)
    cols = (("module", "Module", 110), ("method", "Method", 230), ("total", "Expected", 80),
            ("weeks", "Week by week", 420))
    self.risk_results_frame = ttk.Treeview(workload, columns=[c[0] for c in cols],
                                           show="headings", height=8)
    for col, label, width in cols:
        self.risk_results_frame.heading(col, text=label)
        self.risk_results_frame.column(col, width=width, anchor="w")
    self.risk_results_frame.pack(fill="both", expand=True, pady=4)

    agreement = ttk.LabelFrame(frame, text="How often similar readings were confirmed",
                               padding=8)
    agreement.pack(fill="x", padx=15, pady=(0, 15))
    ttk.Label(agreement, text="Reading id").pack(side="left")
    self.risk_student_var = tk.StringVar()
    ttk.Entry(agreement, textvariable=self.risk_student_var, width=10).pack(side="left", padx=4)
    ttk.Button(agreement, text="Show", command=self.show_model_performance).pack(side="left")
    ttk.Button(agreement, text="Model behind it", command=self.train_risk_model).pack(
        side="left", padx=6)


def predict_student_risk(self):
    """The review-workload forecast (the per-student risk prediction was
    removed: it scored students on their own past readings)."""
    pa = getattr(self.detector, "predictive_analytics", None)
    if pa is None:
        messagebox.showerror(common.TITLE, "Predictive analytics is not available.",
                             parent=self.root)
        return
    out = common.call(self, pa.forecast_review_workload,
                      int(self.forecast_weeks_var.get() or 4), self.forecast_module.value())
    if out is not None:
        self.display_risk_prediction(out)


def display_risk_prediction(self, prediction):
    tree = self.risk_results_frame
    tree.delete(*tree.get_children())
    rows = prediction if isinstance(prediction, list) else prediction.get("modules", [])
    for r in rows:
        weeks = ", ".join(f"{f['week'][5:]}: {f['expected']}" for f in r.get("forecast", []))
        tree.insert("", "end", values=(r.get("module_code"), r.get("method"),
                                       r.get("expected_total"), weeks))
    if not rows:
        tree.insert("", "end", values=("—", "No readings at the review level yet", "", ""))


def train_risk_model(self):
    """The model whose estimate is shown (trained on review outcomes)."""
    out = common.call(self, self.detector.list_model_versions) or {}
    active = [v for v in out.get("versions", []) if v.get("is_active")]
    common.text_window(self, "Model behind the estimate",
                       active[0] if active else "No model is active. Train one under Model "
                                                "Management.", 640, 420)


def show_model_performance(self):
    """For one reading: how often similar readings were confirmed."""
    value = self.risk_student_var.get().strip()
    if not value.isdigit():
        messagebox.showwarning(common.TITLE, "Enter the reading id (shown in History and "
                                             "Alerts).", parent=self.root)
        return
    pa = getattr(self.detector, "predictive_analytics", None)
    out = common.call(self, pa.reviewer_agreement, int(value)) if pa else None
    if out is not None:
        common.text_window(self, f"Reading {value}: similar readings", out, 640, 420)


# ── self-check preview ──────────────────────────────────────────────────


def create_student_self_check_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Student self-check (preview)", style="Title.TLabel").pack(
        anchor="w", padx=15, pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "What a student sees when they check a draft in Academic Integrity: the same "
        "indicators, with advice, three checks a day, nothing kept. This preview is not "
        "counted or stored.")).pack(anchor="w", padx=15)
    buttons = ttk.Frame(frame)
    buttons.pack(side="bottom", fill="x", padx=15, pady=10)
    self.self_check_text = scrolledtext.ScrolledText(frame, wrap="word", height=12)
    self.self_check_text.pack(fill="both", expand=True, padx=15, pady=8)
    ttk.Button(buttons, text="Preview", command=self.run_self_check).pack(side="left")


def run_self_check(self):
    text = self.self_check_text.get("1.0", "end").strip()
    if not text:
        messagebox.showwarning(common.TITLE, "Paste a text first.", parent=self.root)
        return
    tool = getattr(self.detector, "student_self_check", None)
    if tool is None:
        messagebox.showerror(common.TITLE, "The self-check is not available.", parent=self.root)
        return
    result = common.call(self, tool.preview_analysis, text)
    if result is not None:
        if result.get("error"):
            messagebox.showerror(common.TITLE, result["error"], parent=self.root)
            return
        self.show_self_check_results(result, text)


def show_self_check_results(self, result, text=None):
    win = tk.Toplevel(self.root)
    win.title("Self-check preview")
    win.geometry(f"{min(900, win.winfo_screenwidth() - 60)}x"
                 f"{min(640, win.winfo_screenheight() - 100)}")
    win.transient(self.root)
    ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=6)
    common.show_reading(self, win, result, text)
    for advice in result.get("suggestions", []):
        ttk.Label(win, text=f"• {advice}", wraplength=820).pack(anchor="w", padx=12)
