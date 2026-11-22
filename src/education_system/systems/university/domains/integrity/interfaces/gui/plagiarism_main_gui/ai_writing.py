"""AI-writing readings in the Academic Integrity window: the staff tab
(readings on their modules, review, reply, read a submission), the
student's tab (their own released readings, comment) and the window that
shows one reading with its passages highlighted.

The rules are in ``university/application/integrity/ai`` and
``ai_indicators``. A reading is a set of indicators, never proof; the
screens say so and never call work "AI generated".
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import ai as integrity_ai
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui import (  # noqa: E501
    pickers,
)
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.report_view import (  # noqa: E501
    _scrolled_text,
)
from education_system.systems.university.infrastructure.ui.record_screens import (
    Field, RecordTab, ask, ask_text, call, info, make_tree, nice,
)

PASSAGE_COLOURS = {"artefact": "#f4a6a6", "stock": "#ffe08a", "opener": "#bfe0f7"}
PASSAGE_LABELS = {"artefact": "leftover chat text", "stock": "stock phrasing",
                  "opener": "formulaic opening"}
STATUSES = ("flagged", "waiting review", "reviewed", "all")


def strength(row) -> str:
    level = row.get("level") or ""
    if level.startswith("not "):
        return "—"
    return f"{float(row.get('ai_score') or 0):.2f}"


def highlight_kinds(text_widget, text, passages) -> None:
    """``text`` in ``text_widget`` with each passage tagged by its kind."""
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", text)
    for kind, colour in PASSAGE_COLOURS.items():
        text_widget.tag_configure(kind, background=colour)
    for p in passages:
        if p.get("start") is None or p.get("end") is None:
            continue
        text_widget.tag_add(p.get("kind") or "stock", f"1.0+{int(p['start'])}c",
                            f"1.0+{int(p['end'])}c")
    text_widget.configure(state="disabled")


def indicator_lines(reading) -> list[str]:
    lines = [f"{i['label']}: {i['shown']} — {i['meaning']}" for i in reading.get("indicators")
             or []]
    if reading.get("note"):
        lines.append(reading["note"])
    return lines or ["No indicators recorded."]


def comment_lines(reading) -> list[str]:
    return [f"{c['at'][:16]}  {c['author']}: {c['comment']}" for c in reading.get("comments")
            or []] or ["None"]


class ReadingWindow(tk.Toplevel):
    """One reading: the indicators, the text with the passages behind them
    highlighted, and the comments. ``on_change`` runs after a write."""

    def __init__(self, parent, who, ai_result_id, on_change=None):
        super().__init__(parent)
        self.who = who
        self.ai_result_id = ai_result_id
        self.on_change = on_change
        self.title(f"AI-writing reading {ai_result_id}")
        self.transient(parent.winfo_toplevel())
        width = min(1200, self.winfo_screenwidth() - 80)
        height = min(760, self.winfo_screenheight() - 100)
        self.geometry(f"{width}x{height}")
        self.minsize(min(800, width), min(520, height))
        # A write: staff viewing a reading is audited.
        self.reading = call(self, integrity_ai.result_detail, who, ai_result_id, write=True)
        if self.reading is None:
            self.after(10, self.destroy)
            return
        self._build()

    def _build(self):
        r = self.reading
        bar = ttk.Frame(self, padding=(8, 4))
        bar.pack(side="bottom", fill="x")                  # packed first: stays on screen
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(bar, text="Comment…" if self.who.is_student else "Reply…",
                   command=self.comment).pack(side="right", padx=4)
        if self.who.is_staff and not r.get("decision"):
            ttk.Button(bar, text="Refer as a case…",
                       command=lambda: self.review("refer")).pack(side="right", padx=4)
            ttk.Button(bar, text="No concern…",
                       command=lambda: self.review("no_concern")).pack(side="right", padx=4)
        key = ttk.Frame(bar)
        key.pack(side="left")
        for kind, colour in PASSAGE_COLOURS.items():
            tk.Label(key, text=f" {PASSAGE_LABELS[kind]} ", background=colour).pack(
                side="left", padx=2)
        head = ttk.Frame(self, padding=(10, 8))
        head.pack(side="top", fill="x")
        ttk.Label(head, text=r.get("title") or "Work", font=("Segoe UI", 13, "bold")).pack(
            anchor="w")
        ttk.Label(head, text=r["notice"], wraplength=1100, foreground="#8a1c1c").pack(anchor="w")
        ttk.Label(head, text=f"{nice(r.get('level'))} · strength {strength(r)} · "
                             f"{r.get('words_checked') or 0} words read · module "
                             f"{r.get('course_code') or '—'} · student {r.get('student_id')} · "
                             f"{str(r.get('created_at') or '')[:16]}").pack(anchor="w")
        if r.get("decision"):
            ttk.Label(head, text=f"Reviewed: {nice(r['decision'])} by {r.get('reviewed_by')} — "
                                 f"{r.get('note') or ''}"
                                 + (f" (case {r['case_id']})" if r.get("case_id") else ""),
                      wraplength=1100).pack(anchor="w")
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=4)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        frame, text = _scrolled_text(left, height=20)
        frame.pack(fill="both", expand=True)
        highlight_kinds(text, r.get("text") or "(text removed under the retention policy)",
                        r.get("passages") or [])
        ttk.Label(right, text="Indicators", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tree = make_tree(right, [("label", "Indicator", 170), ("shown", "Reading", 120)],
                         height=6)
        for n, i in enumerate(r.get("indicators") or []):
            tree.insert("", "end", iid=str(n), values=[i["label"], i["shown"]])
        meaning = ttk.Label(right, text="Select an indicator to see what it means.",
                            wraplength=420, foreground="#555555")
        meaning.pack(anchor="w", pady=4)

        def show_meaning(_event=None):
            sel = tree.selection()
            if sel:
                meaning.configure(text=r["indicators"][int(sel[0])]["meaning"])
        tree.bind("<<TreeviewSelect>>", show_meaning)
        if r.get("note"):
            ttk.Label(right, text=r["note"], wraplength=420).pack(anchor="w")
        ttk.Label(right, text="Comments", font=("Segoe UI", 11, "bold")).pack(anchor="w",
                                                                               pady=(8, 0))
        for line in comment_lines(r):
            ttk.Label(right, text=line, wraplength=420).pack(anchor="w")

    def _changed(self):
        if self.on_change:
            self.on_change()

    def comment(self):
        text = ask_text(self, f"Reading {self.ai_result_id}",
                        "Your comment (seen by the module's staff)" if self.who.is_student
                        else "Your reply (seen by the student)")
        if text and call(self, integrity_ai.comment, self.who, self.ai_result_id, text,
                         write=True) is not None:
            self._changed()
            self.destroy()
            ReadingWindow(self.master, self.who, self.ai_result_id, self.on_change)

    def review(self, decision):
        note = ask_text(self, f"Reading {self.ai_result_id}",
                        "Reason (for a referral: the concern, sent to the student)")
        if not note:
            return
        out = call(self, integrity_ai.review_flag, self.who, self.ai_result_id, decision, note,
                   write=True)
        if out is not None:
            if out.get("case_id"):
                info(self, f"Case {out['case_id']} opened and the student told.")
            self._changed()
            self.destroy()


class AiWritingTab(RecordTab):
    """AI-writing readings on the person's modules: flagged ones to clear
    or refer, every reading, and taking a reading of a submission."""

    columns = [("id", "Reading", 60), ("title", "Work", 210), ("student", "Student", 90),
               ("module", "Module", 80), ("level", "Level", 130), ("strength", "Strength", 65),
               ("review", "Review", 90)]
    statuses = STATUSES
    _threshold = 1.0

    def new_actions(self):
        return [("Read a submission…", self.read_submission),
                ("Read pasted text…", self.read_text)]

    def load(self, conn, search, status):
        self._threshold = access.number(conn, "ai_review_threshold")
        status = status or "waiting review"
        if status in ("flagged", "waiting review"):
            rows = integrity_ai.flags(conn, self.who, include_reviewed=status == "flagged")
        else:
            rows = integrity_ai.results(conn, self.who)
            if status == "reviewed":
                rows = [r for r in rows if r["decision"]]
        if search:
            needle = search.lower()
            rows = [r for r in rows if needle in " ".join(str(r.get(k) or "") for k in (
                "title", "student_id", "course_code")).lower()]
        return rows

    def values(self, row):
        return [row["id"], row["title"], row["student_id"], row["course_code"],
                nice(row["level"]), strength(row),
                nice(row["decision"]) or ("waiting" if self._flagged(row) else "—")]

    def _flagged(self, row) -> bool:
        return float(row.get("ai_score") or 0) >= self._threshold

    def fetch(self, conn, record_id):
        return integrity_ai.result_detail(conn, self.who, int(record_id))

    def render(self, record):
        self.detail.show(f"AI-writing reading {record['id']}", [
            ("", record["notice"]),
            ("", [("Work", record["title"]), ("Student", record["student_id"]),
                  ("Module", record["course_code"]), ("Assignment", record["assignment_id"]),
                  ("Level", nice(record["level"])), ("Strength", strength(record)),
                  ("Words read", record.get("words_checked")),
                  ("Taken", record["created_at"]), ("Taken by", record["checked_by"]),
                  ("Review", nice(record["decision"])), ("Reviewed by", record["reviewed_by"]),
                  ("Reason", record["note"]), ("Case", record["case_id"])]),
            ("Indicators", indicator_lines(record)),
            ("Comments", comment_lines(record))])

    def actions(self, record):
        found = [("Open reading", lambda: ReadingWindow(self, self.who, record["id"],
                                                        on_change=self.reload)),
                 ("Reply…", lambda: self.reply(record))]
        if not record["decision"]:
            found += [("No concern…", lambda: self.decide(record, "no_concern")),
                      ("Refer as a case…", lambda: self.decide(record, "refer"))]
        return found

    def decide(self, record, decision):
        note = ask_text(self, f"AI-writing reading {record['id']}",
                        "Reason (for a referral: the concern, sent to the student)")
        if not note:
            return
        result = self.write(integrity_ai.review_flag, self.who, record["id"], decision, note)
        if result and result.get("case_id"):
            info(self, f"Case {result['case_id']} opened and the student told.")

    def reply(self, record):
        text = ask_text(self, f"Reading {record['id']}", "Your reply (seen by the student)")
        if text:
            self.write(integrity_ai.comment, self.who, record["id"], text)

    def read_submission(self):
        values = ask(self, "Read a submission", [
            pickers.submission_field(self, self.who)])
        if not values:
            return
        submission_id = int(values["submission_id"])
        from education_system.systems.university.infrastructure.integrity import text_extract
        text = call(self, text_extract.submission_text, submission_id)
        if text is None:
            return
        result_id = self.write(integrity_ai.run_check, self.who, text=text[0], module_code=None,
                               submission_id=submission_id, file_type=text[1])
        if result_id:
            ReadingWindow(self, self.who, result_id, on_change=self.reload)

    def read_text(self):
        values = ask(self, "Read pasted or loaded text", [
            pickers.module_field(self, self.who, required=True),
            pickers.student_field(self, self.who, required=True, module_key="module_code"),
            pickers.assignment_field(self, self.who, label="Assignment (optional)"),
            Field("title", "Title"),
            Field("path", "File (blank to paste)", hint="path to .pdf / .docx / .txt"),
            Field("text", "Text", "multiline")])
        if not values:
            return
        text, kind = values["text"], "txt"
        if values["path"]:
            from education_system.systems.university.infrastructure.integrity import text_extract
            try:
                text, kind = text_extract.extract(values["path"]), \
                    text_extract.file_type(values["path"])
            except ValueError as exc:
                info(self, str(exc))
                return
        if not str(text or "").strip():
            info(self, "Paste the text or give a file.")
            return
        assignment = values["assignment_id"] if values["assignment_id"] not in ("", None) \
            else None
        result_id = self.write(integrity_ai.run_check, self.who, text=text,
                               module_code=values["module_code"],
                               student_id=values["student_id"], assignment_id=assignment,
                               title=values["title"], file_type=kind)
        if result_id:
            ReadingWindow(self, self.who, result_id, on_change=self.reload)


class MyAiReadingsTab(RecordTab):
    """The student's own released AI-writing readings, with comments."""

    columns = [("id", "Reading", 60), ("title", "Work", 260), ("module", "Module", 90),
               ("level", "Level", 150), ("review", "Review", 100)]

    def load(self, conn, search, status):
        rows = integrity_ai.results(conn, self.who)
        if search:
            rows = [r for r in rows if search.lower() in (r["title"] or "").lower()]
        return rows

    def values(self, row):
        return [row["id"], row["title"], row["course_code"], nice(row["level"]),
                nice(row["decision"]) or "—"]

    def fetch(self, conn, record_id):
        return integrity_ai.result_detail(conn, self.who, int(record_id))

    def render(self, record):
        self.detail.show(f"Reading {record['id']}", [
            ("", record["notice"]),
            ("", [("Work", record["title"]), ("Module", record["course_code"]),
                  ("Level", nice(record["level"])), ("Taken", record["created_at"]),
                  ("Review", nice(record["decision"]))]),
            ("Indicators", indicator_lines(record)),
            ("Comments", comment_lines(record)),
            ("", "If you think a reading is wrong, say so in a comment: the module's staff "
                 "see it. Nothing is decided on a reading alone.")])

    def actions(self, record):
        return [("Open with my text highlighted",
                 lambda: ReadingWindow(self, self.who, record["id"], on_change=self.reload)),
                ("Comment…", lambda: self.comment(record))]

    def comment(self, record):
        text = ask_text(self, f"Reading {record['id']}",
                        "Your comment (seen by the module's staff)")
        if text:
            self.write(integrity_ai.comment, self.who, record["id"], text,
                       done="Your comment was sent.")
