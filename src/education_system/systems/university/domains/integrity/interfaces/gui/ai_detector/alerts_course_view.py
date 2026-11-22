"""Alerts and course management.

* **Alerts** — every reading at or above the review level opens an alert
  on its module. Staff who review the module record "no concern" (with the
  reason) or refer it as an integrity case; both are the integrity review of
  the reading, so the alert queue and Academic Integrity always agree.
  Escalating opens an integrity case too (the integrity officers are told).
  Integrity officers set the review level and extra e-mail recipients.
* **Course management** — per-assignment profiles and baselines (what
  ordinary work on the assignment looks like), comparing a text with its
  assignment's baseline, a module's integrity dashboard and its end-of-term
  report.
"""

import logging

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)

_ALERT_COLUMNS = (("alert_id", "Alert", 55), ("ai_result_id", "Reading", 65),
                  ("student_id", "Student", 100), ("module_code", "Module", 90),
                  ("submission_title", "Work", 220), ("risk_level", "Level", 70),
                  ("ai_score", "Strength", 70), ("status", "Status", 90),
                  ("created_at", "Raised", 140), ("case_id", "Case", 55))


# ── alerts ──────────────────────────────────────────────────────────────


def create_alerts_notifications_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Alerts", style="Title.TLabel").pack(anchor="w", padx=15, pady=(15, 2))
    ttk.Label(frame, text=common.NOTICE, wraplength=900,
              foreground=self.colors["danger"]).pack(anchor="w", padx=15)

    top = ttk.Frame(frame)
    top.pack(fill="x", padx=15, pady=6)
    ttk.Label(top, text="Level").pack(side="left")
    self.alert_level_var = tk.StringVar(value="")
    ttk.Combobox(top, textvariable=self.alert_level_var, state="readonly", width=10,
                 values=["", "low", "medium", "high"]).pack(side="left", padx=4)
    self.alert_reviewed_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(top, text="include reviewed", variable=self.alert_reviewed_var,
                    command=self.view_alert_queue).pack(side="left", padx=6)
    ttk.Button(top, text="🔄 Refresh", command=self.view_alert_queue).pack(side="left", padx=6)
    thresholds_btn = ttk.Button(top, text="Review level…", command=self.configure_alert_thresholds)
    thresholds_btn.pack(side="right")
    email_btn = ttk.Button(top, text="E-mail recipients…", command=self.setup_email_alerts)
    email_btn.pack(side="right", padx=6)
    common.officer_only(self, thresholds_btn, email_btn)
    self.alert_summary_var = tk.StringVar()
    ttk.Label(frame, textvariable=self.alert_summary_var).pack(anchor="w", padx=15)

    actions = ttk.Frame(frame)
    actions.pack(side="bottom", fill="x", padx=15, pady=(0, 15))
    ttk.Button(actions, text="Open reading", command=lambda: _open_alert(self)).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="No concern…", command=self.dismiss_alert).pack(side="left",
                                                                           padx=(0, 6))
    ttk.Button(actions, text="Refer as a case…", command=lambda: _refer(self)).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Escalate…", command=self.escalate_to_dean).pack(side="left")

    self.alert_tree = ttk.Treeview(frame, columns=[c[0] for c in _ALERT_COLUMNS],
                                   show="headings", height=14)
    for col, label, width in _ALERT_COLUMNS:
        self.alert_tree.heading(col, text=label)
        self.alert_tree.column(col, width=width, anchor="w")
    self.alert_tree.pack(fill="both", expand=True, padx=15, pady=6)
    self.alert_tree.bind("<Double-1>", lambda _e: _open_alert(self))
    self._alerts = {}
    self.view_alert_queue()


def view_alert_queue(self):
    tree = self.__dict__.get("alert_tree")
    if tree is None or not tree.winfo_exists():
        return
    out = common.call(self, self.detector.view_alert_queue,
                      self.alert_level_var.get() or None, bool(self.alert_reviewed_var.get()))
    if out is None:
        return
    tree.delete(*tree.get_children())
    self._alerts = {}
    for a in out.get("alerts", []):
        self._alerts[str(a["alert_id"])] = a
        values = [a.get(c[0]) for c in _ALERT_COLUMNS]
        values[6] = f"{float(a.get('ai_score') or 0):.2f}"
        tree.insert("", "end", iid=str(a["alert_id"]), values=values)
    summary = out.get("summary", {})
    self.alert_summary_var.set(f"{out.get('total', 0)} alert(s); waiting: "
                               + (", ".join(f"{k} {v}" for k, v in summary.items()) or "none"))


