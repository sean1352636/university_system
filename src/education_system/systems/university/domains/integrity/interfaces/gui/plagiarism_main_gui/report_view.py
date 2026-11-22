"""The similarity report: the checked text with every matching passage
highlighted, and the matched sources.

Students see their own text and what kind of source matched it; staff also
see, passage by passage, the matching text in the source, the AI-detection
score for the same work, can record their review decision and (when the
integrity settings allow it) search published sources from here.

Word-for-word passages are highlighted yellow, reworded (paraphrased)
passages orange. Matches with classmates on a module that allows
collaboration are listed but not highlighted: they do not count.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import review
from education_system.systems.university.infrastructure.ui.record_screens import (
    Field, ask, call, info, nice,
)

DECISIONS = [("no_concern", "No concern (properly cited / common phrasing)"),
             ("false_positive", "False positive (the match is wrong)"),
             ("refer", "Refer as an integrity case")]


EXACT_COLOUR = "#ffe08a"
REWORDED_COLOUR = "#ffb870"
PEER_LABEL = "classmate on this assignment — collaboration allowed, not counted"


def highlight(text_widget, text, passages, tag="match") -> None:
    """Put ``text`` in ``text_widget`` with ``passages`` (start/end
    character offsets) highlighted: word-for-word in yellow, reworded
    (``kind == 'paraphrase'``) in orange."""
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", text)
    text_widget.tag_configure(tag, background=EXACT_COLOUR)
    text_widget.tag_configure("reworded", background=REWORDED_COLOUR)
    for p in passages:
        if p.get("start") is None or p.get("end") is None:
            continue
        name = "reworded" if p.get("kind") == "paraphrase" else tag
        text_widget.tag_add(name, f"1.0+{int(p['start'])}c", f"1.0+{int(p['end'])}c")
    text_widget.configure(state="disabled")


def score_lines(rep) -> list[str]:
    """The paraphrase and disguised-character lines of a report."""
    lines = []
    if rep.get("paraphrase_score"):
        lines.append(f"Reworded from a source: {float(rep['paraphrase_score']):.0%} of the words "
                     "(highlighted orange)")
    if rep.get("obfuscated_chars"):
        lines.append(f"Disguised characters: {rep['obfuscated_chars']} (look-alike letters from "
                     "another alphabet or hidden characters inside words)")
    return lines


def _scrolled_text(parent, height=12):
    frame = ttk.Frame(parent)
    widget = tk.Text(frame, wrap="word", height=height, font=("Segoe UI", 10), padx=8, pady=6)
    bar = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
    widget.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    widget.pack(side="left", fill="both", expand=True)
    return frame, widget


class ReportWindow(tk.Toplevel):
    """One result. ``on_change`` is called after a review is recorded."""

    def __init__(self, parent, who, result_id, on_change=None):
        super().__init__(parent)
        self.who = who
        self.result_id = result_id
        self.on_change = on_change
        self.title(f"Similarity report {result_id}")
        self.transient(parent.winfo_toplevel())
        width = min(1200, self.winfo_screenwidth() - 80)
        height = min(760, self.winfo_screenheight() - 100)
        self.geometry(f"{width}x{height}")
        self.minsize(800, 520)
        # A write: viewing a report is audited.
        self.report = call(self, review.result_detail, who, result_id, write=True)
        if self.report is None:
            self.after(10, self.destroy)
            return
        self._build()

    def _build(self):
        rep = self.report
        bar = ttk.Frame(self, padding=(8, 4))
        bar.pack(side="bottom", fill="x")                  # packed first: stays on screen
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(bar, text="Export…", command=self.export_report).pack(side="left", padx=4)
        ttk.Button(bar, text="E-mail…", command=self.email_report).pack(side="left", padx=4)
        if self.who.is_staff and rep.get("submission_id"):
            ttk.Button(bar, text="Open uploaded file", command=self.open_original).pack(
                side="left", padx=4)
        if self.who.is_staff and not rep.get("case_id") and rep.get("review_status") in (
                "pending", "not_needed"):
            ttk.Button(bar, text="Record review…", command=self.record_review).pack(
                side="right", padx=4)
        if self.who.is_staff and call(self, access.setting, "external_checks",
                                      quiet=True) == "1":
            ttk.Button(bar, text="Search published sources", command=self.search_external).pack(
                side="right", padx=4)
        head = ttk.Frame(self, padding=(10, 8))
        head.pack(side="top", fill="x")
        ttk.Label(head, text=rep.get("title") or "Document", font=("Segoe UI", 13, "bold")).pack(
            anchor="w")
        summary = (f"Similarity {float(rep['similarity_score'] or 0):.0%} · {nice(rep['status'])}"
                   f" · review: {nice(rep.get('review_status'))}"
                   f" · {rep.get('words_checked') or 0} words checked, "
                   f"{rep.get('words_excluded') or 0} quoted/reference words left out")
        ttk.Label(head, text=summary).pack(anchor="w")
        for line in score_lines(rep):
            ttk.Label(head, text=line, foreground="#b0620a").pack(anchor="w")
        signal = rep.get("ai_signal")
        if signal:
            line = ttk.Frame(head)
            line.pack(anchor="w", fill="x")
            ttk.Label(line, text=f"AI-writing reading for this work: "
                                 f"{nice(signal.get('level')) or 'recorded'} "
                                 f"({str(signal.get('created_at') or '')[:10]}) — indicators, "
                                 "not evidence", foreground="#555555").pack(side="left")
            ttk.Button(line, text="Open reading",
                       command=lambda: self.open_ai_reading(signal["id"])).pack(side="left",
                                                                                padx=6)
        if rep.get("external_checked_at"):
            ttk.Label(head, text=f"Published sources searched {rep['external_checked_at'][:16]}",
                      foreground="#555555").pack(anchor="w")
        if rep.get("report"):
            ttk.Label(head, text=rep["report"], wraplength=1000, foreground="#555555").pack(
                anchor="w")
        if rep.get("review_note"):
            ttk.Label(head, text=f"Reviewer's note: {rep['review_note']}", wraplength=1000).pack(
                anchor="w")
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=4)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        ttk.Label(left, text="Checked text (matching passages highlighted)").pack(anchor="w")
        frame, self.text = _scrolled_text(left)
        frame.pack(fill="both", expand=True)
        passages = [p for m in rep["matches"] if m.get("counted", True) for p in m["passages"]]
        highlight(self.text, rep["text"], passages)
        self._build_sources(right)

    def _build_sources(self, parent):
        ttk.Label(parent, text="Matched sources").pack(anchor="w")
        self.sources = ttk.Treeview(parent, columns=("source", "kind", "score", "words"),
                                    show="headings", height=6, selectmode="browse")
        for key, heading, width in (("source", "Source", 240), ("kind", "Match", 90),
                                    ("score", "Score", 60), ("words", "Words", 60)):
            self.sources.heading(key, text=heading)
            self.sources.column(key, width=width, stretch=key == "source")
        self.sources.pack(fill="x")
        for m in self.report["matches"]:
            counted = m.get("counted", True)
            source = m["source"] if counted else f"{m['source']} ({PEER_LABEL})"
            kind = "not counted" if not counted else {"paraphrase": "reworded"}.get(
                m.get("match_kind"), "word for word")
            self.sources.insert("", "end", iid=str(m["match_id"]),
                                values=(source, kind, f"{m['score']:.0%}", m["matched_words"]))
        self.sources.bind("<<TreeviewSelect>>", lambda _e: self._show_match())
        ttk.Label(parent, text="Passages" + (" (theirs below each of yours)"
                                             if self.who.is_staff else "")).pack(anchor="w")
        frame, self.passages = _scrolled_text(parent, height=10)
        frame.pack(fill="both", expand=True)
        self.passages.tag_configure("own", background="#ffe08a")
        self.passages.tag_configure("src", background="#cfe3ff")
        self.passages.tag_configure("label", foreground="#555555")
        if not self.report["matches"]:
            self.passages.insert("end", "No matching text was found.", ("label",))
        self.passages.configure(state="disabled")

    def _show_match(self):
        sel = self.sources.selection()
        match = next((m for m in self.report["matches"] if sel and str(m["match_id"]) == sel[0]),
                     None)
        self.passages.configure(state="normal")
        self.passages.delete("1.0", "end")
        if match and not match.get("counted", True):
            self.passages.insert("end", f"Not counted: {PEER_LABEL}.\n\n", ("label",))
        for n, p in enumerate(match["passages"] if match else [], start=1):
            kind = " — reworded" if p.get("kind") == "paraphrase" else ""
            self.passages.insert("end", f"Passage {n} ({p['words']} words{kind})\n", ("label",))
            self.passages.insert("end", p["text"] + "\n", ("own",))
            if "source_text" in p:
                self.passages.insert("end", "Source:\n", ("label",))
                self.passages.insert("end", (p["source_text"] or "—") + "\n", ("src",))
            self.passages.insert("end", "\n")
        self.passages.configure(state="disabled")
        if match and match["passages"]:
            self.text.see(f"1.0+{int(match['passages'][0]['start'])}c")

    def open_ai_reading(self, ai_result_id):
        from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.ai_writing import (  # noqa: E501
            ReadingWindow,
        )
        ReadingWindow(self, self.who, ai_result_id, on_change=self.on_change)

    def record_review(self):
        values = ask(self, "Record review", [
            Field("decision", "Decision", "combo", DECISIONS, required=True),
            Field("case_type", "Case type (if referred)", "combo", list(review.CASE_TYPES)),
            Field("note", "Reason", "multiline", required=True)],
            {"case_type": "plagiarism"})
        if not values:
            return
        result = call(self, review.review, self.who, self.result_id, values["decision"],
                      values["note"], case_type=values["case_type"] or "plagiarism", write=True)
        if result is None:
            return
        info(self, f"Case {result['case_id']} opened and the student told."
             if result.get("case_id") else "Review recorded.")
        if self.on_change:
            self.on_change()
        self.destroy()

    def search_external(self):
        from education_system.systems.university.application.integrity import (
            external as integrity_external,
        )
        found = call(self, integrity_external.search_external, self.who,
                     self.report["document_id"], write=True)
        if found is None:
            return
        note = (f"{found['queries']} phrase(s) searched; {found['sources_added']} new published "
                "source(s) added.")
        if found["errors"]:
            note += "\nSome searches failed: " + "; ".join(found["errors"][:3])
        info(self, note + "\nThe work was checked again; the new report opens now.")
        if self.on_change:
            self.on_change()
        ReportWindow(self.master, self.who, found["result_id"], on_change=self.on_change)
        self.destroy()

    def export_report(self):
        from tkinter import filedialog

        from education_system.systems.university.application.integrity import tools
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("HTML", "*.html"), ("CSV", "*.csv")],
            initialfile=f"similarity_report_{self.result_id}.pdf")
        if not path:
            return
        fmt = path.rsplit(".", 1)[-1].lower()
        if fmt not in tools.REPORT_FORMATS:
            info(self, "Save as .pdf, .html or .csv.")
            return
        data = call(self, tools.export_report, self.who, self.result_id, fmt, write=True)
        if data is not None:
            with open(path, "wb") as fh:
                fh.write(data)
            info(self, "Report saved.")

    def email_report(self):
        from education_system.systems.university.application.integrity import tools
        choices = [("me", "To me")]
        if self.who.is_staff:
            choices.append(("student", "To the student (once the report is released)"))
        values = ask(self, "E-mail this report", [
            Field("recipient", "Send", "combo", choices, required=True),
            Field("note", "Note (optional)", "multiline")], {"recipient": "me"})
        if values and call(self, tools.email_report, self.who, self.result_id,
                           values["recipient"], values["note"], write=True) is not None:
            info(self, "The report has been sent.")

    def open_original(self):
        from education_system.systems.university.application.integrity import tools
        from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.case_view import (  # noqa: E501
            _open_path,
        )
        found = call(self, tools.original_file, self.who, self.report["document_id"], write=True)
        if found:
            _open_path(found["path"])
