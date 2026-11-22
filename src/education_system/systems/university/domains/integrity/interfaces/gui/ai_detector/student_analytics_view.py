"""Integrations, enhanced detection, student management and advanced
analytics. Every action calls the detector backend (scoped to the modules
the signed-in person reviews) and shows its real result; nothing here
judges a student on its own — readings are indicators for a conversation
with the student, and anything that could lead to a penalty goes through an
integrity case."""

import logging
import os

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


def _show(self, title, fn, *args, **kwargs):
    out = common.call(self, fn, *args, **kwargs)
    if out is None or common.result_failed(self, out):
        return None
    if isinstance(out, dict) and out.get("error"):
        messagebox.showerror(common.TITLE, out["error"], parent=self.root)
        return None
    common.text_window(self, title, out, 760, 560)
    return out


def _student_pickers(self, parent, attr, label="Student"):
    """Module + student pickers (real ids); returns the student picker."""
    ttk.Label(parent, text="Module").pack(side="left")
    module = common.IdPicker(parent, common.modules(self), width=28)
    module.pack(side="left", padx=4)
    ttk.Label(parent, text=label).pack(side="left")
    student = common.IdPicker(parent, (), width=30)
    student.pack(side="left", padx=4)
    module.bind("<<ComboboxSelected>>",
                lambda _e: student.set_choices(common.students(module.value())))
    setattr(self, attr, (module, student))
    return student


def _student(self, attr):
    _module, student = self.__dict__.get(attr, (None, None))
    value = student.value() if student is not None else None
    if not value:
        messagebox.showwarning(common.TITLE, "Choose the module and the student.",
                               parent=self.root)
    return value


# ── integrations ────────────────────────────────────────────────────────


def create_integrations_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Integrations", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                   pady=15)
    similarity = ttk.LabelFrame(frame, text="Similarity checking", padding=10)
    similarity.pack(fill="x", padx=15, pady=4)
    ttk.Label(similarity, wraplength=850, text=(
        "Submissions are compared with the university's own repository of submissions and "
        "reference documents; results are reviewed in Academic Integrity. No external "
        "similarity service is connected.")).pack(anchor="w")
    ttk.Button(similarity, text="Open Academic Integrity",
               command=lambda: _open_integrity(self)).pack(anchor="w", pady=(6, 0))

    record = ttk.LabelFrame(frame, text="Refer a reading for an outcome", padding=10)
    record.pack(fill="x", padx=15, pady=4)
    ttk.Label(record, wraplength=850, text=(
        "Opens an integrity case with your proposed outcome for the integrity officer. "
        "Nothing goes on the student's record unless the case is decided against them.")).pack(
        anchor="w")
    row = ttk.Frame(record)
    row.pack(fill="x", pady=4)
    ttk.Label(row, text="Reading's submission id").pack(side="left")
    self.push_submission_var = tk.StringVar()
    ttk.Entry(row, textvariable=self.push_submission_var, width=10).pack(side="left", padx=4)
    ttk.Button(row, text="Refer…", command=self.push_to_academic_record).pack(side="left",
                                                                            padx=6)
    status = ttk.LabelFrame(frame, text="Readings referred from the detector", padding=6)
    status.pack(fill="both", expand=True, padx=15, pady=(4, 15))
    cols = (("record_id", "Record", 160), ("student_id", "Student", 100),
            ("violation_type", "Concern", 150), ("sanction", "Proposed", 160),
            ("status", "Status", 80), ("case_id", "Case", 60), ("created_at", "When", 150))
    self.integration_tree = ttk.Treeview(status, columns=[c[0] for c in cols], show="headings",
                                         height=8)
    for col, label, width in cols:
        self.integration_tree.heading(col, text=label)
        self.integration_tree.column(col, width=width, anchor="w")
    self.integration_tree.pack(fill="both", expand=True)
    self._integration_columns = [c[0] for c in cols]
    self._load_integration_status()


def _open_integrity(self):
    from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.window import (
        open_integrity_window,
    )
    open_integrity_window(self.root, getattr(self, "auth", None))