def _selected_alert(self):
    sel = self.alert_tree.selection()
    if not sel:
        messagebox.showwarning(common.TITLE, "Select an alert.", parent=self.root)
        return None
    return self._alerts.get(sel[0])


def _open_alert(self):
    alert = _selected_alert(self)
    if alert and alert.get("submission_id"):
        details = common.call(self, self.detector.get_submission_details,
                              int(alert["submission_id"]))
        if details is not None:
            self.show_submission_details_window(details)


def dismiss_alert(self):
    """No concern, with the reason (recorded as the reading's review)."""
    alert = _selected_alert(self)
    if not alert:
        return
    reason = simpledialog.askstring(common.TITLE, "Why is there no concern? (recorded, and "
                                                  "shown to the student with the reading)",
                                    parent=self.root)
    if not reason:
        return
    out = common.call(self, self.detector.dismiss_alert, alert["alert_id"], "other", reason)
    if out and not common.result_failed(self, out):
        self.view_alert_queue()


def _refer(self):
    alert = _selected_alert(self)
    if not alert:
        return
    note = simpledialog.askstring(common.TITLE, "Why refer it? Say what else the concern rests "
                                                "on — a reading alone cannot lead to a penalty.",
                                  parent=self.root)
    if not note:
        return
    out = common.call(self, self.detector.refer_alert, alert["alert_id"], note)
    if out and not common.result_failed(self, out):
        messagebox.showinfo(common.TITLE, f"Case {out.get('case_id')} opened; the student and "
                                          "the integrity officers are told.", parent=self.root)
        self.view_alert_queue()


def escalate_to_dean(self):
    """Escalate the selected alert's reading: an integrity case is opened."""
    alert = _selected_alert(self)
    if not alert:
        return
    win = tk.Toplevel(self.root)
    win.title("Escalate")
    win.transient(self.root)
    form = ttk.Frame(win, padding=10)
    form.pack(fill="both", expand=True)
    ttk.Label(form, text="Concern").grid(row=0, column=0, sticky="w")
    kind = ttk.Combobox(form, state="readonly", width=30,
                        values=["Unauthorised AI use", "Contract cheating", "Plagiarism",
                                "Collusion", "Other"])
    kind.set("Unauthorised AI use")
    kind.grid(row=0, column=1, sticky="w", pady=3)
    ttk.Label(form, text="Summary").grid(row=1, column=0, sticky="nw")
    summary = scrolledtext.ScrolledText(form, height=6, width=60, wrap="word")
    summary.grid(row=1, column=1, pady=3)
    ttk.Label(form, text="Suggested outcome").grid(row=2, column=0, sticky="w")
    action = ttk.Entry(form, width=50)
    action.grid(row=2, column=1, sticky="w", pady=3)

    def go():
        text = summary.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning(common.TITLE, "Write the summary.", parent=win)
            return
        out = common.call(self, self.detector.escalate_to_dean, alert["submission_id"],
                          alert.get("student_id"), kind.get(), text,
                          action.get().strip() or None)
        if out and not common.result_failed(self, out):
            win.destroy()
            messagebox.showinfo(common.TITLE, f"Escalated as case {out.get('case_id')}.",
                                parent=self.root)
            self.view_alert_queue()

    ttk.Button(form, text="Escalate", command=go).grid(row=3, column=1, sticky="e", pady=6)


def configure_alert_thresholds(self):
    """The review level (integrity setting; officers)."""
    current = common.threshold()
    value = simpledialog.askfloat(common.TITLE, "Strength at which a reading waits for review "
                                                "(0–1):", initialvalue=current, minvalue=0.05,
                                  maxvalue=1.0, parent=self.root)
    if value is None:
        return
    low, medium = round(value / 3, 3), round(value * 2 / 3, 3)
    out = common.call(self, self.detector.configure_alert_thresholds, low, medium, value,
                      max(value + 0.001, min(1.0, value + 0.15)))
    if out and not common.result_failed(self, out):
        self.update_status(f"Review level set to {value:.2f}")
        self.view_alert_queue()


