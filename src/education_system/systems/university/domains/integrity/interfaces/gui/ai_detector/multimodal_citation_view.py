"""Images, code, citations and timing — all informational: none of these
changes a reading's strength.

* **Images** — text recognised in uploaded images compared with the
  written text (needs Pillow and pytesseract; says so when they are not
  installed).
* **Code** — leftover chat text in comments and strings ("Here's the
  updated function", "As an AI language model"); ordinary coding
  conventions are not counted.
* **Citations** — each citation is verified (its DOI resolves), not found,
  dated in the future, or unverified (no DOI, or the lookup was not
  possible) — "unverified" is not a concern.
* **Timing** — words per minute against the text's complexity when the
  writing time is known, and when a student's readings were taken. Timing
  says nothing about who wrote the work; use it only to ask about drafting.
"""

import logging

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


def _tab(self, label, builder):
    notebook = self.__dict__.get("notebook")
    if notebook is None:
        return None
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=label)
    builder(frame)
    return frame


def _result_dict(result):
    return result.to_dict() if hasattr(result, "to_dict") else dict(result or {})


def _analyzer(self, name):
    found = getattr(self.detector, name, None)
    if found is None:
        raise ValueError(f"Not available: {self.detector.component_errors.get(name, name)}")
    return found


# ── images and code ─────────────────────────────────────────────────────


def create_multi_modal_analysis_tab(self):
    return _tab(self, "🖼️ Multi-Modal", self.create_multi_modal_analysis_view)


def create_multi_modal_analysis_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Images and code (informational)", style="Title.TLabel").pack(
        anchor="w", padx=15, pady=(15, 6))
    images = ttk.LabelFrame(frame, text="Images against the written text", padding=8)
    images.pack(fill="x", padx=15, pady=4)
    self.uploaded_images_label = ttk.Label(images, text="No images chosen")
    ttk.Button(images, text="Choose images…", command=self.upload_images_for_analysis).pack(
        side="left", padx=(0, 6))
    ttk.Button(images, text="Compare with the text below",
               command=self.analyze_image_text_consistency).pack(side="left", padx=(0, 6))
    self.uploaded_images_label.pack(side="left")
    code = ttk.LabelFrame(frame, text="Code", padding=8)
    code.pack(fill="x", padx=15, pady=4)
    ttk.Label(code, text="Language").pack(side="left")
    self.code_language_var = tk.StringVar(value="python")
    ttk.Combobox(code, textvariable=self.code_language_var, state="readonly", width=12,
                 values=["python", "java", "javascript", "c", "cpp", "csharp", "sql", "r",
                         "other"]).pack(side="left", padx=4)
    ttk.Button(code, text="Check the code below", command=self.analyze_code_submission).pack(
        side="left", padx=6)
    self.code_input = scrolledtext.ScrolledText(frame, wrap="none", height=14)
    self.code_input.pack(fill="both", expand=True, padx=15, pady=(6, 15))