def _load_integration_status(self):
    tree = self.__dict__.get("integration_tree")
    if tree is None:
        return
    scope = common.scope(self)
    conn = common._connect()
    try:
        cur = conn.execute("SELECT a.*, s.course_code FROM ai_detector_academic_records a LEFT "
                           "JOIN ai_detector_results r ON r.id = a.ai_result_id LEFT JOIN "
                           "ai_detector_submissions s ON s.id = r.submission_id ORDER BY "
                           "a.created_at DESC LIMIT 200")
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    except Exception as exc:
        logger.warning("Referred readings unavailable: %s", exc)
        rows = []
    finally:
        conn.close()
    tree.delete(*tree.get_children())
    for r in rows:
        if scope["modules"] is not None and r.get("course_code") not in scope["modules"]:
            continue
        tree.insert("", "end", values=[r.get(c) for c in self._integration_columns])


def push_to_academic_record(self):
    """Refer a reading with a proposed outcome (opens an integrity case)."""
    value = self.push_submission_var.get().strip()
    if not value.isdigit():
        messagebox.showwarning(common.TITLE, "Enter the reading's submission id (shown in "
                                             "History).", parent=self.root)
        return
    details = common.call(self, self.detector.get_submission_details, int(value))
    if details is None:
        return
    win = tk.Toplevel(self.root)
    win.title(f"Refer reading {details.get('result_id')}")
    win.transient(self.root)
    form = ttk.Frame(win, padding=10)
    form.pack(fill="both", expand=True)
    ttk.Label(form, text=f"Student {details.get('student_id')}, module "
                         f"{details.get('course_code')}: {details.get('level')}").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
    ttk.Label(form, text="Concern").grid(row=1, column=0, sticky="w")
    concern = ttk.Combobox(form, state="readonly", width=30,
                           values=["Unauthorised AI use", "Contract cheating", "Plagiarism",
                                   "Collusion", "Other"])
    concern.set("Unauthorised AI use")
    concern.grid(row=1, column=1, sticky="w", pady=2)
    ttk.Label(form, text="Proposed outcome").grid(row=2, column=0, sticky="w")
    sanction = ttk.Combobox(form, state="readonly", width=30,
                            values=["Advice on good academic practice", "Formal warning",
                                    "Mark capped at the pass mark", "Resubmission",
                                    "Mark of zero", "Refer to the misconduct panel"])
    sanction.set("Advice on good academic practice")
    sanction.grid(row=2, column=1, sticky="w", pady=2)
    ttk.Label(form, text="What else the concern rests on").grid(row=3, column=0, sticky="nw")
    notes = scrolledtext.ScrolledText(form, height=5, width=60, wrap="word")
    notes.grid(row=3, column=1, pady=2)

    def go():
        text = notes.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning(common.TITLE, "Say what else the concern rests on — a "
                                                 "reading alone cannot lead to a penalty.",
                                   parent=win)
            return
        out = common.call(self, self.detector.push_to_academic_record, details["student_id"],
                          int(value), concern.get(), sanction.get(), None, text)
        if out and not common.result_failed(self, out):
            win.destroy()
            messagebox.showinfo(common.TITLE, f"Case {out.get('case_id')} opened. "
                                              f"{out.get('note', '')}", parent=self.root)
            self._load_integration_status()

    ttk.Button(form, text="Refer", command=go).grid(row=4, column=1, sticky="e", pady=6)


# ── enhanced detection ──────────────────────────────────────────────────


def create_enhanced_detection_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Enhanced detection (informational)", style="Title.TLabel").pack(
        anchor="w", padx=15, pady=(15, 2))
    ttk.Label(frame, text=common.NOTICE, wraplength=900).pack(anchor="w", padx=15)
    who = ttk.Frame(frame)
    who.pack(fill="x", padx=15, pady=6)
    _student_pickers(self, who, "_enhanced_pickers")
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", padx=15)
    for label, command in (("Writing style against earlier work",
                            self.analyze_writing_style_fingerprint),
                           ("Paraphrasing-tool patterns", self.detect_paraphrasing_tools),
                           ("Leftover prompt text", self.analyze_prompt_artifacts),
                           ("Other-language paragraphs", self.detect_translation_artifacts)):
        ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 6))
    buttons2 = ttk.Frame(frame)
    buttons2.pack(fill="x", padx=15, pady=4)
    for label, command in (("Against the module level", self.analyze_knowledge_consistency),
                           ("Pasted / formatting traces", self.detect_copy_paste_patterns),
                           ("References", self.analyze_reference_authenticity),
                           ("Compare drafts…", self.compare_draft_versions)):
        ttk.Button(buttons2, text=label, command=command).pack(side="left", padx=(0, 6))
    self.enhanced_text = scrolledtext.ScrolledText(frame, wrap="word", height=14)
    self.enhanced_text.pack(fill="both", expand=True, padx=15, pady=(6, 15))