def setup_email_alerts(self):
    """Also e-mail someone about new alerts (module staff always are)."""
    email = simpledialog.askstring(common.TITLE, "E-mail address to tell about new alerts:",
                                   parent=self.root)
    if not email:
        return
    levels = simpledialog.askstring(common.TITLE, "For which levels? (comma-separated: low, "
                                                  "medium, high)", initialvalue="high",
                                    parent=self.root)
    if not levels:
        return
    out = common.call(self, self.detector.setup_email_alerts, email.strip(),
                      [s.strip() for s in levels.split(",") if s.strip()])
    if out and not common.result_failed(self, out):
        self.update_status(f"{email} will be told about new alerts")


# ── course management ───────────────────────────────────────────────────


def create_course_management_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Course management", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                         pady=(15, 6))
    row = ttk.Frame(frame)
    row.pack(fill="x", padx=15, pady=4)
    ttk.Label(row, text="Module").pack(side="left")
    self.course_module = common.IdPicker(row, common.modules(self), width=34)
    self.course_module.pack(side="left", padx=6)
    self.course_module.bind("<<ComboboxSelected>>", lambda _e: self._load_assignment_profiles())
    ttk.Button(row, text="Dashboard", command=self.view_course_integrity_dashboard).pack(
        side="left", padx=4)
    ttk.Button(row, text="End-of-term report…", command=self.generate_course_end_report).pack(
        side="left", padx=4)

    profiles = ttk.LabelFrame(frame, text="Assignment profiles and baselines", padding=8)
    profiles.pack(fill="both", expand=True, padx=15, pady=8)
    buttons = ttk.Frame(profiles)
    buttons.pack(side="bottom", fill="x", pady=(6, 0))
    ttk.Button(buttons, text="New profile…", command=self.create_assignment_profile).pack(
        side="left", padx=(0, 6))
    ttk.Button(buttons, text="Set baseline from samples…",
               command=self.set_assignment_baseline).pack(side="left", padx=(0, 6))
    ttk.Button(buttons, text="Compare a text…",
               command=self.compare_against_assignment_baseline).pack(side="left")
    cols = (("profile_id", "Profile", 150), ("assignment_name", "Assignment", 220),
            ("assignment_type", "Type", 90), ("words", "Words", 100),
            ("baseline_set", "Baseline", 70), ("created_by", "By", 90))
    self.profile_tree = ttk.Treeview(profiles, columns=[c[0] for c in cols], show="headings",
                                     height=8)
    for col, label, width in cols:
        self.profile_tree.heading(col, text=label)
        self.profile_tree.column(col, width=width, anchor="w")
    self.profile_tree.pack(fill="both", expand=True)
    self.course_output = ttk.Frame(frame)
    self.course_output.pack(fill="x", padx=15, pady=(0, 15))


def _load_assignment_profiles(self):
    module = self.course_module.value()
    tree = self.profile_tree
    tree.delete(*tree.get_children())
    if not module:
        return
    conn = common._connect()
    try:
        rows = conn.execute("SELECT profile_id, assignment_name, assignment_type, "
                            "word_count_min, word_count_max, baseline_set, created_by FROM "
                            "ai_detector_assignment_profiles WHERE course_code = ? ORDER BY "
                            "created_at DESC", (module,)).fetchall()
    except Exception as exc:
        logger.warning("Assignment profiles unavailable: %s", exc)
        rows = []
    finally:
        conn.close()
    for r in rows:
        words = f"{r[3] or '—'}–{r[4] or '—'}"
        tree.insert("", "end", iid=r[0], values=(r[0], r[1], r[2], words,
                                                 "yes" if r[5] else "no", r[6]))


def _load_courses_for_dashboard(self):
    """Modules the person may see (kept for older callers)."""
    return [code for code, _label in common.modules(self)]


def _selected_profile(self):
    sel = self.profile_tree.selection()
    if not sel:
        messagebox.showwarning(common.TITLE, "Select a profile.", parent=self.root)
        return None
    return sel[0]


