"""External APIs and visual analysis.

* **External APIs** (integrity officers) — register an outside detection
  service (URL and key, held only while the window is open), test it with
  a fixed sentence, see its rate limit and circuit-breaker state, and —
  after confirming that the text will leave the university — compare its
  score for a text with the reading. Outside scores are no more reliable
  than ours: they are shown as information, never as evidence. "Ensemble"
  is the review-outcome model's estimate for the text.
* **Visual analysis** — for a pasted text: each sentence shaded by how much
  of it lies in an indicator passage (stock phrasing, leftover chat text,
  formulaic opening), the paragraph flow, and plain complexity figures.
"""

import logging
import re

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)

TEST_SENTENCE = "This is a fixed test sentence used only to check the connection."


# ── external APIs ───────────────────────────────────────────────────────


def create_api_integration_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="External detection APIs", style="Title.TLabel").pack(
        anchor="w", padx=15, pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "Integrity officers only. Comparing sends the text to the outside service, so it "
        "always asks first. Outside scores are information, not evidence.")).pack(anchor="w",
                                                                                 padx=15)
    config = ttk.LabelFrame(frame, text="Register a service (kept until the window closes)",
                            padding=10)
    config.pack(fill="x", padx=15, pady=8)
    ttk.Label(config, text="Name").pack(side="left")
    self.api_service_var = tk.StringVar()
    ttk.Entry(config, textvariable=self.api_service_var, width=14).pack(side="left", padx=4)
    ttk.Label(config, text="URL").pack(side="left")
    self.api_url_var = tk.StringVar()
    ttk.Entry(config, textvariable=self.api_url_var, width=40).pack(side="left", padx=4)
    ttk.Label(config, text="Key").pack(side="left")
    self.api_key_var = tk.StringVar()
    ttk.Entry(config, textvariable=self.api_key_var, width=20, show="*").pack(side="left",
                                                                             padx=4)
    register = ttk.Button(config, text="Register", command=self.register_external_api)
    register.pack(side="left", padx=4)
    actions = ttk.Frame(frame)
    actions.pack(fill="x", padx=15)
    test = ttk.Button(actions, text="Test connection", command=self.test_api_connection)
    test.pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="State of each service", command=self.show_api_performance).pack(
        side="left", padx=(0, 6))
    compare = ttk.Button(actions, text="Compare for the text below…",
                         command=self.compare_api_results)
    compare.pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Model estimate for the text below",
               command=self.run_ensemble_prediction).pack(side="left")
    common.officer_only(self, register, test, compare)
    self.api_text = scrolledtext.ScrolledText(frame, wrap="word", height=12)
    self.api_text.pack(fill="both", expand=True, padx=15, pady=(8, 15))


def _gateway(self):
    gateway = getattr(self.detector, "api_gateway", None)
    if gateway is None:
        raise ValueError("The API gateway did not start: "
                         + self.detector.component_errors.get("api_gateway", ""))
    return gateway


def register_external_api(self):
    name = self.api_service_var.get().strip()
    url = self.api_url_var.get().strip()
    key = self.api_key_var.get().strip()
    if not name or not url.startswith("https://") or not key:
        messagebox.showwarning(common.TITLE, "Give a name, an https:// URL and the key.",
                               parent=self.root)
        return
    if common.call(self, self.detector.require_officer) is None:
        return
    gateway = common.call(self, _gateway, self)
    if gateway is None:
        return
    gateway.register_api(name, {"url": url, "api_key": key, "timeout": 30,
                                "max_requests_per_minute": 30, "weight": 1.0})
    self.api_key_var.set("")
    self.update_status(f"Service '{name}' registered for this session")


def test_api_connection(self):
    gateway = common.call(self, _gateway, self)
    if gateway is None:
        return
    name = self.api_service_var.get().strip()
    if name not in gateway.api_configs:
        messagebox.showwarning(common.TITLE, "Register the service first.", parent=self.root)
        return
    result = gateway.call_api(name, TEST_SENTENCE)
    if result:
        messagebox.showinfo(common.TITLE, f"'{name}' answered in "
                                          f"{result.get('response_time', 0):.2f} s.",
                            parent=self.root)
    else:
        messagebox.showerror(common.TITLE, f"'{name}' did not answer (see the log).",
                             parent=self.root)


