"""Anti-evasion, the audit chain and benchmarking.

* **Anti-evasion** — counts disguised characters in a text: look-alike
  letters from another alphabet sitting beside Latin letters, hidden
  characters inside words and text-direction overrides. A fact about the
  text, not a judgement about who wrote it; ordinary Greek or Cyrillic
  words are not counted.
* **Audit chain** — every reading, review, referral, model change and
  export is written to a hash-chained log in the database
  (``ai_audit_chain``). Verifying walks the chain and names the first
  block whose link or contents were changed (or that is missing).
* **Benchmarking** — this institution's readings over a period against the
  other institutions recorded in the same database.
"""

import logging

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


def _post(widget, callback):
    """Run *callback* on the Tk main loop, from any thread."""
    try:
        if widget.winfo_exists():
            widget.after(0, callback)
    except (tk.TclError, RuntimeError):
        pass


def _tab(self, label, builder):
    """Older notebook-tab entry points build the same view in a tab."""
    notebook = self.__dict__.get("notebook")
    if notebook is None:
        return None
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=label)
    builder(frame)
    return frame


# ── anti-evasion ────────────────────────────────────────────────────────


def create_adversarial_detection_tab(self):
    return _tab(self, "🛡️ Anti-Evasion", self.create_adversarial_detection_view)


def create_adversarial_detection_view(self, parent):
    """Paste a text and count its disguised characters."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Disguised characters", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                           pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "Counts look-alike letters from another alphabet next to Latin letters, hidden "
        "characters inside words and text-direction overrides — tricks used to get past "
        "checks. Ordinary Greek or Cyrillic words (maths, names, quotations) are not counted. "
        "Every full reading includes this count too.")).pack(anchor="w", padx=15)
    buttons = ttk.Frame(frame)
    buttons.pack(side="bottom", fill="x", padx=15, pady=10)
    self.adversarial_text = scrolledtext.ScrolledText(frame, wrap="word", height=14)
    self.adversarial_text.pack(fill="both", expand=True, padx=15, pady=8)
    ttk.Button(buttons, text="Check this text",
               command=self.test_adversarial_detection).pack(side="left")


def test_adversarial_detection(self):
    """Check the pasted text."""
    widget = self.__dict__.get("adversarial_text")
    text = widget.get("1.0", "end").strip() if widget is not None else ""
    if not text:
        messagebox.showwarning(common.TITLE, "Paste a text to check.", parent=self.root)
        return
    detector = getattr(self.detector, "adversarial_detector", None)
    if detector is None:
        messagebox.showerror(common.TITLE, "The anti-evasion check is not available: "
                             + self.detector.component_errors.get("adversarial_detector", ""),
                             parent=self.root)
        return
    result = common.call(self, detector.detect_evasion_attempts, text)
    if result is not None:
        self.show_adversarial_results(result)


def show_adversarial_results(self, result):
    data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    evidence = data.get("evidence") or {}
    details = evidence.get("details") or {}
    lines = [
        f"Disguised characters: {details.get('disguised_characters', 0)}",
        f"Text-direction overrides: {details.get('direction_marks', 0)}",
        f"Asked about from: {details.get('review_from', '—')} characters",
        f"Found: {', '.join(evidence.get('evasion_techniques') or []) or 'nothing'}",
        "",
        evidence.get("note", ""),
    ]
    common.text_window(self, "Disguised characters", "\n".join(lines), 640, 360)


# ── audit chain ─────────────────────────────────────────────────────────


def create_blockchain_audit_tab(self):
    return _tab(self, "🔗 Audit chain", self.create_blockchain_audit_view)


def create_blockchain_audit_view(self, parent):
    """The persisted chain: head, verify, and the latest blocks."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Audit chain", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                  pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "Every reading, review, referral, model change and export is a block holding the hash "
        "of the block before it, kept in the database. Changing or deleting any block breaks "
        "the chain from that point, and Verify names where.")).pack(anchor="w", padx=15)
    info = ttk.LabelFrame(frame, text="Chain", padding=10)
    info.pack(fill="x", padx=15, pady=8)
    self.chain_length_label = ttk.Label(info, text="Blocks: —")
    self.chain_length_label.pack(anchor="w")
    self.pending_transactions_label = ttk.Label(info, text="Latest: —")
    self.pending_transactions_label.pack(anchor="w")
    self.chain_verify_label = ttk.Label(info, text="Not verified yet")
    self.chain_verify_label.pack(anchor="w")
    controls = ttk.Frame(frame)
    controls.pack(fill="x", padx=15)
    ttk.Button(controls, text="✔ Verify the chain",
               command=self.verify_blockchain_integrity).pack(side="left", padx=(0, 6))
    ttk.Button(controls, text="🔄 Refresh", command=self.update_blockchain_display).pack(
        side="left", padx=(0, 6))
    ttk.Button(controls, text="📜 Whole history",
               command=self.view_blockchain_history).pack(side="left")
    listing = ttk.LabelFrame(frame, text="Latest blocks", padding=6)
    listing.pack(fill="both", expand=True, padx=15, pady=(8, 15))
    self.chain_tree = _blocks_tree(listing)
    self.update_blockchain_display()