def create_assignment_profile(self):
    module = self.course_module.value()
    if not module:
        messagebox.showwarning(common.TITLE, "Choose the module.", parent=self.root)
        return
    assignments = common.assignments(module)
    win = tk.Toplevel(self.root)
    win.title("New assignment profile")
    win.transient(self.root)
    form = ttk.Frame(win, padding=10)
    form.pack(fill="both", expand=True)
    ttk.Label(form, text="Assignment").grid(row=0, column=0, sticky="w")
    assignment = common.IdPicker(form, assignments, width=40)
    assignment.grid(row=0, column=1, pady=3)
    ttk.Label(form, text="Type").grid(row=1, column=0, sticky="w")
    kind = ttk.Combobox(form, state="readonly", values=["essay", "report", "reflection",
                                                        "code", "exam"], width=15)
    kind.set("essay")
    kind.grid(row=1, column=1, sticky="w", pady=3)
    ttk.Label(form, text="Words (min–max)").grid(row=2, column=0, sticky="w")
    words = ttk.Frame(form)
    words.grid(row=2, column=1, sticky="w")
    wmin, wmax = ttk.Entry(words, width=8), ttk.Entry(words, width=8)
    wmin.pack(side="left")
    wmax.pack(side="left", padx=4)

    def go():
        if not assignment.value():
            messagebox.showwarning(common.TITLE, "Choose the assignment.", parent=win)
            return
        label = assignment.get()
        out = common.call(self, self.detector.create_assignment_profile, module,
                          label.split(" (due", 1)[0], kind.get(),
                          int(wmin.get()) if wmin.get().isdigit() else None,
                          int(wmax.get()) if wmax.get().isdigit() else None)
        if out and not common.result_failed(self, out):
            win.destroy()
            self._load_assignment_profiles()

    ttk.Button(form, text="Create", command=go).grid(row=3, column=1, sticky="e", pady=6)


def set_assignment_baseline(self):
    profile = _selected_profile(self)
    if not profile:
        return
    folder = filedialog.askdirectory(parent=self.root, title="Folder of sample work for this "
                                                              "assignment")
    if not folder:
        return
    out = common.call(self, self.detector.set_assignment_baseline, profile, "samples", folder)
    if out and not common.result_failed(self, out):
        common.text_window(self, "Baseline", out, 560, 380)
        self._load_assignment_profiles()


def compare_against_assignment_baseline(self):
    profile = _selected_profile(self)
    if not profile:
        return
    win = tk.Toplevel(self.root)
    win.title("Compare a text with the baseline")
    win.transient(self.root)
    buttons = ttk.Frame(win)
    buttons.pack(side="bottom", fill="x", padx=8, pady=6)
    text = scrolledtext.ScrolledText(win, height=14, width=80, wrap="word")
    text.pack(fill="both", expand=True, padx=8, pady=8)

    def go():
        body = text.get("1.0", "end").strip()
        if not body:
            return
        out = common.call(self, self.detector.compare_against_assignment_baseline, profile, body)
        if out and not common.result_failed(self, out):
            common.text_window(self, "Compared with the baseline", out, 600, 420)

    ttk.Button(buttons, text="Compare", command=go).pack(side="right")


def view_course_integrity_dashboard(self):
    module = self.course_module.value()
    if not module:
        messagebox.showwarning(common.TITLE, "Choose the module.", parent=self.root)
        return
    out = common.call(self, self.detector.view_course_integrity_dashboard, module)
    if out is not None:
        if out.get("error"):
            messagebox.showerror(common.TITLE, out["error"], parent=self.root)
            return
        common.text_window(self, f"{module} — integrity dashboard", out, 640, 480)


def generate_course_end_report(self):
    module = self.course_module.value()
    if not module:
        messagebox.showwarning(common.TITLE, "Choose the module.", parent=self.root)
        return
    term = simpledialog.askstring(common.TITLE, "Term or semester (e.g. 2026-27 S1):",
                                  parent=self.root)
    if not term:
        return
    out = common.call(self, self.detector.generate_course_end_report, module, term,
                      export_format="json")
    if out and not common.result_failed(self, out):
        common.text_window(self, f"{module} — end-of-term report", out, 640, 480)