def show_api_performance(self):
    gateway = common.call(self, _gateway, self)
    if gateway is None:
        return
    state = {}
    for name in gateway.api_configs:
        breaker = gateway.circuit_breakers.get(name, {})
        state[name] = {"url": gateway.api_configs[name]["url"],
                       "calls in the last minute": len(gateway.rate_limits.get(name, {})
                                                       .get("requests", [])),
                       "limit per minute": gateway.rate_limits.get(name, {}).get("max_per_minute"),
                       "recent failures": breaker.get("failures"),
                       "paused after failures": breaker.get("is_open")}
    common.text_window(self, "External services", state or "No service registered.", 640, 420)


def compare_api_results(self):
    gateway = common.call(self, _gateway, self)
    if gateway is None or common.call(self, self.detector.require_officer) is None:
        return
    text = self.api_text.get("1.0", "end").strip()
    if not text or not gateway.api_configs:
        messagebox.showwarning(common.TITLE, "Register a service and paste the text.",
                               parent=self.root)
        return
    if not messagebox.askyesno(common.TITLE, "This sends the text to "
                               + ", ".join(gateway.api_configs) + " outside the university. "
                               "Only do this where the student has been told. Continue?",
                               parent=self.root):
        return
    from education_system.systems.university.application.integrity import ai_indicators
    ours = ai_indicators.assess(text)
    out = {"this university's reading": f"{ours.get('level')} (strength "
                                        f"{ours.get('strength')})"}
    for name in gateway.api_configs:
        result = gateway.call_api(name, text)
        out[name] = (f"score {result.get('score')}, confidence {result.get('confidence')}"
                     if result else "no answer")
    out["note"] = "Outside scores are information only, never evidence."
    common.text_window(self, "Compared", out, 600, 380)


def run_ensemble_prediction(self):
    trainer = getattr(self.detector, "advanced_ml_trainer", None)
    text = self.api_text.get("1.0", "end").strip()
    if trainer is None or not text:
        messagebox.showwarning(common.TITLE, "Paste a text first.", parent=self.root)
        return
    result = common.call(self, trainer.predict_ensemble, text)
    if result is None:
        messagebox.showinfo(common.TITLE, "No estimate: either no model is active (train one "
                                          "under Model Management) or the text is too short.",
                            parent=self.root)
        return
    self.show_ensemble_results(result)


def show_ensemble_results(self, result):
    common.text_window(self, "Model estimate", {**result, "note": (
        "How often readings like this one were upheld when staff reviewed them. "
        "Informational: it never sets a flag.")}, 560, 360)


# ── visual analysis ─────────────────────────────────────────────────────


def create_visual_analysis_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Visual analysis", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                      pady=(15, 6))
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", padx=15)
    ttk.Button(buttons, text="🔥 Sentence shading", command=self.generate_text_heatmap).pack(
        side="left", padx=(0, 6))
    ttk.Button(buttons, text="📈 Paragraph flow", command=self.generate_writing_flow).pack(
        side="left", padx=(0, 6))
    ttk.Button(buttons, text="📊 Complexity", command=self.generate_complexity_viz).pack(
        side="left")
    panes = ttk.PanedWindow(frame, orient="vertical")
    panes.pack(fill="both", expand=True, padx=15, pady=(8, 15))
    top = ttk.LabelFrame(panes, text="Text", padding=4)
    self.visual_text = scrolledtext.ScrolledText(top, wrap="word", height=8)
    self.visual_text.pack(fill="both", expand=True)
    self.visual_display_frame = ttk.LabelFrame(panes, text="Result", padding=4)
    panes.add(top, weight=1)
    panes.add(self.visual_display_frame, weight=2)


def _visual_text(self):
    text = self.visual_text.get("1.0", "end").strip()
    if not text:
        messagebox.showwarning(common.TITLE, "Paste a text first.", parent=self.root)
    return text


def _clear(self):
    for widget in self.visual_display_frame.winfo_children():
        widget.destroy()


def generate_text_heatmap(self):
    """Shade each sentence by how much of it lies in an indicator passage."""
    text = _visual_text(self)
    if not text:
        return
    from education_system.systems.university.application.integrity import ai_indicators
    reading = ai_indicators.assess(text, min_words=1)
    covered = [0] * len(text)
    for p in reading.get("passages", []):
        for i in range(p["start"], min(p["end"], len(text))):
            covered[i] = 1
    sentences = []
    for match in re.finditer(r"[^.!?]+[.!?]*", text):
        start, end = match.span()
        if text[start:end].strip():
            share = sum(covered[start:end]) / max(1, end - start)
            sentences.append({"start": start, "end": end, "share": share})
    self.display_text_heatmap({"text": text, "sentences": sentences, "reading": reading})