def upload_images_for_analysis(self):
    paths = filedialog.askopenfilenames(parent=self.root, title="Choose images",
                                        filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")])
    if not paths:
        return
    self.uploaded_images = []
    for path in paths:
        with open(path, "rb") as fh:
            self.uploaded_images.append(fh.read())
    self.uploaded_images_label.config(text=f"{len(paths)} image(s) chosen")


def analyze_image_text_consistency(self):
    images = self.__dict__.get("uploaded_images") or []
    text = self.code_input.get("1.0", "end").strip()
    if not images or not text:
        messagebox.showwarning(common.TITLE, "Choose images and paste the written text below.",
                               parent=self.root)
        return
    analyzer = common.call(self, _analyzer, self, "multimodal_analyzer")
    if analyzer is not None:
        result = common.call(self, analyzer.analyze_image_text_consistency, text, images)
        if result is not None:
            self.show_multimodal_results(result)


def analyze_code_submission(self):
    code = self.code_input.get("1.0", "end").strip()
    if not code:
        messagebox.showwarning(common.TITLE, "Paste the code first.", parent=self.root)
        return
    analyzer = common.call(self, _analyzer, self, "multimodal_analyzer")
    if analyzer is not None:
        result = common.call(self, analyzer.analyze_code_submission, code,
                             self.code_language_var.get())
        if result is not None:
            self.show_code_analysis_results(result)


def show_multimodal_results(self, result):
    data = _result_dict(result)
    common.text_window(self, "Images against the text", data.get("evidence") or data, 620, 420)


def show_code_analysis_results(self, result):
    data = _result_dict(result)
    evidence = data.get("evidence") or {}
    found = evidence.get("patterns_found") or []
    body = (f"Leftover chat text found: {len(found)}\n"
            + "".join(f"  • {p}\n" for p in found)
            + f"\nLines: {evidence.get('line_count')}\n\n{evidence.get('note', '')}")
    common.text_window(self, "Code", body, 620, 420)


# ── citations ───────────────────────────────────────────────────────────


def create_citation_verification_tab(self):
    return _tab(self, "📚 Citations", self.create_citation_verification_view)


def create_citation_verification_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Citations (informational)", style="Title.TLabel").pack(
        anchor="w", padx=15, pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "Each citation with a DOI is looked up. 'Not found' and 'dated in the future' are "
        "worth checking with the student; 'unverified' only means it could not be looked "
        "up.")).pack(anchor="w", padx=15)
    buttons = ttk.Frame(frame)
    buttons.pack(side="bottom", fill="x", padx=15, pady=10)
    ttk.Button(buttons, text="🔍 Check the citations", command=self.verify_citations).pack(
        side="left")
    self.citation_text = scrolledtext.ScrolledText(frame, wrap="word", height=14)
    self.citation_text.pack(fill="both", expand=True, padx=15, pady=6)


def verify_citations(self):
    text = self.citation_text.get("1.0", "end").strip()
    if not text:
        messagebox.showwarning(common.TITLE, "Paste text with citations.", parent=self.root)
        return
    verifier = common.call(self, _analyzer, self, "citation_verifier")
    if verifier is None:
        return
    self.update_status("Checking citations…")
    result = common.call(self, verifier.verify_citations, text)
    if result is not None:
        self.show_citation_results(result)


def show_citation_results(self, result):
    data = _result_dict(result)
    evidence = data.get("evidence") or {}
    win = tk.Toplevel(self.root)
    win.title("Citations")
    win.geometry(f"{min(960, win.winfo_screenwidth() - 60)}x"
                 f"{min(560, win.winfo_screenheight() - 100)}")
    win.transient(self.root)
    ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=6)
    ttk.Label(win, padding=8, text=(
        f"{evidence.get('total_citations', 0)} citation(s): {evidence.get('checked', 0)} looked "
        f"up, {evidence.get('unverified', 0)} could not be, "
        f"{evidence.get('suspicious_citations', 0)} worth checking with the student."
        if evidence.get("total_citations") else evidence.get("reason", "No citations found."))
    ).pack(anchor="w")
    cols = (("citation", "Citation", 420), ("status", "Result", 110), ("reason", "Why", 360))
    tree = ttk.Treeview(win, columns=[c[0] for c in cols], show="headings")
    for col, label, width in cols:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor="w")
    tree.tag_configure("check", background="#fde2e2")
    for c in evidence.get("citation_details") or []:
        tree.insert("", "end", tags=("check",) if c.get("suspicious") else (),
                    values=(c.get("citation"), str(c.get("status")).replace("_", " "),
                            (c.get("details") or {}).get("reason", "")))
    tree.pack(fill="both", expand=True, padx=8)
    self.update_status("Citations checked")


# ── timing ──────────────────────────────────────────────────────────────


def create_temporal_analysis_tab(self):
    return _tab(self, "⏱️ Timing", self.create_temporal_analysis_view)