def _enhanced_text(self):
    text = self.enhanced_text.get("1.0", "end").strip()
    if not text:
        messagebox.showwarning(common.TITLE, "Paste the text first.", parent=self.root)
    return text


def analyze_writing_style_fingerprint(self):
    student = _student(self, "_enhanced_pickers")
    if student:
        _show(self, "Writing style against earlier work",
              self.detector.analyze_writing_style_fingerprint, student,
              self.enhanced_text.get("1.0", "end").strip() or None)


def detect_paraphrasing_tools(self):
    text = _enhanced_text(self)
    if text:
        _show(self, "Paraphrasing-tool patterns", self.detector.detect_paraphrasing_tools, text)


def analyze_prompt_artifacts(self):
    text = _enhanced_text(self)
    if text:
        _show(self, "Leftover prompt text", self.detector.analyze_prompt_artifacts, text)


def detect_translation_artifacts(self):
    text = _enhanced_text(self)
    if text:
        _show(self, "Other-language paragraphs", self.detector.detect_translation_artifacts, text)


def analyze_knowledge_consistency(self):
    text = _enhanced_text(self)
    student = _student(self, "_enhanced_pickers") if text else None
    if student:
        module, _s = self._enhanced_pickers
        _show(self, "Against the module level", self.detector.analyze_knowledge_consistency,
              text, student, module.value())


def detect_copy_paste_patterns(self):
    text = _enhanced_text(self)
    if text:
        _show(self, "Pasted / formatting traces", self.detector.detect_copy_paste_patterns, text)


def analyze_reference_authenticity(self):
    text = _enhanced_text(self)
    if text:
        self.update_status("Checking references…")
        _show(self, "References", self.detector.analyze_reference_authenticity, text)


def _load_draft_files(self):
    paths = filedialog.askopenfilenames(parent=self.root, title="Choose the drafts, oldest first",
                                        filetypes=[("Documents", "*.txt *.md *.pdf *.docx")])
    return list(paths)


def compare_draft_versions(self):
    paths = self._load_draft_files()
    if len(paths) < 2:
        if paths:
            messagebox.showwarning(common.TITLE, "Choose at least two drafts.", parent=self.root)
        return
    drafts = []
    for path in paths:
        try:
            drafts.append(self._extract_text_from_file(path))
        except ValueError as exc:
            messagebox.showerror(common.TITLE, f"{os.path.basename(path)}: {exc}",
                                 parent=self.root)
            return
    module, student = self.__dict__.get("_enhanced_pickers", (None, None))
    _show(self, "Drafts compared", self.detector.compare_draft_versions, drafts,
          student.value() if student is not None else None)


# ── student management ──────────────────────────────────────────────────


def create_student_management_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Students", style="Title.TLabel").pack(anchor="w", padx=15,
                                                               pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "A student's readings over time, for context when talking to them. Readings are "
        "indicators, not evidence, and nothing here grades the student.")).pack(anchor="w",
                                                                                padx=15)
    one = ttk.LabelFrame(frame, text="One student", padding=8)
    one.pack(fill="x", padx=15, pady=6)
    row = ttk.Frame(one)
    row.pack(fill="x")
    _student_pickers(self, row, "_mgmt_pickers")
    row2 = ttk.Frame(one)
    row2.pack(fill="x", pady=(6, 0))
    for label, command in (("Profile", self.view_student_profile),
                           ("Readings over time", self.view_student_progression),
                           ("Integrity summary", self.generate_student_report_card),
                           ("Flag for review…", self.flag_student_for_review)):
        ttk.Button(row2, text=label, command=command).pack(side="left", padx=(0, 6))
    two = ttk.LabelFrame(frame, text="Compare with another student", padding=8)
    two.pack(fill="x", padx=15, pady=6)
    row3 = ttk.Frame(two)
    row3.pack(fill="x")
    _student_pickers(self, row3, "_compare_pickers", "Other student")
    ttk.Button(row3, text="Compare", command=self.compare_students).pack(side="left", padx=6)
    cohort = ttk.LabelFrame(frame, text="A whole module", padding=8)
    cohort.pack(fill="x", padx=15, pady=(6, 15))
    ttk.Label(cohort, text="Module").pack(side="left")
    self.bulk_module = common.IdPicker(cohort, common.modules(self), width=30)
    self.bulk_module.pack(side="left", padx=4)
    ttk.Button(cohort, text="Summarise", command=self.bulk_student_analysis).pack(side="left",
                                                                                padx=6)