def display_text_heatmap(self, heatmap_data):
    _clear(self)
    widget = tk.Text(self.visual_display_frame, wrap="word", height=12)
    key = ttk.Frame(self.visual_display_frame)
    key.pack(side="bottom", fill="x")
    shades = (("none", "#ffffff", 0.0), ("a little", "#fef3c7", 0.01),
              ("some", "#fde68a", 0.25), ("most", "#fca5a5", 0.6))
    for name, colour, _floor in shades:
        widget.tag_configure(name, background=colour)
        tk.Label(key, text=f" {name} ", bg=colour, relief="solid", bd=1).pack(side="left", padx=2)
    ttk.Label(key, text="share of the sentence inside an indicator passage").pack(side="left",
                                                                                padx=6)
    widget.pack(fill="both", expand=True)
    widget.insert("1.0", heatmap_data["text"])
    for s in heatmap_data["sentences"]:
        name = next(n for n, _c, floor in reversed(shades) if s["share"] >= floor)
        widget.tag_add(name, f"1.0+{s['start']}c", f"1.0+{s['end']}c")
    widget.configure(state="disabled")
    reading = heatmap_data.get("reading") or {}
    ttk.Label(self.visual_display_frame, text=common.summary(reading)).pack(side="bottom",
                                                                           anchor="w")


def generate_writing_flow(self):
    text = _visual_text(self)
    if not text:
        return
    analyzer = getattr(self.detector, "visual_analyzer", None)
    if analyzer is None:
        messagebox.showerror(common.TITLE, "Visual analysis is not available.", parent=self.root)
        return
    flow = common.call(self, analyzer.generate_writing_flow_visualization, text)
    if flow is not None:
        self.display_writing_flow(flow)


def display_writing_flow(self, flow_data):
    _clear(self)
    ttk.Label(self.visual_display_frame,
              text=f"Paragraphs: {flow_data.get('total_paragraphs', 0)}, average "
                   f"{flow_data.get('avg_paragraph_length', 0):.1f} words, "
                   f"{flow_data.get('transition_frequency', 0):.0%} open with a connective"
              ).pack(anchor="w")
    cols = (("n", "Paragraph", 80), ("words", "Words", 70), ("sentences", "Sentences", 80),
            ("avg", "Words per sentence", 130), ("transition", "Connective", 90),
            ("complexity", "Complexity", 90))
    tree = ttk.Treeview(self.visual_display_frame, columns=[c[0] for c in cols],
                        show="headings", height=10)
    for col, label, width in cols:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor="w")
    for p in flow_data.get("flow_data", []):
        tree.insert("", "end", values=(p.get("paragraph_index", 0) + 1, p.get("word_count"),
                                       p.get("sentence_count"),
                                       f"{p.get('avg_sentence_length', 0):.1f}",
                                       "yes" if p.get("has_transition") else "",
                                       f"{p.get('complexity_score', 0):.2f}"))
    tree.pack(fill="both", expand=True)


def generate_complexity_viz(self):
    text = _visual_text(self)
    if not text:
        return
    _clear(self)
    words = re.findall(r"[A-Za-z']+", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    unique = len({w.lower() for w in words})
    figures = (("Words", len(words)), ("Sentences", len(sentences)),
               ("Average word length", f"{sum(map(len, words)) / max(1, len(words)):.1f} letters"),
               ("Average sentence length", f"{len(words) / max(1, len(sentences)):.1f} words"),
               ("Different words", unique),
               ("Different words / words", f"{unique / max(1, len(words)):.2f}"))
    for label, value in figures:
        row = ttk.Frame(self.visual_display_frame)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=f"{label}:").pack(side="left")
        ttk.Label(row, text=str(value), font=("Segoe UI", 10, "bold")).pack(side="right")
    ttk.Label(self.visual_display_frame, wraplength=700, text=(
        "Plain figures about the text. They are not indicators: vocabulary and sentence "
        "length vary with the subject and the writer.")).pack(anchor="w", pady=6)