def create_temporal_analysis_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Timing (informational)", style="Title.TLabel").pack(
        anchor="w", padx=15, pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "When or how fast someone works says nothing about who wrote the work. Use this only "
        "to ask a student how they drafted it.")).pack(anchor="w", padx=15)
    speed = ttk.LabelFrame(frame, text="Writing speed (when the writing time is known)",
                           padding=8)
    speed.pack(fill="both", expand=True, padx=15, pady=6)
    row = ttk.Frame(speed)
    row.pack(fill="x")
    ttk.Label(row, text="Minutes spent writing").pack(side="left")
    self.time_taken_var = tk.StringVar()
    ttk.Entry(row, textvariable=self.time_taken_var, width=8).pack(side="left", padx=4)
    ttk.Button(row, text="Check", command=self.analyze_writing_speed).pack(side="left", padx=6)
    self.temporal_text = scrolledtext.ScrolledText(speed, wrap="word", height=8)
    self.temporal_text.pack(fill="both", expand=True, pady=4)
    patterns = ttk.LabelFrame(frame, text="When a student's readings were taken", padding=8)
    patterns.pack(fill="x", padx=15, pady=(6, 15))
    ttk.Label(patterns, text="Module").pack(side="left")
    module = common.IdPicker(patterns, common.modules(self), width=28)
    module.pack(side="left", padx=4)
    ttk.Label(patterns, text="Student").pack(side="left")
    self.temporal_student = common.IdPicker(patterns, (), width=28)
    self.temporal_student.pack(side="left", padx=4)
    module.bind("<<ComboboxSelected>>",
                lambda _e: self.temporal_student.set_choices(common.students(module.value())))
    ttk.Button(patterns, text="Show", command=self.analyze_submission_patterns).pack(
        side="left", padx=6)
    self.temporal_results_frame = ttk.Frame(frame)
    self.temporal_results_frame.pack(fill="x", padx=15)


def analyze_writing_speed(self):
    try:
        minutes = float(self.time_taken_var.get())
    except ValueError:
        messagebox.showwarning(common.TITLE, "Give the minutes as a number.", parent=self.root)
        return
    text = self.temporal_text.get("1.0", "end").strip()
    if not text or minutes <= 0:
        messagebox.showwarning(common.TITLE, "Paste the text and give the minutes.",
                               parent=self.root)
        return
    analyzer = common.call(self, _analyzer, self, "temporal_analyzer")
    if analyzer is not None:
        result = common.call(self, analyzer.analyze_writing_speed, text, int(minutes * 60))
        if result is not None:
            self.show_temporal_results(result)


def analyze_submission_patterns(self):
    student = self.temporal_student.value()
    if not student:
        messagebox.showwarning(common.TITLE, "Choose the module and the student.",
                               parent=self.root)
        return
    analyzer = common.call(self, _analyzer, self, "temporal_analyzer")
    if analyzer is not None:
        patterns = common.call(self, analyzer.analyze_submission_patterns, student)
        if patterns is not None:
            self.show_submission_patterns(patterns)


def show_temporal_results(self, result):
    evidence = _result_dict(result).get("evidence") or {}
    lines = [f"Words per minute: {evidence.get('words_per_minute', 0):.1f}",
             f"Text complexity: {evidence.get('complexity_score', 0):.2f}",
             f"Usual range for that complexity: {evidence.get('expected_wpm_range')}"]
    if evidence.get("anomaly"):
        lines.append(f"Worth asking: {evidence['anomaly']}")
    lines += ["", evidence.get("note", "")]
    common.text_window(self, "Writing speed", "\n".join(lines), 560, 300)


def show_submission_patterns(self, patterns):
    for widget in self.temporal_results_frame.winfo_children():
        widget.destroy()
    if patterns.get("error"):
        text = f"Could not read the times: {patterns['error']}"
    elif patterns.get("insufficient_data"):
        text = "Fewer than three readings for this student."
    else:
        text = (f"{patterns.get('total_submissions')} reading(s); usual hour "
                f"{patterns.get('avg_hour', 0):.1f}; "
                f"{patterns.get('regular_interval_count', 0)} a day apart. "
                + patterns.get("note", ""))
    ttk.Label(self.temporal_results_frame, text=text, wraplength=900).pack(anchor="w", pady=4)