def view_student_profile(self):
    student = _student(self, "_mgmt_pickers")
    if student:
        _show(self, f"Student {student}", self.detector.view_student_profile, student)


def compare_students(self):
    first = _student(self, "_mgmt_pickers")
    second = _student(self, "_compare_pickers") if first else None
    if first and second:
        _show(self, f"{first} and {second}", self.detector.compare_students, first, second)


def generate_student_report_card(self):
    student = _student(self, "_mgmt_pickers")
    if student:
        _show(self, f"Integrity summary — {student}",
              self.detector.generate_student_report_card, student)


def flag_student_for_review(self):
    student = _student(self, "_mgmt_pickers")
    if not student:
        return
    reason = simpledialog.askstring(common.TITLE, f"Why should {student}'s work be looked at "
                                                  "more closely?", parent=self.root)
    if not reason:
        return
    severity = simpledialog.askstring(common.TITLE, "Priority (low, medium, high):",
                                      initialvalue="medium", parent=self.root)
    out = common.call(self, self.detector.flag_student_for_review, student, reason,
                      severity=(severity or "medium").strip().lower())
    if out and not common.result_failed(self, out):
        self.update_status(f"{student} flagged for review")


def view_student_progression(self):
    student = _student(self, "_mgmt_pickers")
    if student:
        _show(self, f"Readings over time — {student}", self.detector.view_student_progression,
              student)


def bulk_student_analysis(self):
    module = self.bulk_module.value()
    if not module:
        messagebox.showwarning(common.TITLE, "Choose the module.", parent=self.root)
        return
    _show(self, f"{module} — readings by student", self.detector.bulk_student_analysis,
          course_code=module)


# ── advanced analytics ──────────────────────────────────────────────────


def create_advanced_analytics_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Advanced analytics (your modules)", style="Title.TLabel").pack(
        anchor="w", padx=15, pady=(15, 6))
    grid = ttk.Frame(frame)
    grid.pack(fill="x", padx=15)
    actions = (("Spread of strengths", self.show_detection_confidence_distribution),
               ("Frequent words", self.generate_word_cloud),
               ("Readings over time", self.plot_submission_timeline),
               ("How the indicators relate", self.show_correlation_matrix),
               ("Very similar texts", self.cluster_similar_submissions),
               ("By module", self.generate_department_comparison),
               ("Week by week", self.show_weekly_trends),
               ("Export all as a data pack", self.export_visualization_pack))
    for i, (label, command) in enumerate(actions):
        ttk.Button(grid, text=label, command=command, width=30).grid(row=i // 2, column=i % 2,
                                                                     padx=4, pady=4, sticky="w")


def show_detection_confidence_distribution(self):
    _show(self, "Spread of strengths", self.detector.show_detection_confidence_distribution)


def generate_word_cloud(self):
    _show(self, "Frequent words", self.detector.generate_word_cloud)


def plot_submission_timeline(self):
    _show(self, "Readings over time", self.detector.plot_submission_timeline)


def show_correlation_matrix(self):
    _show(self, "How the indicators relate", self.detector.show_correlation_matrix)


def cluster_similar_submissions(self):
    _show(self, "Very similar texts", self.detector.cluster_similar_submissions)


def generate_department_comparison(self):
    _show(self, "By module", self.detector.generate_department_comparison)


def show_weekly_trends(self):
    _show(self, "Week by week", self.detector.show_weekly_trends)


def export_visualization_pack(self):
    out = common.call(self, self.detector.export_visualization_pack)
    if out and not common.result_failed(self, out):
        common.text_window(self, "Data pack", out, 600, 360)