def _blocks_tree(parent, height=14):
    cols = (("index", "Block", 60), ("timestamp", "When", 150), ("event", "Event", 170),
            ("actor", "Who", 110), ("payload", "Detail", 380), ("hash", "Hash", 140))
    tree = ttk.Treeview(parent, columns=[c[0] for c in cols], show="headings", height=height)
    for col, label, width in cols:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor="w")
    tree.pack(fill="both", expand=True)
    return tree


def _fill_blocks(tree, blocks):
    import json
    tree.delete(*tree.get_children())
    for b in blocks:
        tree.insert("", "end", values=(b["index"], b["timestamp"], b["event"], b["actor"],
                                       json.dumps(b["payload"], default=str)[:300],
                                       str(b["hash"])[:16] + "…"))


def _chain(self):
    chain = getattr(self.detector, "blockchain_audit", None)
    if chain is None:
        raise ValueError("The audit chain is not available: "
                         + self.detector.component_errors.get("blockchain_audit", ""))
    return chain


def mine_blockchain_block(self):
    """Kept for older screens: blocks are written as events happen, so
    there is nothing waiting to be added — this refreshes the view."""
    self.update_blockchain_display()
    messagebox.showinfo(common.TITLE, "Blocks are written as events happen; nothing is "
                                      "waiting to be added.", parent=self.root)


def verify_blockchain_integrity(self):
    """Walk the whole chain and say whether it is intact."""
    chain = common.call(self, _chain, self)
    if chain is None:
        return
    found = common.call(self, chain.verify_chain)
    if found is None:
        return
    label = self.__dict__.get("chain_verify_label")
    if found.get("ok"):
        text = f"Intact: {found['blocks']} block(s) checked"
        messagebox.showinfo(common.TITLE, text, parent=self.root)
    else:
        text = (f"BROKEN at block {found.get('first_bad')}: {found.get('problem')} "
                f"({found.get('blocks')} block(s) read)")
        messagebox.showerror(common.TITLE, text, parent=self.root)
    if label is not None and label.winfo_exists():
        label.config(text=text, foreground=self.colors["success" if found.get("ok") else "danger"])


def view_blockchain_history(self):
    """Every block, newest first."""
    chain = common.call(self, _chain, self)
    if chain is None:
        return
    blocks = common.call(self, chain.get_blocks, 5000)
    if blocks is None:
        return
    win = tk.Toplevel(self.root)
    win.title("Audit chain — every block")
    win.geometry(f"{min(1100, win.winfo_screenwidth() - 60)}x"
                 f"{min(640, win.winfo_screenheight() - 100)}")
    win.transient(self.root)
    ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=6)
    _fill_blocks(_blocks_tree(win, 24), blocks)


def update_blockchain_display(self):
    """Head of the chain and its latest blocks."""
    label = self.__dict__.get("chain_length_label")
    if label is None or not label.winfo_exists():
        return
    chain = getattr(self.detector, "blockchain_audit", None)
    if chain is None:
        label.config(text="The audit chain is not available")
        return
    try:
        head = chain.head()
        blocks = chain.get_blocks(200)
    except Exception as exc:
        logger.warning("Audit chain read failed: %s", exc)
        label.config(text=f"The audit chain could not be read: {exc}")
        return
    count = 0 if head.get("idx") is None else head["idx"] + 1
    label.config(text=f"Blocks: {count}")
    self.pending_transactions_label.config(
        text=f"Latest: block {head.get('idx')} at {head.get('at') or '—'}, hash "
             f"{str(head.get('hash'))[:20]}…" if count else "Latest: none yet")
    _fill_blocks(self.chain_tree, blocks)


# ── benchmarking ────────────────────────────────────────────────────────


def create_benchmarking_tab(self):
    return _tab(self, "📊 Benchmarking", self.create_benchmarking_view)


def create_benchmarking_view(self, parent):
    """This institution's readings against the others recorded here."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Benchmarking", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                   pady=(15, 2))
    row = ttk.Frame(frame)
    row.pack(fill="x", padx=15, pady=8)
    ttk.Label(row, text="Institution id:").pack(side="left")
    self.benchmark_institution_var = tk.StringVar()
    fl = getattr(self.detector, "federated_learning", None)
    if fl is not None:
        self.benchmark_institution_var.set(common.call(self, lambda: fl.institution_id,
                                                       quiet=True) or "")
    ttk.Entry(row, textvariable=self.benchmark_institution_var, width=20).pack(side="left",
                                                                              padx=(5, 15))
    ttk.Label(row, text="Period:").pack(side="left")
    self.benchmark_period_var = tk.StringVar(value="1_month")
    ttk.Combobox(row, textvariable=self.benchmark_period_var, state="readonly",
                 values=["1_month", "3_months", "1_year"], width=12).pack(side="left", padx=5)
    ttk.Button(row, text="Compare", command=self.generate_benchmark_report).pack(side="left",
                                                                               padx=10)
    self.benchmark_results_frame = ttk.Frame(frame)
    self.benchmark_results_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))


def generate_benchmark_report(self):
    institution_id = self.benchmark_institution_var.get().strip()
    if not institution_id:
        messagebox.showwarning(common.TITLE, "Enter the institution id (set it under Federated "
                                             "Learning).", parent=self.root)
        return
    bench = getattr(self.detector, "institution_benchmarking", None)
    if bench is None:
        messagebox.showerror(common.TITLE, "Benchmarking is not available.", parent=self.root)
        return
    report = common.call(self, bench.generate_benchmark_report, institution_id,
                         self.benchmark_period_var.get())
    if report is not None:
        self.display_benchmark_report(report)


def display_benchmark_report(self, report):
    for widget in self.benchmark_results_frame.winfo_children():
        widget.destroy()
    if report.get("error"):
        ttk.Label(self.benchmark_results_frame, text=f"Error: {report['error']}").pack(anchor="w")
        return
    for title, key in (("This institution", "institution_metrics"),
                       ("Other institutions", "benchmarks"),
                       ("Compared", "performance_indicators")):
        values = report.get(key) or {}
        box = ttk.LabelFrame(self.benchmark_results_frame, text=title, padding=8)
        box.pack(fill="x", pady=4)
        if not values:
            ttk.Label(box, text="No data for this period").pack(anchor="w")
        for name, value in values.items():
            ttk.Label(box, text=f"{name.replace('_', ' ').capitalize()}: {value}").pack(anchor="w")
